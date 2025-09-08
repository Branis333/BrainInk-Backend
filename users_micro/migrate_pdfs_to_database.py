#!/usr/bin/env python3
"""
Migration script to convert PDF files to database binary storage.
This script will read existing PDF files from the file system and store them in the database.
"""

import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

# Add the parent directory to the path to import our modules
sys.path.append(str(Path(__file__).parent))

from db.database import get_db
from models.study_area_models import StudentPDF


def calculate_file_hash(file_data: bytes) -> str:
    """Calculate MD5 hash of file data"""
    return hashlib.md5(file_data).hexdigest()


def migrate_pdf_files_to_database():
    """
    Migrate existing PDF files from file system to database binary storage
    """
    print("🔄 Starting PDF migration to database storage...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Find all StudentPDF records that have pdf_path but no pdf_data
        pdf_records = db.query(StudentPDF).filter(
            StudentPDF.pdf_path.isnot(None),
            StudentPDF.pdf_data.is_(None)
        ).all()
        
        if not pdf_records:
            print("✅ No PDF records found that need migration.")
            return
        
        print(f"📋 Found {len(pdf_records)} PDF records to migrate...")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for pdf_record in pdf_records:
            try:
                print(f"🔍 Processing: {pdf_record.pdf_filename}")
                
                # Try to find the PDF file
                pdf_path = Path(pdf_record.pdf_path)
                
                # If path is not absolute, try common locations
                if not pdf_path.is_absolute() or not pdf_path.exists():
                    possible_paths = [
                        Path(pdf_record.pdf_path),
                        Path("uploads/student_pdfs") / pdf_record.pdf_filename,
                        Path("/opt/render/project/src/uploads/student_pdfs") / pdf_record.pdf_filename,
                        Path.cwd() / "uploads" / "student_pdfs" / pdf_record.pdf_filename,
                    ]
                    
                    found_path = None
                    for p in possible_paths:
                        if p.exists():
                            found_path = p
                            break
                    
                    if not found_path:
                        print(f"⚠️  File not found: {pdf_record.pdf_filename} (skipping)")
                        skipped_count += 1
                        continue
                    
                    pdf_path = found_path
                
                # Read the PDF file
                with open(pdf_path, 'rb') as f:
                    pdf_data = f.read()
                
                # Calculate hash and size
                content_hash = calculate_file_hash(pdf_data)
                pdf_size = len(pdf_data)
                
                # Update the database record
                pdf_record.pdf_data = pdf_data
                pdf_record.pdf_size = pdf_size
                pdf_record.content_hash = content_hash
                pdf_record.mime_type = "application/pdf"
                
                print(f"✅ Migrated: {pdf_record.pdf_filename} ({pdf_size} bytes, hash: {content_hash[:8]}...)")
                migrated_count += 1
                
            except Exception as e:
                print(f"❌ Error processing {pdf_record.pdf_filename}: {str(e)}")
                error_count += 1
                continue
        
        # Commit all changes
        if migrated_count > 0:
            db.commit()
            print(f"💾 Committed {migrated_count} PDF records to database")
        
        # Summary
        print(f"\n📊 Migration Summary:")
        print(f"   ✅ Migrated: {migrated_count}")
        print(f"   ⚠️  Skipped: {skipped_count}")
        print(f"   ❌ Errors: {error_count}")
        print(f"   📁 Total: {len(pdf_records)}")
        
        if migrated_count > 0:
            print(f"\n🎉 Migration completed successfully!")
            print(f"💡 You can now safely remove the old PDF files from the file system.")
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        db.rollback()
    
    finally:
        db.close()


def verify_migration():
    """
    Verify that the migration was successful
    """
    print("\n🔍 Verifying migration...")
    
    db = next(get_db())
    
    try:
        # Count records with database storage
        with_data = db.query(StudentPDF).filter(StudentPDF.pdf_data.isnot(None)).count()
        
        # Count records still using file paths
        with_paths_only = db.query(StudentPDF).filter(
            StudentPDF.pdf_path.isnot(None),
            StudentPDF.pdf_data.is_(None)
        ).count()
        
        total = db.query(StudentPDF).count()
        
        print(f"📊 Verification Results:")
        print(f"   📁 Total PDF records: {total}")
        print(f"   💾 Stored in database: {with_data}")
        print(f"   📂 Still using file paths: {with_paths_only}")
        
        if with_paths_only == 0:
            print("✅ All PDF records are now using database storage!")
        else:
            print(f"⚠️  {with_paths_only} records still need migration")
    
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 PDF Migration Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    else:
        migrate_pdf_files_to_database()
        verify_migration()
