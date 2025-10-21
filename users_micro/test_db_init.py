#!/usr/bin/env python
"""Test database initialization"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing database connection...")
    from db.connection import initialize_database
    
    print("Initializing database...")
    initialize_database()
    
    print("✅ Database initialization completed successfully!")
except Exception as e:
    print(f"❌ Error during database initialization: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
