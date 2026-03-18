#!/usr/bin/env python3
"""
Migration script to add missing columns to as_courses table
This ensures the database schema matches the model definitions
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

def add_missing_columns():
    """Add missing columns to as_courses table"""
    
    print("🔄 Starting migration to add missing as_courses columns...")
    
    # Get database connection from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Parse DATABASE_URL
    parsed = urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    cursor = conn.cursor()
    
    try:
        # List of columns to add if they don't exist
        columns_to_add = [
            {
                "name": "total_weeks",
                "definition": "INTEGER NOT NULL DEFAULT 8",
                "description": "Total duration in weeks"
            },
            {
                "name": "blocks_per_week", 
                "definition": "INTEGER NOT NULL DEFAULT 2",
                "description": "Number of blocks per week"
            },
            {
                "name": "textbook_source",
                "definition": "TEXT",
                "description": "Source textbook information"
            },
            {
                "name": "textbook_content",
                "definition": "TEXT", 
                "description": "Original textbook content"
            },
            {
                "name": "generated_by_ai",
                "definition": "BOOLEAN DEFAULT FALSE",
                "description": "Whether course was AI-generated"
            }
        ]
        
        # Check which columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'as_courses'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Existing columns in as_courses: {existing_columns}")
        
        # Add missing columns
        for column in columns_to_add:
            if column["name"] not in existing_columns:
                print(f"➕ Adding column: {column['name']} - {column['description']}")
                
                alter_query = sql.SQL("ALTER TABLE as_courses ADD COLUMN {} {}").format(
                    sql.Identifier(column["name"]),
                    sql.SQL(column["definition"])
                )
                
                cursor.execute(alter_query)
                print(f"✅ Added column: {column['name']}")
            else:
                print(f"✅ Column {column['name']} already exists")
        
        # Verify all columns now exist
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'as_courses'
            ORDER BY ordinal_position
        """)
        
        all_columns = cursor.fetchall()
        print(f"\n📊 Final as_courses table structure:")
        for col_name, data_type, nullable, default in all_columns:
            print(f"   {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'} {f'DEFAULT {default}' if default else ''}")
        
        # Commit changes
        conn.commit()
        print(f"\n🎉 Migration completed successfully!")
        print(f"✅ All required columns are now present in as_courses table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise e
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_missing_columns()