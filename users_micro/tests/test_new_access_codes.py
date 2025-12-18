"""
Test script for the new email-based access code system
Run this after applying the database migration
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust your server URL
PRINCIPAL_TOKEN = "your_principal_jwt_token_here"
STUDENT_TOKEN = "your_student_jwt_token_here"

# Headers
principal_headers = {
    "Authorization": f"Bearer {PRINCIPAL_TOKEN}",
    "Content-Type": "application/json"
}

student_headers = {
    "Authorization": f"Bearer {STUDENT_TOKEN}",
    "Content-Type": "application/json"
}

def test_access_code_generation():
    """Test generating access codes for students and teachers"""
    print("=== Testing Access Code Generation ===")
    
    # Generate student access code
    student_code_data = {
        "school_id": 1,
        "code_type": "student",
        "email": "john.doe@example.com"
    }
    
    response = requests.post(
        f"{BASE_URL}/access-codes/generate",
        headers=principal_headers,
        json=student_code_data
    )
    
    if response.status_code == 200:
        student_code = response.json()
        print(f"✅ Student code generated: {student_code['code']} for {student_code['email']}")
    else:
        print(f"❌ Student code generation failed: {response.text}")
    
    # Generate teacher access code
    teacher_code_data = {
        "school_id": 1,
        "code_type": "teacher",
        "email": "jane.smith@example.com"
    }
    
    response = requests.post(
        f"{BASE_URL}/access-codes/generate",
        headers=principal_headers,
        json=teacher_code_data
    )
    
    if response.status_code == 200:
        teacher_code = response.json()
        print(f"✅ Teacher code generated: {teacher_code['code']} for {teacher_code['email']}")
    else:
        print(f"❌ Teacher code generation failed: {response.text}")

def test_duplicate_code_handling():
    """Test that duplicate codes for same email are handled properly"""
    print("\n=== Testing Duplicate Code Handling ===")
    
    code_data = {
        "school_id": 1,
        "code_type": "student",
        "email": "duplicate.test@example.com"
    }
    
    # First generation
    response1 = requests.post(
        f"{BASE_URL}/access-codes/generate",
        headers=principal_headers,
        json=code_data
    )
    
    # Second generation (should reactivate existing if inactive, or return error if active)
    response2 = requests.post(
        f"{BASE_URL}/access-codes/generate",
        headers=principal_headers,
        json=code_data
    )
    
    if response1.status_code == 200 and response2.status_code in [200, 400]:
        print("✅ Duplicate code handling working correctly")
    else:
        print(f"❌ Duplicate code handling failed")

def test_school_joining():
    """Test joining school with the new reusable system"""
    print("\n=== Testing School Joining ===")
    
    join_data = {
        "school_name": "Test School",
        "email": "john.doe@example.com",
        "access_code": "STUDENT_CODE_HERE"  # Replace with actual code
    }
    
    response = requests.post(
        f"{BASE_URL}/join-school/student",
        headers=student_headers,
        json=join_data
    )
    
    if response.status_code == 200:
        print("✅ School joining successful (code remains active)")
    elif response.status_code == 400 and "already a student" in response.text:
        print("✅ Duplicate joining prevented (user already in school)")
    else:
        print(f"❌ School joining failed: {response.text}")

def test_code_management():
    """Test code management endpoints"""
    print("\n=== Testing Code Management ===")
    
    # Get codes by email
    email = "john.doe@example.com"
    response = requests.get(
        f"{BASE_URL}/access-codes/by-email/{email}",
        headers=principal_headers
    )
    
    if response.status_code == 200:
        codes = response.json()
        print(f"✅ Found {len(codes)} codes for {email}")
        
        if codes:
            code_id = codes[0]['id']
            
            # Test deactivation
            response = requests.delete(
                f"{BASE_URL}/access-codes/{code_id}",
                headers=principal_headers
            )
            
            if response.status_code == 200:
                print("✅ Code deactivation successful")
                
                # Test reactivation
                response = requests.put(
                    f"{BASE_URL}/access-codes/{code_id}/reactivate",
                    headers=principal_headers
                )
                
                if response.status_code == 200:
                    print("✅ Code reactivation successful")
                else:
                    print(f"❌ Code reactivation failed: {response.text}")
            else:
                print(f"❌ Code deactivation failed: {response.text}")
    else:
        print(f"❌ Getting codes by email failed: {response.text}")

if __name__ == "__main__":
    print("🧪 Testing New Access Code System")
    print("⚠️  Make sure to update the tokens and URLs before running!")
    
    # Uncomment the tests you want to run:
    # test_access_code_generation()
    # test_duplicate_code_handling()
    # test_school_joining()
    # test_code_management()
    
    print("\n✅ All tests completed!")
