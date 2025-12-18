"""
Quick Start Script for BrainInk Backend
This script helps set up the initial admin user and test the system
"""
import requests
import json
from getpass import getpass

BASE_URL = "http://localhost:8000"  # Update this to your API URL

def register_admin():
    """Register the initial admin user"""
    print("=== Registering Initial Admin User ===")
    
    username = input("Enter admin username: ")
    email = input("Enter admin email: ")
    password = getpass("Enter admin password: ")
    fname = input("Enter first name: ")
    lname = input("Enter last name: ")
    
    data = {
        "username": username,
        "email": email,
        "password": password,
        "fname": fname,
        "lname": lname
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=data)
        if response.status_code == 201:
            print("✅ Admin user registered successfully!")
            return response.json()
        else:
            print(f"❌ Registration failed: {response.json()}")
            return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def login_admin(username):
    """Login as admin"""
    print(f"=== Logging in as {username} ===")
    
    password = getpass("Enter password: ")
    
    data = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=data)
        if response.status_code == 200:
            print("✅ Login successful!")
            token_data = response.json()
            return token_data["access_token"]
        else:
            print(f"❌ Login failed: {response.json()}")
            return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def check_roles(token):
    """Check available roles"""
    print("=== Checking Available Roles ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/study-area/roles/all", headers=headers)
        if response.status_code == 200:
            roles = response.json()
            print("✅ Available roles:")
            for role in roles:
                print(f"  - {role['name']} ({role['description']})")
            return True
        else:
            print(f"❌ Failed to get roles: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_system():
    """Test basic system functionality"""
    print("=== BrainInk Backend Quick Start ===\n")
    
    # Test server connection
    print("1. Testing server connection...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Server is running!")
            print(f"   Status: {response.json()}")
        else:
            print("❌ Server not responding properly")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {str(e)}")
        print("Make sure your FastAPI server is running!")
        return
    
    # Register admin if needed
    print("\n2. Admin user setup...")
    choice = input("Do you need to register an admin user? (y/n): ")
    
    if choice.lower() == 'y':
        admin_data = register_admin()
        if not admin_data:
            return
        username = admin_data.get("username")
    else:
        username = input("Enter existing admin username: ")
    
    # Login
    print("\n3. Admin login...")
    token = login_admin(username)
    if not token:
        return
    
    # Check roles
    print("\n4. System check...")
    if check_roles(token):
        print("\n✅ System is ready!")
        print("\nNext steps:")
        print("1. Assign 'principal' role to users who will create schools")
        print("2. Principals can create school requests")
        print("3. You (admin) can approve school requests")
        print("4. Principals can generate access codes")
        print("5. Students/teachers can join schools with access codes")
        print("\nRefer to DEPLOYMENT_GUIDE.md for complete workflow!")
    else:
        print("\n❌ System check failed. Check your database and role initialization.")

if __name__ == "__main__":
    test_system()
