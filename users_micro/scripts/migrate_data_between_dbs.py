#!/usr/bin/env python3
"""
Data-only PostgreSQL migration script.

Purpose:
- Copy all table data from a source PostgreSQL database to a target PostgreSQL database.
- Does NOT create or alter tables (schema must already exist in target).

Behavior:
- Discovers tables from source schema (default: public).
- Optionally truncates target tables before copy (recommended for full migration).
- Copies matching columns only (source/target intersection), so small schema drifts are tolerated.
- Resets sequences in target after copy to avoid primary key collisions.

Usage examples:
  python scripts/migrate_data_between_dbs.py \
    --source-url "$OLD_DATABASE_URL" \
    --target-url "$NEW_DATABASE_URL" \
    --truncate-target

  python scripts/migrate_data_between_dbs.py \
    --source-url "$OLD_DATABASE_URL" \
    --target-url "$NEW_DATABASE_URL" \
    --schema public \
    --exclude alembic_version

You can also use env vars:
  SOURCE_DATABASE_URL
  TARGET_DATABASE_URL
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import psycopg2
from psycopg2 import sql


@dataclass
class TableInfo:
    schema: str
    name: str


def parse_args() -> argparse.Namespace:
    default_excluded_tables = [
        "student_images",
        "as_ai_submissions",
        "student_pdfs",
        "report_shares",
    ]

    parser = argparse.ArgumentParser(description="Data-only Postgres migration (no schema migration).")
    parser.add_argument("--source-url", default=os.getenv("SOURCE_DATABASE_URL"), help="Source PostgreSQL URL")
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL"), help="Target PostgreSQL URL")
    parser.add_argument("--schema", default="public", help="Schema to migrate (default: public)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=default_excluded_tables.copy(),
        help="Table name to exclude. Repeatable, e.g. --exclude alembic_version",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Truncate target tables before copy (recommended for full replacement)",
    )
    parser.add_argument(
        "--keep-target-data",
        action="store_true",
        help="Do not truncate target tables. Use with caution; may cause duplicate key conflicts.",
    )
    return parser.parse_args()


def require_args(args: argparse.Namespace) -> None:
    if not args.source_url:
        raise ValueError("Missing --source-url (or SOURCE_DATABASE_URL env var).")
    if not args.target_url:
        raise ValueError("Missing --target-url (or TARGET_DATABASE_URL env var).")
    if args.truncate_target and args.keep_target_data:
        raise ValueError("Choose either --truncate-target or --keep-target-data, not both.")


def get_connection(dsn: str):
    return psycopg2.connect(dsn)


def get_tables(conn, schema: str, exclude: Sequence[str]) -> List[TableInfo]:
    exclude_set = {name.strip().lower() for name in exclude}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """,
            (schema,),
        )
        rows = cur.fetchall()

    tables = [TableInfo(schema=row[0], name=row[1]) for row in rows if row[1].lower() not in exclude_set]
    return tables


def to_table_name_set(tables: Sequence[TableInfo]) -> set[str]:
    return {t.name for t in tables}


