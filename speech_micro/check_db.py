#!/usr/bin/env python3

import sqlite3
import os

# Find database files
db_files = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.db') or file.endswith('.sqlite'):
            db_files.append(os.path.join(root, file))

print('Found database files:', db_files)

# Try to connect to the most likely database
db_path = None
if 'brain_ink.db' in str(db_files):
    db_path = next((f for f in db_files if 'brain_ink.db' in f), None)
elif db_files:
    db_path = db_files[0]

if db_path:
    print(f'Connecting to: {db_path}')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print('Tables:', [t[0] for t in tables])
    
    # Check transcription sessions
    if any('session' in t[0].lower() for t in tables):
        session_tables = [t[0] for t in tables if 'session' in t[0].lower()]
        for session_table in session_tables:
            print(f'\nChecking {session_table}:')
            cursor.execute(f'SELECT * FROM {session_table} LIMIT 5')
            rows = cursor.fetchall()
            if rows:
                for i, row in enumerate(rows):
                    print(f'  Row {i+1}: {row}')
            else:
                print('  No data found')
    
    # Check transcription data tables
    if any('transcription' in t[0].lower() for t in tables):
        transcription_tables = [t[0] for t in tables if 'transcription' in t[0].lower() and 'session' not in t[0].lower()]
        for transcription_table in transcription_tables:
            print(f'\nChecking {transcription_table}:')
            cursor.execute(f'SELECT * FROM {transcription_table} LIMIT 5')
            rows = cursor.fetchall()
            if rows:
                for i, row in enumerate(rows):
                    print(f'  Row {i+1}: {row}')
            else:
                print('  No data found')
    
    conn.close()
else:
    print('No database file found')
