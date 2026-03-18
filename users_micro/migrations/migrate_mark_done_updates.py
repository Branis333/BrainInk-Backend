#!/usr/bin/env python3
"""
Migration script to align database with mark-done model updates

Changes applied (idempotent):
1) as_ai_submissions
   - Make session_id NULLABLE
   - Ensure block_id (FK -> as_course_blocks.id)
   - Ensure assignment_id (FK -> as_course_assignments.id)
   - Ensure ai_corrections/ai_strengths/ai_improvements TEXT columns
   - Add CHECK constraint: (lesson_id IS NOT NULL) OR (block_id IS NOT NULL)

2) as_study_sessions
   - Make lesson_id NULLABLE
   - Ensure block_id (FK -> as_course_blocks.id)
   - Ensure status VARCHAR(20) NOT NULL DEFAULT 'pending'
   - Ensure completion_percentage DOUBLE PRECISION NOT NULL DEFAULT 0.0
   - Ensure marked_done_at TIMESTAMP NULL

3) as_student_progress
   - Ensure blocks_completed INT NOT NULL DEFAULT 0
   - Ensure total_blocks INT NOT NULL DEFAULT 0
   - Ensure average_score DOUBLE PRECISION NULL
   - Ensure total_study_time INT NOT NULL DEFAULT 0
   - Ensure sessions_count INT NOT NULL DEFAULT 0
   - Ensure started_at TIMESTAMP DEFAULT now()
   - Ensure last_activity TIMESTAMP DEFAULT now()
   - Ensure completed_at TIMESTAMP NULL

This migration is safe to run multiple times; it checks existence before applying changes.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

sys.path.append(str(Path(__file__).parent))


def get_connection():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    conn.autocommit = False
    return conn


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def is_column_nullable(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    if not row:
        return True
    return row[0] == 'YES'


def constraint_exists(cur, table_name: str, constraint_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = %s AND c.conname = %s
        """,
        (table_name, constraint_name),
    )
    return cur.fetchone() is not None


def fk_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.key_column_usage kcu
        JOIN information_schema.table_constraints tc
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.constraint_schema = tc.constraint_schema
        WHERE tc.table_name = %s
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def ensure_column(cur, table: str, name: str, definition: str, fk_ref: str | None = None, fk_name: str | None = None):
    if not column_exists(cur, table, name):
        print(f"➕ Adding column {table}.{name} ({definition})")
        cur.execute(sql.SQL("ALTER TABLE {} ADD COLUMN {} {};").format(
            sql.Identifier(table), sql.Identifier(name), sql.SQL(definition)
        ))
    else:
        print(f"✅ Column {table}.{name} already exists")

    if fk_ref and not fk_exists(cur, table, name):
        print(f"🔗 Adding foreign key on {table}.{name} → {fk_ref}")
        fk_ident = sql.Identifier(fk_name) if fk_name else sql.Identifier(f"fk_{table}_{name}")
        cur.execute(sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) REFERENCES {}(id);").format(
            sql.Identifier(table), fk_ident, sql.Identifier(name), sql.Identifier(fk_ref)
        ))
    elif fk_ref:
        print(f"✅ Foreign key for {table}.{name} already exists")


def migrate_as_study_sessions(cur):
    table = 'as_study_sessions'
    print(f"\n📦 Migrating {table} ...")

    # lesson_id nullable
    if column_exists(cur, table, 'lesson_id') and not is_column_nullable(cur, table, 'lesson_id'):
        print("✏️ Making as_study_sessions.lesson_id NULLABLE")
        cur.execute("ALTER TABLE as_study_sessions ALTER COLUMN lesson_id DROP NOT NULL;")
    else:
        print("✅ lesson_id already nullable or absent")

    # block_id
    ensure_column(cur, table, 'block_id', 'INTEGER', fk_ref='as_course_blocks', fk_name='fk_as_study_sessions_block_id')

    # status
    ensure_column(cur, table, 'status', "VARCHAR(20) NOT NULL DEFAULT 'pending'")

    # completion_percentage
    ensure_column(cur, table, 'completion_percentage', 'DOUBLE PRECISION NOT NULL DEFAULT 0.0')

    # marked_done_at
    ensure_column(cur, table, 'marked_done_at', 'TIMESTAMP NULL')


def migrate_as_ai_submissions(cur):
    table = 'as_ai_submissions'
    print(f"\n📦 Migrating {table} ...")

    # session_id nullable
    if column_exists(cur, table, 'session_id') and not is_column_nullable(cur, table, 'session_id'):
        print("✏️ Making as_ai_submissions.session_id NULLABLE")
        cur.execute("ALTER TABLE as_ai_submissions ALTER COLUMN session_id DROP NOT NULL;")
    else:
        print("✅ session_id already nullable or absent")

    # block_id
    ensure_column(cur, table, 'block_id', 'INTEGER', fk_ref='as_course_blocks', fk_name='fk_as_ai_submissions_block_id')

    # assignment_id
    ensure_column(cur, table, 'assignment_id', 'INTEGER', fk_ref='as_course_assignments', fk_name='fk_as_ai_submissions_assignment_id')

    # ai_* text helpers
    ensure_column(cur, table, 'ai_corrections', 'TEXT')
    ensure_column(cur, table, 'ai_strengths', 'TEXT')
    ensure_column(cur, table, 'ai_improvements', 'TEXT')

    # Check constraint for lesson or block
    constraint_name = 'ck_as_ai_submissions_lesson_or_block'
    if not constraint_exists(cur, table, constraint_name):
        print("🧩 Adding CHECK constraint (lesson_id IS NOT NULL) OR (block_id IS NOT NULL) as NOT VALID")
        cur.execute(
            sql.SQL(
                "ALTER TABLE {} ADD CONSTRAINT {} CHECK ((lesson_id IS NOT NULL) OR (block_id IS NOT NULL)) NOT VALID;"
            ).format(sql.Identifier(table), sql.Identifier(constraint_name))
        )
        # Try to validate (won't block future inserts if data is already compliant)
        try:
            print("✅ Validating CHECK constraint ...")
            cur.execute(sql.SQL("ALTER TABLE {} VALIDATE CONSTRAINT {};").format(
                sql.Identifier(table), sql.Identifier(constraint_name)
            ))
        except Exception as e:
            # Keep it NOT VALID if existing rows violate; new rows will be checked
            print(f"⚠️ Validation failed; constraint remains NOT VALID. Existing rows may not comply. Details: {e}")
    else:
        print("✅ CHECK constraint already exists")


def migrate_as_student_progress(cur):
    table = 'as_student_progress'
    print(f"\n📦 Migrating {table} ...")

    ensure_column(cur, table, 'blocks_completed', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(cur, table, 'total_blocks', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(cur, table, 'average_score', 'DOUBLE PRECISION')
    ensure_column(cur, table, 'total_study_time', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(cur, table, 'sessions_count', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(cur, table, 'started_at', 'TIMESTAMP DEFAULT now()')
    ensure_column(cur, table, 'last_activity', 'TIMESTAMP DEFAULT now()')
    ensure_column(cur, table, 'completed_at', 'TIMESTAMP NULL')


def run_migration():
    print("🚀 Starting mark-done schema migration ...")
    conn = get_connection()
    cur = conn.cursor()

    try:
        migrate_as_study_sessions(cur)
        migrate_as_ai_submissions(cur)
        migrate_as_student_progress(cur)

        conn.commit()
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
