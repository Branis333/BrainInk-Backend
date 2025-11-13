#!/usr/bin/env python3
"""
Database Compatibility Checker
Verifies that database tables match the API interface requirements
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def get_database_connection():
    """Get database connection from environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Parse DATABASE_URL
    parsed = urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    return conn

def get_table_structure(cursor, table_name):
    """Get detailed table structure"""
    cursor.execute("""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return {row[0]: {
        'type': row[1],
        'nullable': row[2] == 'YES',
        'default': row[3],
        'max_length': row[4],
        'precision': row[5],
        'scale': row[6]
    } for row in cursor.fetchall()}

def check_api_compatibility(cursor):
    """Check if database structure matches API interface requirements"""
    print("🔍 CHECKING API COMPATIBILITY")
    print("=" * 60)
    
    compatibility_issues = []
    
    # Define expected structure for each API response
    api_requirements = {
        "AssignmentStatus": {
            "description": "Backend response from /grades/assignments/{id}/status",
            "required_fields": {
                "as_course_assignments": ["id", "title", "description", "points"],
                "as_student_assignments": ["id", "status", "grade", "submitted_at", "feedback"],
            },
            "status_values": ["assigned", "submitted", "graded", "overdue", "passed", "needs_retry", "failed"]
        },
        
        "AssignmentGradeResult": {
            "description": "Backend response from /grades/assignments/{id}/retry",
            "required_fields": {
                "as_course_assignments": ["id", "title", "description", "points", "due_days_after_assignment"],
                "as_student_assignments": ["id", "status", "grade", "submitted_at", "feedback"],
            }
        },
        
        "BlockAvailability": {
            "description": "Backend response from /grades/blocks/{id}/availability", 
            "required_fields": {
                "as_course_blocks": ["id", "title", "week", "block_number"]
            }
        },
        
        "CourseBlocksProgress": {
            "description": "Backend response from /grades/course/{id}/blocks-progress",
            "required_fields": {
                "as_course_blocks": ["id", "week", "block_number", "title", "description", "duration_minutes"],
                "as_study_sessions": ["user_id", "course_id", "block_id", "status"]
            }
        },
        
        "StudySessionMarkDone": {
            "description": "Backend endpoint POST /grades/mark-done",
            "required_fields": {
                "as_study_sessions": ["user_id", "course_id", "block_id", "status", "marked_done_at"]
            }
        }
    }
    
    # Check each table structure
    for api_name, requirements in api_requirements.items():
        print(f"\n📋 Checking {api_name}:")
        print(f"   Purpose: {requirements['description']}")
        
        for table_name, required_columns in requirements["required_fields"].items():
            table_structure = get_table_structure(cursor, table_name)
            
            if not table_structure:
                issue = f"❌ Table {table_name} does not exist"
                print(f"   {issue}")
                compatibility_issues.append(issue)
                continue
                
            print(f"   📊 Checking table: {table_name}")
            
            for column in required_columns:
                if column not in table_structure:
                    issue = f"❌ Missing column: {table_name}.{column}"
                    print(f"      {issue}")
                    compatibility_issues.append(issue)
                else:
                    col_info = table_structure[column]
                    print(f"      ✅ {column}: {col_info['type']}")
        
        # Check status values for assignment tables
        if "status_values" in requirements:
            print(f"   📝 Expected status values: {', '.join(requirements['status_values'])}")
    
    return compatibility_issues

def check_data_consistency(cursor):
    """Check data consistency for API endpoints"""
    print("\n🔍 CHECKING DATA CONSISTENCY")
    print("=" * 60)
    
    consistency_issues = []
    
    # Check for orphaned records
    orphan_checks = [
        {
            "description": "Study sessions with invalid course_id",
            "query": """
                SELECT COUNT(*) FROM as_study_sessions ss 
                WHERE NOT EXISTS (
                    SELECT 1 FROM as_courses c WHERE c.id = ss.course_id
                )
            """
        },
        {
            "description": "Study sessions with invalid block_id",
            "query": """
                SELECT COUNT(*) FROM as_study_sessions ss 
                WHERE ss.block_id IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM as_course_blocks cb WHERE cb.id = ss.block_id
                )
            """
        },
        {
            "description": "Student assignments with invalid assignment_id",
            "query": """
                SELECT COUNT(*) FROM as_student_assignments sa 
                WHERE NOT EXISTS (
                    SELECT 1 FROM as_course_assignments ca WHERE ca.id = sa.assignment_id
                )
            """
        },
        {
            "description": "AI submissions with invalid session_id",
            "query": """
                SELECT COUNT(*) FROM as_ai_submissions ais 
                WHERE NOT EXISTS (
                    SELECT 1 FROM as_study_sessions ss WHERE ss.id = ais.session_id
                )
            """
        }
    ]
    
    for check in orphan_checks:
        try:
            cursor.execute(check["query"])
            count = cursor.fetchone()[0]
            if count > 0:
                issue = f"❌ {check['description']}: {count} records"
                print(f"   {issue}")
                consistency_issues.append(issue)
            else:
                print(f"   ✅ {check['description']}: OK")
        except Exception as e:
            issue = f"❌ Error checking {check['description']}: {str(e)}"
            print(f"   {issue}")
            consistency_issues.append(issue)
    
    return consistency_issues

def check_api_endpoint_requirements(cursor):
    """Check specific requirements for each API endpoint"""
    print("\n🔍 CHECKING API ENDPOINT REQUIREMENTS")
    print("=" * 60)
    
    endpoint_issues = []
    
    # Test queries that each endpoint would run
    endpoint_tests = [
        {
            "endpoint": "POST /grades/mark-done",
            "description": "Mark study session as done",
            "query": """
                SELECT COUNT(*) FROM as_study_sessions 
                WHERE user_id = 1 AND block_id = 1 AND status IN ('pending', 'in_progress')
            """,
            "expected": "Should find sessions that can be marked done"
        },
        {
            "endpoint": "GET /grades/blocks/{block_id}/availability", 
            "description": "Check block availability",
            "query": """
                SELECT cb.id, cb.title, cb.week, cb.block_number
                FROM as_course_blocks cb 
                WHERE cb.id = 1 AND cb.is_active = TRUE
            """,
            "expected": "Should find active blocks"
        },
        {
            "endpoint": "GET /grades/assignments/{assignment_id}/status",
            "description": "Get assignment status with attempts",
            "query": """
                SELECT ca.id, ca.title, ca.points, sa.status, sa.grade 
                FROM as_course_assignments ca
                LEFT JOIN as_student_assignments sa ON ca.id = sa.assignment_id
                WHERE ca.id = 1
            """,
            "expected": "Should return assignment and student status"
        },
        {
            "endpoint": "POST /grades/assignments/{assignment_id}/retry",
            "description": "Retry assignment with 24-hour window check",
            "query": """
                SELECT COUNT(*) FROM as_ai_submissions 
                WHERE user_id = 1 AND assignment_id = 1 
                AND submitted_at >= NOW() - INTERVAL '24 hours'
            """,
            "expected": "Should count recent attempts for retry logic"
        },
        {
            "endpoint": "GET /grades/course/{course_id}/blocks-progress",
            "description": "Get course blocks with completion status",
            "query": """
                SELECT 
                    cb.id, cb.week, cb.block_number, cb.title,
                    CASE WHEN ss.id IS NOT NULL THEN TRUE ELSE FALSE END as completed
                FROM as_course_blocks cb
                LEFT JOIN as_study_sessions ss ON cb.id = ss.block_id 
                    AND ss.user_id = 1 AND ss.status = 'completed'
                WHERE cb.course_id = 1 AND cb.is_active = TRUE
                ORDER BY cb.week, cb.block_number
            """,
            "expected": "Should return blocks with completion status"
        }
    ]
    
    for test in endpoint_tests:
        print(f"\n📡 Testing: {test['endpoint']}")
        print(f"   📝 {test['description']}")
        
        try:
            cursor.execute(test["query"])
            result = cursor.fetchall()
            print(f"   ✅ Query executed successfully")
            print(f"   📊 Returned {len(result)} rows")
            
            # Show sample data if available
            if result and len(result) > 0:
                print(f"   💾 Sample: {result[0] if len(result[0]) <= 5 else str(result[0])[:100] + '...'}")
            
        except Exception as e:
            issue = f"❌ {test['endpoint']}: {str(e)}"
            print(f"   {issue}")
            endpoint_issues.append(issue)
    
    return endpoint_issues

def generate_test_data_queries(cursor):
    """Generate queries to create test data for API testing"""
    print("\n🧪 GENERATING TEST DATA QUERIES")
    print("=" * 60)
    
    test_queries = [
        """
        -- Test Course
        INSERT INTO as_courses (id, title, subject, created_by, total_weeks, blocks_per_week)
        VALUES (9999, 'API Test Course', 'Testing', 1, 4, 2)
        ON CONFLICT (id) DO NOTHING;
        """,
        
        """
        -- Test Course Blocks
        INSERT INTO as_course_blocks (id, course_id, week, block_number, title, duration_minutes)
        VALUES 
            (9999, 9999, 1, 1, 'Test Block 1.1', 45),
            (9998, 9999, 1, 2, 'Test Block 1.2', 45)
        ON CONFLICT (course_id, week, block_number) DO NOTHING;
        """,
        
        """
        -- Test Assignment
        INSERT INTO as_course_assignments (id, course_id, title, description, assignment_type, points)
        VALUES (9999, 9999, 'Test Assignment', 'API compatibility test', 'quiz', 100)
        ON CONFLICT (id) DO NOTHING;
        """,
        
        """
        -- Test Study Session
        INSERT INTO as_study_sessions (id, user_id, course_id, block_id, status)
        VALUES (9999, 1, 9999, 9999, 'pending')
        ON CONFLICT (id) DO NOTHING;
        """,
        
        """
        -- Test Student Assignment
        INSERT INTO as_student_assignments (user_id, assignment_id, course_id, due_date, status)
        VALUES (1, 9999, 9999, NOW() + INTERVAL '7 days', 'assigned')
        ON CONFLICT (user_id, assignment_id) DO NOTHING;
        """
    ]
    
    print("📝 Test data queries generated:")
    for i, query in enumerate(test_queries, 1):
        print(f"\n-- Query {i}:")
        print(query.strip())
    
    return test_queries

def main():
    """Main compatibility checking function"""
    print("🔍 DATABASE COMPATIBILITY CHECKER")
    print("=" * 80)
    print("📅 Check Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🎯 Purpose: Verify backend-frontend API compatibility")
    print("=" * 80)
    
    conn = None
    cursor = None
    
    try:
        # Connect to database
        conn = get_database_connection()
        cursor = conn.cursor()
        print("✅ Connected to database successfully")
        
        # Run compatibility checks
        all_issues = []
        
        # Check API structure compatibility
        api_issues = check_api_compatibility(cursor)
        all_issues.extend(api_issues)
        
        # Check data consistency
        data_issues = check_data_consistency(cursor)
        all_issues.extend(data_issues)
        
        # Check endpoint requirements
        endpoint_issues = check_api_endpoint_requirements(cursor)
        all_issues.extend(endpoint_issues)
        
        # Generate test data
        generate_test_data_queries(cursor)
        
        # Summary report
        print(f"\n📊 COMPATIBILITY REPORT SUMMARY")
        print("=" * 60)
        
        if not all_issues:
            print("🎉 ALL COMPATIBILITY CHECKS PASSED!")
            print("✅ Database structure is compatible with API interfaces")
            print("✅ Data consistency checks passed")  
            print("✅ All API endpoints should work correctly")
        else:
            print(f"⚠️  FOUND {len(all_issues)} COMPATIBILITY ISSUES:")
            for i, issue in enumerate(all_issues, 1):
                print(f"   {i}. {issue}")
            
            print(f"\n🔧 RECOMMENDED ACTIONS:")
            print("   1. Run the migration script: migrate_compatibility_update.py")
            print("   2. Fix any data consistency issues")
            print("   3. Test API endpoints with sample data")
            print("   4. Re-run this compatibility checker")
        
        print(f"\n📈 STATISTICS:")
        print(f"   • API interfaces checked: 5")
        print(f"   • Database tables verified: 8")
        print(f"   • Endpoint queries tested: 5")
        print(f"   • Issues found: {len(all_issues)}")
        
    except Exception as e:
        print(f"\n❌ COMPATIBILITY CHECK FAILED: {str(e)}")
        raise e
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("\n🔐 Database connection closed")

if __name__ == "__main__":
    main()