#!/usr/bin/env python3
"""
Database migration script to update student_pdfs table for binary storage.
This script adds the necessary columns to support storing PDFs in the database.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path to import our modules
sys.path.append(str(Path(__file__).parent))

from users_micro.db.connection import get_db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def run_migration():
    """
    Run the database migration to add new columns for PDF binary storage
    """
    print("🚀 Starting database migration for student_pdfs table...")
    
    # Get database session
    db = next(get_db())
    
    migration_queries = [
        # Add new columns
        """
        ALTER TABLE student_pdfs 
        ADD COLUMN IF NOT EXISTS pdf_data BYTEA
        """,
        
        """
        ALTER TABLE student_pdfs 
        ADD COLUMN IF NOT EXISTS pdf_size INTEGER
        """,
        
        """
        ALTER TABLE student_pdfs 
        ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32)
        """,
        
        """
        ALTER TABLE student_pdfs 
        ADD COLUMN IF NOT EXISTS mime_type VARCHAR(50) DEFAULT 'application/pdf'
        """,
        
        # Update existing records
        """
        UPDATE student_pdfs 
        SET mime_type = 'application/pdf' 
        WHERE mime_type IS NULL
        """,
        
        # Create indexes
        """
        CREATE INDEX IF NOT EXISTS idx_student_pdfs_content_hash 
        ON student_pdfs(content_hash)
        """,
        
        """
        CREATE INDEX IF NOT EXISTS idx_student_pdfs_size 
        ON student_pdfs(pdf_size)
        """,
    ]
    
    try:
        print("📝 Executing migration queries...")
        
        for i, query in enumerate(migration_queries, 1):
            print(f"   {i}/{len(migration_queries)}: Executing...")
            db.execute(text(query))
            print(f"   ✅ Query {i} completed")
        
        # Commit all changes
        db.commit()
        print("💾 Migration committed successfully!")
        
        # Get migration summary
        print("\n📊 Checking migration results...")
        
        # Check table structure
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'student_pdfs' 
            ORDER BY ordinal_position
        """))
        
        print("\n📋 Current table structure:")
        for row in result:
            print(f"   - {row.column_name}: {row.data_type} "
                  f"({'NULL' if row.is_nullable == 'YES' else 'NOT NULL'})"
                  f"{' DEFAULT ' + str(row.column_default) if row.column_default else ''}")
        
        # Get record summary
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(pdf_data) as records_with_binary_data,
                COUNT(pdf_path) as records_with_file_paths,
                COALESCE(AVG(pdf_size), 0) as avg_pdf_size_bytes,
                COALESCE(SUM(pdf_size), 0) as total_storage_bytes
            FROM student_pdfs
        """))
        
        summary = result.fetchone()
        print(f"\n📈 Data summary:")
        print(f"   📁 Total records: {summary.total_records}")
        print(f"   💾 Records with binary data: {summary.records_with_binary_data}")
        print(f"   📂 Records with file paths: {summary.records_with_file_paths}")
        print(f"   📏 Average PDF size: {summary.avg_pdf_size_bytes:.0f} bytes")
        print(f"   💿 Total storage used: {summary.total_storage_bytes / 1024 / 1024:.2f} MB")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"💡 Your table is now ready for binary PDF storage.")
        
    except SQLAlchemyError as e:
        print(f"❌ Database error during migration: {str(e)}")
        db.rollback()
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error during migration: {str(e)}")
        db.rollback()
        return False
    
    finally:
        db.close()
    
    return True


def check_migration_status():
    """
    Check if the migration has already been applied
    """
    print("🔍 Checking current migration status...")
    
    db = next(get_db())
    
    try:
        # Check if new columns exist
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'student_pdfs' 
            AND column_name IN ('pdf_data', 'pdf_size', 'content_hash', 'mime_type')
        """))
        
        existing_columns = [row.column_name for row in result]
        required_columns = ['pdf_data', 'pdf_size', 'content_hash', 'mime_type']
        
        print(f"📋 Required columns: {', '.join(required_columns)}")
        print(f"✅ Existing columns: {', '.join(existing_columns)}")
        
        missing_columns = set(required_columns) - set(existing_columns)
        
        if missing_columns:
            print(f"⚠️  Missing columns: {', '.join(missing_columns)}")
            return False
        else:
            print("✅ All required columns exist!")
            return True
    
    except Exception as e:
        print(f"❌ Error checking migration status: {str(e)}")
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    print("🛠️  Student PDFs Table Migration")
    print("=" * 50)
    
    # Check current status
    if check_migration_status():
        print("\n💡 Migration appears to already be applied.")
        print("   Use --force to run anyway, or --status to check details.")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--force":
            print("\n🔄 Running migration anyway (--force)...")
            run_migration()
        elif len(sys.argv) > 1 and sys.argv[1] == "--status":
            # Just show status, already done above
            pass
        else:
            print(f"\n✅ No action needed. Migration is complete.")
    else:
        print("\n🚀 Running migration...")
        if run_migration():
            print("\n✅ Migration completed successfully!")
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