def get_fk_dependencies(conn, schema: str, table_names: Sequence[str]) -> dict[str, set[str]]:
    """Return dependency map: child_table -> {parent_table, ...} limited to provided table_names."""
    name_set = set(table_names)
    deps: dict[str, set[str]] = {name: set() for name in name_set}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                tc.table_name AS child_table,
                ccu.table_name AS parent_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s;
            """,
            (schema,),
        )
        rows = cur.fetchall()

    for child, parent in rows:
        if child in name_set and parent in name_set:
            deps[child].add(parent)

    return deps


def order_tables_by_fk(conn, schema: str, tables: Sequence[TableInfo]) -> list[TableInfo]:
    """Topologically order tables so parent tables are copied before FK-dependent child tables."""
    by_name = {t.name: t for t in tables}
    names = list(by_name.keys())
    deps = get_fk_dependencies(conn, schema, names)

    # Kahn algorithm
    in_degree: dict[str, int] = {n: 0 for n in names}
    children: dict[str, set[str]] = {n: set() for n in names}
    for child, parents in deps.items():
        in_degree[child] = len(parents)
        for p in parents:
            children[p].add(child)

    ready = sorted([n for n in names if in_degree[n] == 0])
    ordered_names: list[str] = []

    while ready:
        n = ready.pop(0)
        ordered_names.append(n)
        for c in sorted(children[n]):
            in_degree[c] -= 1
            if in_degree[c] == 0:
                ready.append(c)
        ready.sort()

    # Cyclic dependencies (or self-references) are appended in deterministic order.
    if len(ordered_names) < len(names):
        remaining = sorted([n for n in names if n not in set(ordered_names)])
        ordered_names.extend(remaining)

    return [by_name[n] for n in ordered_names]


def get_columns(conn, table: TableInfo) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table.schema, table.name),
        )
        return [r[0] for r in cur.fetchall()]


def quote_ident_list(names: Iterable[str]) -> sql.SQL:
    return sql.SQL(", ").join(sql.Identifier(name) for name in names)


def truncate_target_tables(conn, tables: Sequence[TableInfo]) -> None:
    if not tables:
        return
    with conn.cursor() as cur:
        qualified = [sql.SQL("{}.{}").format(sql.Identifier(t.schema), sql.Identifier(t.name)) for t in tables]
        stmt = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE;").format(sql.SQL(", ").join(qualified))
        cur.execute(stmt)


def copy_table_data(source_conn, target_conn, table: TableInfo) -> tuple[int, List[str]]:
    source_cols = get_columns(source_conn, table)
    target_cols = get_columns(target_conn, table)
    common_cols = [c for c in source_cols if c in set(target_cols)]

    if not common_cols:
        return 0, []

    buffer = io.StringIO()

    select_stmt = sql.SQL("COPY (SELECT {} FROM {}.{}) TO STDOUT WITH CSV").format(
        quote_ident_list(common_cols),
        sql.Identifier(table.schema),
        sql.Identifier(table.name),
    )

    with source_conn.cursor() as src_cur:
        src_cur.copy_expert(select_stmt, buffer)

    buffer.seek(0)

    copy_in_stmt = sql.SQL("COPY {}.{} ({}) FROM STDIN WITH CSV").format(
        sql.Identifier(table.schema),
        sql.Identifier(table.name),
        quote_ident_list(common_cols),
    )

    with target_conn.cursor() as dst_cur:
        dst_cur.copy_expert(copy_in_stmt, buffer)

    with target_conn.cursor() as cnt_cur:
        cnt_stmt = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(table.schema),
            sql.Identifier(table.name),
        )
        cnt_cur.execute(cnt_stmt)
        count = int(cnt_cur.fetchone()[0])

    return count, common_cols


def reset_sequences(conn, schema: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              c.table_name,
              c.column_name,
                            pg_get_serial_sequence(format('%%I.%%I', c.table_schema, c.table_name), c.column_name) AS seq_name
            FROM information_schema.columns c
            WHERE c.table_schema = %s
                            AND pg_get_serial_sequence(format('%%I.%%I', c.table_schema, c.table_name), c.column_name) IS NOT NULL;
            """,
            (schema,),
        )
        rows = cur.fetchall()

    with conn.cursor() as cur:
        for table_name, column_name, seq_name in rows:
            max_stmt = sql.SQL("SELECT MAX({col}) FROM {sch}.{tbl}").format(
                col=sql.Identifier(column_name),
                sch=sql.Identifier(schema),
                tbl=sql.Identifier(table_name),
            )
            cur.execute(max_stmt)
            max_id = cur.fetchone()[0]

            # For empty tables, reset sequence to start value (1) and mark as not called.
            if max_id is None:
                cur.execute("SELECT setval(%s, 1, false)", (seq_name,))
            else:
                cur.execute("SELECT setval(%s, %s, true)", (seq_name, int(max_id)))


