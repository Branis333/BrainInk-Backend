"""
Test script for the subjects management system
Run this after applying the database migration
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust your server URL
PRINCIPAL_TOKEN = "your_principal_jwt_token_here"
TEACHER_TOKEN = "your_teacher_jwt_token_here"
STUDENT_TOKEN = "your_student_jwt_token_here"

# Headers
principal_headers = {
    "Authorization": f"Bearer {PRINCIPAL_TOKEN}",
    "Content-Type": "application/json"
}

teacher_headers = {
    "Authorization": f"Bearer {TEACHER_TOKEN}",
    "Content-Type": "application/json"
}

student_headers = {
    "Authorization": f"Bearer {STUDENT_TOKEN}",
    "Content-Type": "application/json"
}

def test_subject_creation():
    """Test creating subjects as principal"""
    print("=== Testing Subject Creation (Principal) ===")
    
    subjects_to_create = [
        {"name": "Mathematics", "description": "Advanced mathematics course", "school_id": 1},
        {"name": "Physics", "description": "Physics fundamentals", "school_id": 1},
        {"name": "Chemistry", "description": "Basic chemistry", "school_id": 1},
        {"name": "English Literature", "description": "English literature and writing", "school_id": 1}
    ]
    
    created_subjects = []
    
    for subject_data in subjects_to_create:
        response = requests.post(
            f"{BASE_URL}/subjects/create",
            headers=principal_headers,
            json=subject_data
        )
        
        if response.status_code == 200:
            subject = response.json()
            created_subjects.append(subject)
            print(f"✅ Subject created: {subject['name']} (ID: {subject['id']})")
        else:
            print(f"❌ Subject creation failed for {subject_data['name']}: {response.text}")
    
    return created_subjects

def test_get_school_subjects():
    """Test getting school subjects as principal"""
    print("\n=== Testing Get School Subjects (Principal) ===")
    
    response = requests.get(
        f"{BASE_URL}/subjects/my-school",
        headers=principal_headers
    )
    
    if response.status_code == 200:
        subjects = response.json()
        print(f"✅ Found {len(subjects)} subjects in school")
        for subject in subjects:
            print(f"   - {subject['name']}: {subject['teacher_count']} teachers, {subject['student_count']} students")
        return subjects
    else:
        print(f"❌ Getting school subjects failed: {response.text}")
        return []

def test_teacher_assignment():
    """Test assigning teachers to subjects"""
    print("\n=== Testing Teacher Assignment (Principal) ===")
    
    # You'll need to replace these with actual subject and teacher IDs
    assignments = [
        {"subject_id": 1, "teacher_id": 1},  # Math teacher
        {"subject_id": 2, "teacher_id": 2},  # Physics teacher
        {"subject_id": 1, "teacher_id": 2},  # Physics teacher also teaches math
    ]
    
    for assignment in assignments:
        response = requests.post(
            f"{BASE_URL}/subjects/assign-teacher",
            headers=principal_headers,
            json=assignment
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Teacher assignment successful: {result['message']}")
        else:
            print(f"❌ Teacher assignment failed: {response.text}")

def test_get_teacher_subjects():
    """Test getting subjects assigned to teacher"""
    print("\n=== Testing Get Teacher Subjects (Teacher) ===")
    
    response = requests.get(
        f"{BASE_URL}/teachers/my-subjects",
        headers=teacher_headers
    )
    
    if response.status_code == 200:
        subjects = response.json()
        print(f"✅ Teacher is assigned to {len(subjects)} subjects")
        for subject in subjects:
            print(f"   - {subject['name']}: {subject['student_count']} students")
        return subjects
    else:
        print(f"❌ Getting teacher subjects failed: {response.text}")
        return []

def test_student_enrollment():
    """Test adding students to subjects as teacher"""
    print("\n=== Testing Student Enrollment (Teacher) ===")
    
    # You'll need to replace these with actual subject and student IDs
    enrollments = [
        {"subject_id": 1, "student_id": 1},  # Student 1 in Math
        {"subject_id": 1, "student_id": 2},  # Student 2 in Math
        {"subject_id": 2, "student_id": 1},  # Student 1 in Physics
    ]
    
    for enrollment in enrollments:
        response = requests.post(
            f"{BASE_URL}/subjects/add-student",
            headers=teacher_headers,
            json=enrollment
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Student enrollment successful: {result['message']}")
        else:
            print(f"❌ Student enrollment failed: {response.text}")

def test_subject_details():
    """Test getting detailed subject information"""
    print("\n=== Testing Subject Details ===")
    
    subject_id = 1  # Replace with actual subject ID
    
    # Test as principal
    response = requests.get(
        f"{BASE_URL}/subjects/{subject_id}",
        headers=principal_headers
    )
    
    if response.status_code == 200:
        subject = response.json()
        print(f"✅ Subject details (Principal): {subject['name']}")
        print(f"   Teachers: {len(subject['teachers'])}")
        print(f"   Students: {len(subject['students'])}")
    else:
        print(f"❌ Getting subject details (Principal) failed: {response.text}")
    
    # Test as teacher
    response = requests.get(
        f"{BASE_URL}/subjects/{subject_id}",
        headers=teacher_headers
    )
    
    if response.status_code == 200:
        subject = response.json()
        print(f"✅ Subject details (Teacher): {subject['name']}")
    elif response.status_code == 403:
        print("✅ Teacher access properly restricted (not assigned to this subject)")
    else:
        print(f"❌ Getting subject details (Teacher) failed: {response.text}")

def test_get_student_subjects():
    """Test getting subjects for student"""
    print("\n=== Testing Get Student Subjects (Student) ===")
    
    response = requests.get(
        f"{BASE_URL}/students/my-subjects",
        headers=student_headers
    )
    
    if response.status_code == 200:
        subjects = response.json()
        print(f"✅ Student is enrolled in {len(subjects)} subjects")
        for subject in subjects:
            print(f"   - {subject['name']}")
    else:
        print(f"❌ Getting student subjects failed: {response.text}")

def test_permission_restrictions():
    """Test that permission restrictions work properly"""
    print("\n=== Testing Permission Restrictions ===")
    
    # Test teacher trying to create subject (should fail)
    subject_data = {"name": "Unauthorized Subject", "school_id": 1}
    response = requests.post(
        f"{BASE_URL}/subjects/create",
        headers=teacher_headers,
        json=subject_data
    )
    
    if response.status_code == 403:
        print("✅ Teacher properly restricted from creating subjects")
    else:
        print(f"❌ Teacher restriction failed: {response.status_code}")
    
    # Test student trying to add student to subject (should fail)
    enrollment_data = {"subject_id": 1, "student_id": 2}
    response = requests.post(
        f"{BASE_URL}/subjects/add-student",
        headers=student_headers,
        json=enrollment_data
    )
    
    if response.status_code == 403:
        print("✅ Student properly restricted from managing enrollments")
    else:
        print(f"❌ Student restriction failed: {response.status_code}")

if __name__ == "__main__":
    print("🧪 Testing Subjects Management System")
    print("⚠️  Make sure to update the tokens and IDs before running!")
    
    # Uncomment the tests you want to run:
    # created_subjects = test_subject_creation()
    # school_subjects = test_get_school_subjects()
    # test_teacher_assignment()
    # teacher_subjects = test_get_teacher_subjects()
    # test_student_enrollment()
    # test_subject_details()
    # test_get_student_subjects()
    # test_permission_restrictions()
    
    print("\n✅ All tests completed!")
    print("\n📝 Remember to:")
    print("   1. Run the migration script: migrate_subjects.sql")
    print("   2. Update token values and IDs in the test script")
    print("   3. Ensure you have test users with proper roles")
    print("   4. Check that teachers and students belong to the same school")
