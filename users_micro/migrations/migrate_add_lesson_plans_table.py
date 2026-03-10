#!/usr/bin/env python3
"""
Migration script to add lesson_plans table used by teacher lesson planning.
Pattern follows existing direct psycopg2 migration scripts in this repository.
"""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables
load_dotenv()


def _constraint_exists(cursor, constraint_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_name = 'lesson_plans'
          AND constraint_name = %s
        """,
        (constraint_name,),
    )
    return cursor.fetchone() is not None


def _index_exists(cursor, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'lesson_plans'
          AND indexname = %s
        """,
        (index_name,),
    )
    return cursor.fetchone() is not None


def migrate_lesson_plans_table():
    print("\n🔄 Starting migration for lesson_plans table...")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    parsed = urlparse(database_url)

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password,
        sslmode=os.getenv("PGSSLMODE", "require"),
    )
    cursor = conn.cursor()

    try:
        # Check if lesson_plans table already exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'lesson_plans'
            )
            """
        )
        table_exists = bool(cursor.fetchone()[0])

        if not table_exists:
            print("➕ Creating table: lesson_plans")
            cursor.execute(
                """
                CREATE TABLE lesson_plans (
                    id SERIAL PRIMARY KEY,
                    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
                    classroom_id INTEGER NOT NULL REFERENCES classrooms(id),
                    subject_id INTEGER NOT NULL REFERENCES subjects(id),
                    title VARCHAR NOT NULL,
                    description TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL DEFAULT 45,
                    learning_objectives TEXT,
                    activities TEXT,
                    materials_needed TEXT,
                    assessment_strategy TEXT,
                    homework TEXT,
                    references TEXT,
                    source_filename VARCHAR,
                    source_mime_type VARCHAR,
                    source_summary TEXT,
                    generated_by_ai BOOLEAN DEFAULT FALSE,
                    created_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    updated_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                )
                """
            )
            print("✅ Created table: lesson_plans")
        else:
            print("✅ Table lesson_plans already exists; checking missing columns...")

            columns_to_add = [
                {"name": "teacher_id", "definition": "INTEGER REFERENCES teachers(id)", "description": "Teacher owner"},
                {"name": "classroom_id", "definition": "INTEGER REFERENCES classrooms(id)", "description": "Classroom scope"},
                {"name": "subject_id", "definition": "INTEGER REFERENCES subjects(id)", "description": "Subject scope"},
                {"name": "title", "definition": "VARCHAR", "description": "Lesson title"},
                {"name": "description", "definition": "TEXT", "description": "Lesson description"},
                {"name": "duration_minutes", "definition": "INTEGER DEFAULT 45", "description": "Lesson duration"},
                {"name": "learning_objectives", "definition": "TEXT", "description": "JSON-encoded objectives"},
                {"name": "activities", "definition": "TEXT", "description": "JSON-encoded activities"},
                {"name": "materials_needed", "definition": "TEXT", "description": "JSON-encoded materials"},
                {"name": "assessment_strategy", "definition": "TEXT", "description": "Assessment strategy"},
                {"name": "homework", "definition": "TEXT", "description": "Homework plan"},
                {"name": "references", "definition": "TEXT", "description": "JSON-encoded references"},
                {"name": "source_filename", "definition": "VARCHAR", "description": "Uploaded source filename"},
                {"name": "source_mime_type", "definition": "VARCHAR", "description": "Uploaded source MIME type"},
                {"name": "source_summary", "definition": "TEXT", "description": "Source summary/context"},
                {"name": "generated_by_ai", "definition": "BOOLEAN DEFAULT FALSE", "description": "AI generation flag"},
                {"name": "created_date", "definition": "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()", "description": "Creation time"},
                {"name": "updated_date", "definition": "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()", "description": "Update time"},
                {"name": "is_active", "definition": "BOOLEAN DEFAULT TRUE", "description": "Soft-delete flag"},
            ]

            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'lesson_plans'
                """
            )
            existing_columns = {row[0] for row in cursor.fetchall()}
            print(f"📋 Existing columns in lesson_plans: {sorted(existing_columns)}")

            for col in columns_to_add:
                if col["name"] not in existing_columns:
                    print(f"➕ Adding column: {col['name']} - {col['description']}")
                    alter = sql.SQL("ALTER TABLE lesson_plans ADD COLUMN {} {}").format(
                        sql.Identifier(col["name"]),
                        sql.SQL(col["definition"]),
                    )
                    cursor.execute(alter)
                    print(f"✅ Added column: {col['name']}")
                else:
                    print(f"✅ Column {col['name']} already exists")

            # Backfill defaults for rows added before defaults existed
            cursor.execute("UPDATE lesson_plans SET duration_minutes = 45 WHERE duration_minutes IS NULL")
            cursor.execute("UPDATE lesson_plans SET generated_by_ai = FALSE WHERE generated_by_ai IS NULL")
            cursor.execute("UPDATE lesson_plans SET is_active = TRUE WHERE is_active IS NULL")

        # Ensure key constraints exist when table was partially created outside this script
        required_constraints = [
            {
                "name": "lesson_plans_teacher_id_fkey",
                "sql": "ALTER TABLE lesson_plans ADD CONSTRAINT lesson_plans_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES teachers(id)",
            },
            {
                "name": "lesson_plans_classroom_id_fkey",
                "sql": "ALTER TABLE lesson_plans ADD CONSTRAINT lesson_plans_classroom_id_fkey FOREIGN KEY (classroom_id) REFERENCES classrooms(id)",
            },
            {
                "name": "lesson_plans_subject_id_fkey",
                "sql": "ALTER TABLE lesson_plans ADD CONSTRAINT lesson_plans_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES subjects(id)",
            },
        ]

        for item in required_constraints:
            if not _constraint_exists(cursor, item["name"]):
                try:
                    print(f"➕ Adding constraint: {item['name']}")
                    cursor.execute(item["sql"])
                    print(f"✅ Added constraint: {item['name']}")
                except Exception as c_err:
                    # Non-fatal for legacy db states; surface as warning and continue.
                    print(f"⚠️ Could not add constraint {item['name']}: {c_err}")
            else:
                print(f"✅ Constraint {item['name']} already exists")

        # Ensure indexes used by query patterns exist
        index_queries = [
            ("ix_lesson_plans_teacher_id", "CREATE INDEX ix_lesson_plans_teacher_id ON lesson_plans (teacher_id)"),
            ("ix_lesson_plans_classroom_id", "CREATE INDEX ix_lesson_plans_classroom_id ON lesson_plans (classroom_id)"),
            ("ix_lesson_plans_subject_id", "CREATE INDEX ix_lesson_plans_subject_id ON lesson_plans (subject_id)"),
        ]

        for index_name, create_sql in index_queries:
            if not _index_exists(cursor, index_name):
                print(f"➕ Creating index: {index_name}")
                cursor.execute(create_sql)
                print(f"✅ Created index: {index_name}")
            else:
                print(f"✅ Index {index_name} already exists")

        # Show final table structure
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'lesson_plans'
            ORDER BY ordinal_position
            """
        )
        all_columns = cursor.fetchall()
        print("\n📊 Final lesson_plans table structure:")
        for col_name, data_type, nullable, default in all_columns:
            default_str = f" DEFAULT {default}" if default else ""
            print(f"   {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'}{default_str}")

        conn.commit()
        print("\n🎉 Migration completed successfully! lesson_plans is up-to-date.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    migrate_lesson_plans_table()