def main() -> int:
    args = parse_args()
    try:
        require_args(args)
    except ValueError as exc:
        print(f"Argument error: {exc}", file=sys.stderr)
        return 2

    print("Starting data-only migration...")
    print(f"Schema: {args.schema}")

    src = get_connection(args.source_url)
    dst = get_connection(args.target_url)

    try:
        src.autocommit = True
        dst.autocommit = False

        source_tables = get_tables(src, args.schema, args.exclude)
        target_tables = get_tables(dst, args.schema, args.exclude)

        if not source_tables:
            print("No source tables found to migrate.")
            dst.rollback()
            return 0

        if not target_tables:
            print("No target tables found to migrate.", file=sys.stderr)
            dst.rollback()
            return 1

        source_names = to_table_name_set(source_tables)
        target_names = to_table_name_set(target_tables)
        common_names = source_names.intersection(target_names)
        missing_in_target = sorted(source_names.difference(target_names))

        tables = [t for t in source_tables if t.name in common_names]
        tables = order_tables_by_fk(dst, args.schema, tables)

        print(f"Discovered {len(source_tables)} source table(s).")
        print(f"Discovered {len(target_tables)} target table(s).")
        print(f"Will migrate {len(tables)} common table(s).")

        if missing_in_target:
            print(f"Skipping {len(missing_in_target)} table(s) missing in target: {', '.join(missing_in_target)}")

        if not tables:
            print("No common tables to migrate.")
            dst.rollback()
            return 0

        if args.truncate_target and not args.keep_target_data:
            print("Truncating target tables (RESTART IDENTITY CASCADE)...")
            truncate_target_tables(dst, tables)

        # Defers DEFERRABLE constraints until commit where possible.
        with dst.cursor() as cur:
            cur.execute("SET CONSTRAINTS ALL DEFERRED;")

        pending = list(tables)
        last_errors: dict[str, str] = {}
        migrated_tables = 0
        max_passes = 3

        for attempt in range(1, max_passes + 1):
            if not pending:
                break

            print(f"Migration pass {attempt}: {len(pending)} table(s) pending")
            progressed = False
            next_pending: list[TableInfo] = []

            for t in pending:
                savepoint_name = f"sp_{attempt}_{t.name}"
                with dst.cursor() as cur:
                    cur.execute(sql.SQL("SAVEPOINT {};").format(sql.Identifier(savepoint_name)))

                try:
                    count, cols = copy_table_data(src, dst, t)
                    with dst.cursor() as cur:
                        cur.execute(sql.SQL("RELEASE SAVEPOINT {};").format(sql.Identifier(savepoint_name)))
                    migrated_tables += 1
                    progressed = True
                    print(
                        f"[{migrated_tables}/{len(tables)}] {t.schema}.{t.name}: "
                        f"copied using {len(cols)} column(s), target rows={count}"
                    )
                except Exception as table_exc:
                    with dst.cursor() as cur:
                        cur.execute(sql.SQL("ROLLBACK TO SAVEPOINT {};").format(sql.Identifier(savepoint_name)))
                        cur.execute(sql.SQL("RELEASE SAVEPOINT {};").format(sql.Identifier(savepoint_name)))
                    next_pending.append(t)
                    last_errors[t.name] = str(table_exc)

            pending = next_pending
            if pending and not progressed:
                break

        if pending:
            print("Could not migrate some tables after retries:", file=sys.stderr)
            for t in pending:
                print(f" - {t.schema}.{t.name}: {last_errors.get(t.name, 'unknown error')}", file=sys.stderr)
            raise RuntimeError("Migration stopped due to unresolved table copy errors.")

        print("Resetting sequences...")
        reset_sequences(dst, args.schema)

        dst.commit()
        print("Migration completed successfully.")
        return 0

    except Exception as exc:
        dst.rollback()
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1

    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
