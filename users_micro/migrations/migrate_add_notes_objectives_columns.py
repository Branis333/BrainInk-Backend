#!/usr/bin/env python3
"""
Migration script to add objectives/flashcards/progress columns to as_student_notes
Simple, direct migration similar to migrate_add_missing_course_columns.py
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables
load_dotenv()


def add_missing_note_columns():
    print("\n🔄 Starting migration to add objectives/flashcards/progress to as_student_notes...")

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
        # Columns we want to ensure exist
        columns_to_add = [
            {
                "name": "objectives",
                "definition": "JSONB",
                "description": "Per-objective data with summaries and videos",
            },
            {
                "name": "objective_flashcards",
                "definition": "JSONB",
                "description": "Flashcards list per objective (list of lists)",
            },
            {
                "name": "overall_flashcards",
                "definition": "JSONB",
                "description": "Flashcards from entire note summary",
            },
            {
                "name": "objective_progress",
                "definition": "JSONB",
                "description": "Per-objective latest grade and performance summary",
            },
        ]

        # Check existing columns
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'as_student_notes'
            """
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
        print(f"📋 Existing columns in as_student_notes: {sorted(existing_columns)}")

        # Add missing columns
        for col in columns_to_add:
            if col["name"] not in existing_columns:
                print(f"➕ Adding column: {col['name']} - {col['description']}")
                alter = sql.SQL("ALTER TABLE as_student_notes ADD COLUMN {} {}").format(
                    sql.Identifier(col["name"]), sql.SQL(col["definition"])
                )
                cursor.execute(alter)
                print(f"✅ Added column: {col['name']}")
            else:
                print(f"✅ Column {col['name']} already exists")

        # Show final table structure
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'as_student_notes'
            ORDER BY ordinal_position
            """
        )
        all_columns = cursor.fetchall()
        print("\n📊 Final as_student_notes table structure:")
        for col_name, data_type, nullable, default in all_columns:
            default_str = f" DEFAULT {default}" if default else ""
            print(f"   {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'}{default_str}")

        conn.commit()
        print("\n🎉 Migration completed successfully! as_student_notes is up-to-date.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    add_missing_note_columns()
