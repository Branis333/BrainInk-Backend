"""
Test script for BrainInk Study Area Management System
This script demonstrates the complete workflow
"""
import requests
import json
from datetime import datetime, timedelta

# Base URL for your API
BASE_URL = "http://localhost:8000"  # Update this to your actual API URL

class BrainInkTester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.tokens = {}
    
    def register_user(self, username, email, password, fname="", lname=""):
        """Register a new user"""
        data = {
            "username": username,
            "email": email,
            "password": password,
            "fname": fname,
            "lname": lname
        }
        response = self.session.post(f"{self.base_url}/auth/register", json=data)
        return response.json()
    
    def login_user(self, username, password):
        """Login user and store token"""
        data = {
            "username": username,
            "password": password
        }
        response = self.session.post(f"{self.base_url}/auth/login", json=data)
        if response.status_code == 200:
            token_data = response.json()
            self.tokens[username] = token_data["access_token"]
            return token_data
        return response.json()
    
    def get_auth_headers(self, username):
        """Get authentication headers for user"""
        return {"Authorization": f"Bearer {self.tokens[username]}"}
    
    def assign_role(self, admin_username, user_id, role_name):
        """Assign role to user (admin only)"""
        params = {
            "user_id": user_id,
            "role_name": role_name
        }
        response = self.session.post(
            f"{self.base_url}/study-area/roles/assign",
            params=params,
            headers=self.get_auth_headers(admin_username)
        )
        return response.json()
    
    def create_school_request(self, principal_username, school_name, school_address=""):
        """Create school request (principal only)"""
        data = {
            "school_name": school_name,
            "school_address": school_address
        }
        response = self.session.post(
            f"{self.base_url}/study-area/school-requests/create",
            json=data,
            headers=self.get_auth_headers(principal_username)
        )
        return response.json()
    
    def get_pending_requests(self, admin_username):
        """Get pending school requests (admin only)"""
        response = self.session.get(
            f"{self.base_url}/study-area/school-requests/pending",
            headers=self.get_auth_headers(admin_username)
        )
        return response.json()
    
    def review_school_request(self, admin_username, request_id, status, admin_notes=""):
        """Review school request (admin only)"""
        data = {
            "status": status,
            "admin_notes": admin_notes
        }
        response = self.session.put(
            f"{self.base_url}/study-area/school-requests/{request_id}/review",
            json=data,
            headers=self.get_auth_headers(admin_username)
        )
        return response.json()
    
    def generate_access_code(self, principal_username, code_type, school_id, max_usage=1):
        """Generate access code (principal only)"""
        data = {
            "code_type": code_type,
            "school_id": school_id,
            "max_usage": max_usage,
            "expires_date": (datetime.now() + timedelta(days=30)).isoformat()
        }
        response = self.session.post(
            f"{self.base_url}/study-area/access-codes/generate",
            json=data,
            headers=self.get_auth_headers(principal_username)
        )
        return response.json()
    
    def join_school_as_student(self, student_username, school_name, email, access_code):
        """Join school as student"""
        data = {
            "school_name": school_name,
            "email": email,
            "access_code": access_code
        }
        response = self.session.post(
            f"{self.base_url}/study-area/join-school/student",
            json=data,
            headers=self.get_auth_headers(student_username)
        )
        return response.json()
    
    def join_school_as_teacher(self, teacher_username, school_name, email, access_code):
        """Join school as teacher"""
        data = {
            "school_name": school_name,
            "email": email,
            "access_code": access_code
        }
        response = self.session.post(
            f"{self.base_url}/study-area/join-school/teacher",
            json=data,
            headers=self.get_auth_headers(teacher_username)
        )
        return response.json()
    
    def get_school_analytics(self, principal_username):
        """Get school analytics (principal only)"""
        response = self.session.get(
            f"{self.base_url}/study-area/analytics/school-overview",
            headers=self.get_auth_headers(principal_username)
        )
        return response.json()

def run_complete_test():
    """Run a complete test of the system workflow"""
    tester = BrainInkTester()
    
    print("=== BrainInk Study Area Management System Test ===\n")
    
    # 1. Register users
    print("1. Registering users...")
    admin_data = tester.register_user("admin_user", "admin@brainink.com", "admin123", "Admin", "User")
    principal_data = tester.register_user("principal_john", "john@example.com", "principal123", "John", "Doe")
    student_data = tester.register_user("student_alice", "alice@example.com", "student123", "Alice", "Smith")
    teacher_data = tester.register_user("teacher_bob", "bob@example.com", "teacher123", "Bob", "Johnson")
    
    # 2. Login users
    print("2. Logging in users...")
    tester.login_user("admin_user", "admin123")
    tester.login_user("principal_john", "principal123")
    tester.login_user("student_alice", "student123")
    tester.login_user("teacher_bob", "teacher123")
    
    # 3. Assign roles (assuming admin already has admin role)
    print("3. Assigning roles...")
    # Note: You'll need to manually assign admin role to the first admin user
    # or modify this script based on your user system
    
    # 4. Create school request
    print("4. Creating school request...")
    school_request = tester.create_school_request(
        "principal_john", 
        "Greenwood High School", 
        "123 Education Street"
    )
    print(f"School request created: {school_request}")
    
    # 5. Review and approve school request
    print("5. Reviewing school request...")
    pending_requests = tester.get_pending_requests("admin_user")
    if pending_requests:
        request_id = pending_requests[0]["id"]
        approval = tester.review_school_request(
            "admin_user", 
            request_id, 
            "approved", 
            "School verified and approved"
        )
        print(f"School request approved: {approval}")
    
    # 6. Generate access codes
    print("6. Generating access codes...")
    # Note: You'll need the school_id from the created school
    school_id = 1  # Update this based on actual school creation
    
    student_code = tester.generate_access_code("principal_john", "student", school_id, 50)
    teacher_code = tester.generate_access_code("principal_john", "teacher", school_id, 10)
    
    print(f"Student access code: {student_code}")
    print(f"Teacher access code: {teacher_code}")
    
    # 7. Join school
    print("7. Joining school...")
    if student_code.get("code"):
        student_join = tester.join_school_as_student(
            "student_alice",
            "Greenwood High School",
            "alice@example.com",
            student_code["code"]
        )
        print(f"Student joined: {student_join}")
    
    if teacher_code.get("code"):
        teacher_join = tester.join_school_as_teacher(
            "teacher_bob",
            "Greenwood High School", 
            "bob@example.com",
            teacher_code["code"]
        )
        print(f"Teacher joined: {teacher_join}")
    
    # 8. View analytics
    print("8. Viewing school analytics...")
    analytics = tester.get_school_analytics("principal_john")
    print(f"School analytics: {json.dumps(analytics, indent=2, default=str)}")
    
    print("\n=== Test completed! ===")

if __name__ == "__main__":
    print("BrainInk Study Area Test Script")
    print("Make sure your API server is running before executing this script.")
    print("Update the BASE_URL variable to match your API server.")
    
    choice = input("Run complete test? (y/n): ")
    if choice.lower() == 'y':
        try:
            run_complete_test()
        except Exception as e:
            print(f"Test failed with error: {str(e)}")
    else:
        print("Test skipped. You can use the BrainInkTester class for custom testing.")
