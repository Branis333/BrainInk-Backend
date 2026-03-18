#!/usr/bin/env python3
"""
Migration script to make session_id column nullable in as_ai_submissions table
This allows assignments to be submitted without requiring a session_id
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

def make_session_id_nullable():
    """Make session_id column nullable in as_ai_submissions table"""
    
    print("🔄 Starting migration to make session_id nullable in as_ai_submissions...")
    
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
        # Check current structure of as_ai_submissions table
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'as_ai_submissions'
            ORDER BY ordinal_position
        """)
        
        columns_before = cursor.fetchall()
        print(f"📊 Current as_ai_submissions table structure:")
        session_id_found = False
        session_id_nullable = False
        
        for col_name, data_type, nullable, default in columns_before:
            if col_name == 'session_id':
                session_id_found = True
                session_id_nullable = nullable == 'YES'
                print(f"   🎯 {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'} {f'DEFAULT {default}' if default else ''}")
            else:
                print(f"   {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'} {f'DEFAULT {default}' if default else ''}")
        
        if not session_id_found:
            print("❌ session_id column not found in as_ai_submissions table")
            return
        
        if session_id_nullable:
            print("✅ session_id column is already nullable - no migration needed")
            return
        
        print(f"\n🔧 Making session_id column nullable...")
        
        # Make session_id column nullable
        alter_query = """
            ALTER TABLE as_ai_submissions 
            ALTER COLUMN session_id DROP NOT NULL
        """
        
        cursor.execute(alter_query)
        print(f"✅ Successfully made session_id column nullable")
        
        # Verify the change
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'as_ai_submissions' AND column_name = 'session_id'
        """)
        
        result = cursor.fetchone()
        if result:
            col_name, data_type, nullable, default = result
            print(f"✅ Verification: {col_name} is now {'nullable' if nullable == 'YES' else 'NOT NULL'}")
        
        # Show final table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'as_ai_submissions'
            ORDER BY ordinal_position
        """)
        
        columns_after = cursor.fetchall()
        print(f"\n📊 Final as_ai_submissions table structure:")
        for col_name, data_type, nullable, default in columns_after:
            if col_name == 'session_id':
                print(f"   🎯 {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'} {f'DEFAULT {default}' if default else ''}")
            else:
                print(f"   {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'} {f'DEFAULT {default}' if default else ''}")
        
        # Commit changes
        conn.commit()
        print(f"\n🎉 Migration completed successfully!")
        print(f"✅ session_id column in as_ai_submissions is now nullable")
        print(f"🚀 Assignment submissions can now be created without session_id")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise e
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    make_session_id_nullable()