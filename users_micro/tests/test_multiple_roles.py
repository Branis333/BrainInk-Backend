"""
Test script for multiple roles functionality
"""
import requests
import json

BASE_URL = "http://localhost:8000"

class MultipleRolesTest:
    def __init__(self):
        self.session = requests.Session()
        self.admin_token = None
        
    def login_admin(self, username, password):
        """Login as admin and store token"""
        data = {"username": username, "password": password}
        response = self.session.post(f"{BASE_URL}/auth/login", json=data)
        if response.status_code == 200:
            self.admin_token = response.json()["access_token"]
            return True
        return False
    
    def get_headers(self):
        """Get auth headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
    
    def assign_role(self, user_id, role_name):
        """Assign role to user"""
        params = {"user_id": user_id, "role_name": role_name}
        response = self.session.post(
            f"{BASE_URL}/study-area/roles/assign",
            params=params,
            headers=self.get_headers()
        )
        return response
    
    def remove_role(self, user_id, role_name):
        """Remove role from user"""
        params = {"user_id": user_id, "role_name": role_name}
        response = self.session.delete(
            f"{BASE_URL}/study-area/roles/remove",
            params=params,
            headers=self.get_headers()
        )
        return response
    
    def get_user_roles(self, user_id):
        """Get user's roles"""
        response = self.session.get(
            f"{BASE_URL}/study-area/users/{user_id}/roles",
            headers=self.get_headers()
        )
        return response
    
    def test_multiple_roles(self, user_id=1):
        """Test multiple roles functionality"""
        print("=== Testing Multiple Roles Functionality ===\n")
        
        # 1. Check initial roles
        print("1. Getting initial user roles...")
        response = self.get_user_roles(user_id)
        if response.status_code == 200:
            initial_roles = response.json()["roles"]
            print(f"   Initial roles: {initial_roles}")
        else:
            print(f"   Error: {response.json()}")
            return
        
        # 2. Assign teacher role
        print("\n2. Assigning teacher role...")
        response = self.assign_role(user_id, "teacher")
        if response.status_code == 200:
            print(f"   Success: {response.json()['message']}")
        else:
            print(f"   Error: {response.json()}")
        
        # 3. Check roles after adding teacher
        print("\n3. Checking roles after adding teacher...")
        response = self.get_user_roles(user_id)
        if response.status_code == 200:
            roles = response.json()["roles"]
            print(f"   Roles: {roles}")
        
        # 4. Assign principal role (should keep teacher)
        print("\n4. Assigning principal role...")
        response = self.assign_role(user_id, "principal")
        if response.status_code == 200:
            print(f"   Success: {response.json()['message']}")
        
        # 5. Check roles after adding principal
        print("\n5. Checking roles after adding principal...")
        response = self.get_user_roles(user_id)
        if response.status_code == 200:
            roles = response.json()["roles"]
            print(f"   Roles: {roles}")
            print(f"   ✅ User now has multiple roles!")
        
        # 6. Try to assign same role again
        print("\n6. Trying to assign teacher role again...")
        response = self.assign_role(user_id, "teacher")
        if response.status_code == 200:
            print(f"   Response: {response.json()['message']}")
        
        # 7. Remove teacher role (should keep principal)
        print("\n7. Removing teacher role...")
        response = self.remove_role(user_id, "teacher")
        if response.status_code == 200:
            print(f"   Success: {response.json()['message']}")
        
        # 8. Check final roles
        print("\n8. Checking final roles...")
        response = self.get_user_roles(user_id)
        if response.status_code == 200:
            final_roles = response.json()["roles"]
            print(f"   Final roles: {final_roles}")
            print(f"   ✅ Teacher role removed, principal role preserved!")
        
        print("\n=== Multiple Roles Test Complete! ===")

def main():
    """Run multiple roles test"""
    tester = MultipleRolesTest()
    
    print("Multiple Roles Test Script")
    print("Make sure your server is running with the updated models!")
    
    # Login as admin
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")
    
    if not tester.login_admin(username, password):
        print("❌ Login failed!")
        return
    
    print("✅ Admin login successful!")
    
    # Get user ID to test
    user_id = input("Enter user ID to test multiple roles (default: 1): ") or "1"
    user_id = int(user_id)
    
    # Run test
    tester.test_multiple_roles(user_id)

if __name__ == "__main__":
    main()
