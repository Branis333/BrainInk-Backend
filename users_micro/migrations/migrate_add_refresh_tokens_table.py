#!/usr/bin/env python3
"""
Migration script to create the refresh_tokens table for long-lived sessions
and add the user_id foreign key to users.id. Safe to run multiple times.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables from project root .env
load_dotenv()


def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    parsed = urlparse(database_url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password,
        sslmode=os.getenv("PGSSLMODE", "require"),
    )


def ensure_refresh_tokens_table():
    print("\n🔄 Starting migration to add refresh_tokens table...")
    conn = get_conn()
    cur = conn.cursor()

    try:
        # Create extension for UUID if needed (not used here but common)
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

        # Create table if missing
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(128) NOT NULL,
                client_type VARCHAR(20) NOT NULL DEFAULT 'web',
                user_agent TEXT,
                issued_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                last_used_at TIMESTAMP WITHOUT TIME ZONE,
                CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash)
            );
            """
        )
        print("✅ Created/verified refresh_tokens table")

        # Helpful index for lookups by hash
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
            ON refresh_tokens(token_hash);
            """
        )
        print("✅ Created/verified idx_refresh_tokens_token_hash")

        # Helpful index for user lookups
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
            ON refresh_tokens(user_id);
            """
        )
        print("✅ Created/verified idx_refresh_tokens_user_id")

        conn.commit()
        print("\n🎉 Migration completed successfully! refresh_tokens is ready.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    ensure_refresh_tokens_table()
