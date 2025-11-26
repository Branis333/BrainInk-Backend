#!/usr/bin/env python3
"""
Migration script to add image column to as_courses table
Stores compressed course images as binary data in the database
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

def add_image_column():
    """Add image column to as_courses table for storing compressed course images"""
    
    print("🔄 Starting migration to add image column to as_courses table...")
    
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
        # Check if image column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'as_courses' AND column_name = 'image'
        """)
        image_column_exists = cursor.fetchone() is not None
        
        if image_column_exists:
            print("✅ Image column already exists in as_courses table")
        else:
            print("➕ Adding image column to as_courses table...")
            
            # Add image column as BYTEA (PostgreSQL binary data type)
            # BYTEA stores compressed image bytes directly in the database
            alter_query = """
                ALTER TABLE as_courses 
                ADD COLUMN image BYTEA
            """
            
            cursor.execute(alter_query)
            print("✅ Image column added successfully")
            
            # Add index on course id for faster lookups
            print("📊 Adding database indexes for optimal performance...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_as_courses_image 
                ON as_courses(id) 
                WHERE image IS NOT NULL
            """)
            print("✅ Index created for courses with images")
        
        # Display current table structure
        print("\n📋 Current as_courses table structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'as_courses'
            ORDER BY ordinal_position
        """)
        
        all_columns = cursor.fetchall()
        print(f"{'Column Name':<25} {'Data Type':<20} {'Nullable':<10} {'Default':<30}")
        print("-" * 85)
        for col_name, data_type, nullable, default in all_columns:
            nullable_str = "YES" if nullable == 'YES' else "NO"
            default_str = default if default else ""
            print(f"{col_name:<25} {data_type:<20} {nullable_str:<10} {default_str:<30}")
        
        # Commit changes
        conn.commit()
        print(f"\n🎉 Migration completed successfully!")
        print(f"✅ Image column is now available in as_courses table")
        print(f"📸 Features:")
        print(f"   - Stores compressed course images as binary data (BYTEA)")
        print(f"   - Images are automatically compressed by image_service.py (~50% size reduction)")
        print(f"   - No external file paths needed - data stays in database")
        print(f"   - Supports PNG, JPG, JPEG, WEBP, GIF, BMP formats")
        print(f"   - Max file size: 5MB before compression")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise e
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_image_column()
