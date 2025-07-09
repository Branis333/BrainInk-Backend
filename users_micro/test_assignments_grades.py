"""
Test script for Assignments and Grades System
Tests assignment creation, grading, and grade retrieval functionality
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Test user credentials (you'll need to replace these with actual test users)
PRINCIPAL_TOKEN = ""  # Principal's JWT token
TEACHER_TOKEN = ""    # Teacher's JWT token  
STUDENT_TOKEN = ""    # Student's JWT token

def print_test_result(test_name, success, details=""):
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status} - {test_name}")
    if details:
        print(f"   Details: {details}")
    print()

def test_assignment_creation():
    """Test assignment creation by teacher"""
    print("=== Testing Assignment Creation ===")
    
    # Test data
    assignment_data = {
        "title": "Algebra Homework #1",
        "description": "Complete exercises 1-20 from chapter 3",
        "subtopic": "Linear Equations",
        "subject_id": 1,  # Replace with actual subject ID
        "max_points": 100,
        "due_date": (datetime.now() + timedelta(days=7)).isoformat()
    }
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/assignments/create",
            json=assignment_data,
            headers=headers
        )
        
        if response.status_code == 200:
            assignment = response.json()
            print_test_result(
                "Assignment Creation",
                True,
                f"Created assignment: {assignment['title']} (ID: {assignment['id']})"
            )
            return assignment['id']
        else:
            print_test_result(
                "Assignment Creation",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Assignment Creation", False, f"Exception: {str(e)}")
        return None

def test_get_teacher_assignments():
    """Test retrieving teacher's assignments"""
    print("=== Testing Get Teacher Assignments ===")
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/assignments/my-assignments",
            headers=headers
        )
        
        if response.status_code == 200:
            assignments = response.json()
            print_test_result(
                "Get Teacher Assignments",
                True,
                f"Retrieved {len(assignments)} assignments"
            )
            
            for assignment in assignments:
                print(f"   - {assignment['title']}: {assignment['graded_count']}/{assignment['total_students']} graded")
            
            return assignments
        else:
            print_test_result(
                "Get Teacher Assignments",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return []
            
    except Exception as e:
        print_test_result("Get Teacher Assignments", False, f"Exception: {str(e)}")
        return []

def test_subject_assignments(subject_id=1):
    """Test retrieving assignments for a subject"""
    print("=== Testing Get Subject Assignments ===")
    
    headers = {**HEADERS, "Authorization": f"Bearer {STUDENT_TOKEN}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/assignments/subject/{subject_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            assignments = response.json()
            print_test_result(
                "Get Subject Assignments",
                True,
                f"Retrieved {len(assignments)} assignments for subject {subject_id}"
            )
            return assignments
        else:
            print_test_result(
                "Get Subject Assignments",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return []
            
    except Exception as e:
        print_test_result("Get Subject Assignments", False, f"Exception: {str(e)}")
        return []

def test_grade_creation(assignment_id, student_id):
    """Test grade creation by teacher"""
    print("=== Testing Grade Creation ===")
    
    grade_data = {
        "assignment_id": assignment_id,
        "student_id": student_id,
        "points_earned": 85,
        "feedback": "Good work! Pay attention to showing your work on problem 15."
    }
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/grades/create",
            json=grade_data,
            headers=headers
        )
        
        if response.status_code == 200:
            grade = response.json()
            print_test_result(
                "Grade Creation",
                True,
                f"Created grade: {grade['points_earned']}/{grade['assignment_max_points']} ({grade['percentage']:.1f}%)"
            )
            return grade['id']
        else:
            print_test_result(
                "Grade Creation",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Grade Creation", False, f"Exception: {str(e)}")
        return None

def test_bulk_grade_creation(assignment_id):
    """Test bulk grade creation"""
    print("=== Testing Bulk Grade Creation ===")
    
    bulk_grade_data = {
        "assignment_id": assignment_id,
        "grades": [
            {"student_id": 1, "points_earned": 95, "feedback": "Excellent work!"},
            {"student_id": 2, "points_earned": 78, "feedback": "Good effort, review section 3.2"},
            {"student_id": 3, "points_earned": 92, "feedback": "Very good, minor error on #18"}
        ]
    }
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/grades/bulk-create",
            json=bulk_grade_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print_test_result(
                "Bulk Grade Creation",
                True,
                f"Processed: {result['total_processed']}, Successful: {result['total_successful']}, Failed: {result['total_failed']}"
            )
            
            if result['failed_grades']:
                print("   Failed grades:")
                for failed in result['failed_grades']:
                    print(f"     Student {failed['student_id']}: {failed['error']}")
            
            return result
        else:
            print_test_result(
                "Bulk Grade Creation",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Bulk Grade Creation", False, f"Exception: {str(e)}")
        return None

def test_get_student_grades(student_id, subject_id):
    """Test retrieving student grades for a subject"""
    print("=== Testing Get Student Grades ===")
    
    headers = {**HEADERS, "Authorization": f"Bearer {STUDENT_TOKEN}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/grades/student/{student_id}/subject/{subject_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            report = response.json()
            print_test_result(
                "Get Student Grades",
                True,
                f"Student: {report['student_name']}, Subject: {report['subject_name']}"
            )
            print(f"   Completed: {report['completed_assignments']}/{report['total_assignments']} assignments")
            if report['average_percentage']:
                print(f"   Average: {report['average_percentage']:.1f}%")
            
            return report
        else:
            print_test_result(
                "Get Student Grades",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Get Student Grades", False, f"Exception: {str(e)}")
        return None

def test_get_my_grades():
    """Test student retrieving their own grades"""
    print("=== Testing Get My Grades ===")
    
    headers = {**HEADERS, "Authorization": f"Bearer {STUDENT_TOKEN}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/grades/my-grades",
            headers=headers
        )
        
        if response.status_code == 200:
            reports = response.json()
            print_test_result(
                "Get My Grades",
                True,
                f"Retrieved grades for {len(reports)} subjects"
            )
            
            for report in reports:
                print(f"   {report['subject_name']}: {report['completed_assignments']}/{report['total_assignments']} assignments")
                if report['average_percentage']:
                    print(f"     Average: {report['average_percentage']:.1f}%")
            
            return reports
        else:
            print_test_result(
                "Get My Grades",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return []
            
    except Exception as e:
        print_test_result("Get My Grades", False, f"Exception: {str(e)}")
        return []

def test_subject_grades_summary(subject_id):
    """Test getting grades summary for a subject"""
    print("=== Testing Subject Grades Summary ===")
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/grades/subject/{subject_id}/summary",
            headers=headers
        )
        
        if response.status_code == 200:
            summary = response.json()
            print_test_result(
                "Subject Grades Summary",
                True,
                f"Subject: {summary['subject_name']}"
            )
            print(f"   Total Students: {summary['total_students']}")
            print(f"   Total Assignments: {summary['total_assignments']}")
            print(f"   Grades Given: {summary['grades_given']}")
            if summary['average_class_score']:
                print(f"   Class Average: {summary['average_class_score']:.1f}%")
            
            return summary
        else:
            print_test_result(
                "Subject Grades Summary",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Subject Grades Summary", False, f"Exception: {str(e)}")
        return None

def test_grade_update(grade_id):
    """Test updating a grade"""
    print("=== Testing Grade Update ===")
    
    update_data = {
        "points_earned": 88,
        "feedback": "Updated: Good work! Minor improvement on calculations."
    }
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.put(
            f"{BASE_URL}/grades/{grade_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            grade = response.json()
            print_test_result(
                "Grade Update",
                True,
                f"Updated grade: {grade['points_earned']}/{grade['assignment_max_points']} ({grade['percentage']:.1f}%)"
            )
            return grade
        else:
            print_test_result(
                "Grade Update",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Grade Update", False, f"Exception: {str(e)}")
        return None

def test_assignment_update(assignment_id):
    """Test updating an assignment"""
    print("=== Testing Assignment Update ===")
    
    update_data = {
        "description": "Updated: Complete exercises 1-25 from chapter 3 (added bonus problems)",
        "max_points": 110,
        "due_date": (datetime.now() + timedelta(days=10)).isoformat()
    }
    
    headers = {**HEADERS, "Authorization": f"Bearer {TEACHER_TOKEN}"}
    
    try:
        response = requests.put(
            f"{BASE_URL}/assignments/{assignment_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            assignment = response.json()
            print_test_result(
                "Assignment Update",
                True,
                f"Updated assignment: {assignment['title']} (Max points: {assignment['max_points']})"
            )
            return assignment
        else:
            print_test_result(
                "Assignment Update",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return None
            
    except Exception as e:
        print_test_result("Assignment Update", False, f"Exception: {str(e)}")
        return None

def run_all_tests():
    """Run all assignment and grade tests"""
    print("🚀 Starting Assignments and Grades System Tests")
    print("=" * 50)
    
    if not all([PRINCIPAL_TOKEN, TEACHER_TOKEN, STUDENT_TOKEN]):
        print("❌ ERROR: Please set authentication tokens before running tests")
        print("Set PRINCIPAL_TOKEN, TEACHER_TOKEN, and STUDENT_TOKEN variables")
        return
    
    # Test assignment creation
    assignment_id = test_assignment_creation()
    if not assignment_id:
        print("⚠️  Skipping subsequent tests due to assignment creation failure")
        return
    
    # Test retrieving assignments
    test_get_teacher_assignments()
    test_subject_assignments(subject_id=1)  # Replace with actual subject ID
    
    # Test grade creation
    grade_id = test_grade_creation(assignment_id, student_id=1)  # Replace with actual student ID
    test_bulk_grade_creation(assignment_id)
    
    # Test grade retrieval
    test_get_student_grades(student_id=1, subject_id=1)  # Replace with actual IDs
    test_get_my_grades()
    test_subject_grades_summary(subject_id=1)  # Replace with actual subject ID
    
    # Test updates
    if grade_id:
        test_grade_update(grade_id)
    test_assignment_update(assignment_id)
    
    print("✅ All tests completed!")
    print("\nNote: Replace placeholder IDs and tokens with actual values for your test environment")

if __name__ == "__main__":
    # Instructions for setting up test environment
    print("📋 Assignments and Grades System Test Suite")
    print("=" * 50)
    print("Before running tests, please:")
    print("1. Start your FastAPI server")
    print("2. Set up test users (principal, teacher, student)")
    print("3. Create a test school and subject")
    print("4. Update the tokens and IDs in this script")
    print("5. Run the tests")
    print()
    
    # Uncomment the line below after setting up tokens and IDs
    # run_all_tests()
