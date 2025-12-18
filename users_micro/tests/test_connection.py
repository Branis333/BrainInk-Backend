import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    DATABASE_URL = os.getenv("DATABASE_URL")
    print(f"Attempting to connect to: {DATABASE_URL}")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"Connected successfully! PostgreSQL version: {version[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Connection failed: {e}")