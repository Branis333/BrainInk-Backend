#!/usr/bin/env python3
"""
Migration script to add grade posting/review columns to grades table
Adds is_posted and posted_date columns to support grade review workflow
where teachers can review grades before publishing them to students
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables
load_dotenv()


def add_grade_posting_columns():
    print("\n🔄 Starting migration to add grade posting columns to grades table...")

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
                "name": "is_posted",
                "definition": "BOOLEAN DEFAULT FALSE",
                "description": "Whether grade has been shared with student",
            },
            {
                "name": "posted_date",
                "definition": "TIMESTAMP DEFAULT NULL",
                "description": "When grade was posted to student",
            },
        ]

        # Check existing columns
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'grades'
            """
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
        print(f"📋 Existing columns in grades table: {sorted(existing_columns)}")

        # Add missing columns
        for col in columns_to_add:
            if col["name"] not in existing_columns:
                print(f"➕ Adding column: {col['name']} - {col['description']}")
                alter = sql.SQL("ALTER TABLE grades ADD COLUMN {} {}").format(
                    sql.Identifier(col["name"]), sql.SQL(col["definition"])
                )
                cursor.execute(alter)
                print(f"✅ Added column: {col['name']}")
            else:
                print(f"✅ Column {col['name']} already exists")

        # Commit changes
        conn.commit()
        print("✅ Migration committed successfully!")

        # Show final table structure
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'grades'
            ORDER BY ordinal_position
            """
        )
        all_columns = cursor.fetchall()
        print("\n📊 Final grades table structure:")
        for col_name, data_type, nullable, default in all_columns:
            default_str = f" DEFAULT {default}" if default else ""
            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            print(f"   {col_name}: {data_type} {null_str}{default_str}")

        print("\n✨ Grade posting migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed with error: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    add_grade_posting_columns()
