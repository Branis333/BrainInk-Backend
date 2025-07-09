"""
Test script for the new direct school joining system
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
# You'll need to replace these with actual tokens
USER_TOKEN = "your_user_jwt_token_here"  # Regular user token
ADMIN_TOKEN = "your_admin_jwt_token_here"  # Admin token

# Headers
user_headers = {
    "Authorization": f"Bearer {USER_TOKEN}",
    "Content-Type": "application/json"
}

admin_headers = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

def test_get_available_schools():
    """Test getting list of available schools"""
    print("=== Testing Get Available Schools ===")
    
    response = requests.get(
        f"{BASE_URL}/study-area/schools/available",
        headers=user_headers
    )
    
    if response.status_code == 200:
        schools = response.json()
        print(f"✅ Found {len(schools)} available schools:")
        for school in schools:
            print(f"   - {school['name']} (ID: {school['id']}) - Principal: {school['principal_name']}")
            print(f"     Students: {school['total_students']}, Teachers: {school['total_teachers']}")
        return schools
    else:
        print(f"❌ Failed to get schools: {response.text}")
        return []

def test_request_teacher_join(school_id, email):
    """Test requesting to join as teacher"""
    print("=== Testing Teacher Join Request ===")
    
    join_data = {
        "school_id": school_id,
        "email": email
    }
    
    response = requests.post(
        f"{BASE_URL}/study-area/join-school/request-teacher",
        headers=user_headers,
        json=join_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Teacher join: {result['message']}")
        print(f"   Status: {result['status']}")
        print(f"   Note: {result['note']}")
        return result
    else:
        print(f"❌ Teacher join failed: {response.text}")
        return None

def test_request_principal_join(school_id, email):
    """Test requesting to join as principal"""
    print("=== Testing Principal Join Request ===")
    
    join_data = {
        "school_id": school_id,
        "email": email
    }
    
    response = requests.post(
        f"{BASE_URL}/study-area/join-school/request-principal",
        headers=user_headers,
        json=join_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Principal request: {result['message']}")
        print(f"   Status: {result['status']}")
        print(f"   Request ID: {result['request_id']}")
        print(f"   Note: {result['note']}")
        return result
    else:
        print(f"❌ Principal request failed: {response.text}")
        return None

def test_get_pending_principal_requests():
    """Test getting pending principal requests (admin only)"""
    print("=== Testing Get Pending Principal Requests (Admin) ===")
    
    response = requests.get(
        f"{BASE_URL}/study-area/school-requests/principal-pending",
        headers=admin_headers
    )
    
    if response.status_code == 200:
        requests_list = response.json()
        print(f"✅ Found {len(requests_list)} pending principal requests:")
        for req in requests_list:
            print(f"   - {req['user_name']} ({req['user_email']}) → {req['school_name']}")
            print(f"     Request ID: {req['id']}, Date: {req['request_date']}")
        return requests_list
    else:
        print(f"❌ Failed to get pending requests: {response.text}")
        return []

def test_approve_principal_request(request_id):
    """Test approving a principal request (admin only)"""
    print("=== Testing Approve Principal Request (Admin) ===")
    
    response = requests.put(
        f"{BASE_URL}/study-area/school-requests/{request_id}/approve-principal",
        headers=admin_headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Principal approved: {result['message']}")
        print(f"   School: {result['school_name']}")
        print(f"   Principal: {result['principal_name']}")
        return result
    else:
        print(f"❌ Principal approval failed: {response.text}")
        return None

def test_user_status():
    """Test getting user status with new available actions"""
    print("=== Testing User Status with New Actions ===")
    
    response = requests.get(
        f"{BASE_URL}/study-area/user/status",
        headers=user_headers
    )
    
    if response.status_code == 200:
        status = response.json()
        print(f"✅ User: {status['user_info']['full_name']}")
        print(f"   Roles: {status['user_info']['roles']}")
        print("   Available Actions:")
        for action in status['available_actions']:
            print(f"   - {action['action']}: {action['description']}")
        return status
    else:
        print(f"❌ Failed to get user status: {response.text}")
        return None

def run_full_test():
    """Run complete test workflow"""
    print("🧪 Testing New Direct School Joining System")
    print("⚠️  Make sure to update the tokens and email before running!")
    
    # Replace with actual test email
    test_email = "test@example.com"
    
    # 1. Get available schools
    schools = test_get_available_schools()
    if not schools:
        print("❌ No schools available for testing")
        return
    
    print("\n" + "="*50)
    
    # 2. Test user status
    test_user_status()
    
    print("\n" + "="*50)
    
    # 3. Test teacher join (should work if school has principal)
    school_with_principal = None
    school_without_principal = None
    
    for school in schools:
        if school['principal_name'] != "No Principal Assigned":
            school_with_principal = school
        else:
            school_without_principal = school
    
    if school_with_principal:
        print(f"\n🧪 Testing teacher join for school with principal: {school_with_principal['name']}")
        test_request_teacher_join(school_with_principal['id'], test_email)
    
    print("\n" + "="*50)
    
    # 4. Test principal join (should work if school has no principal)
    if school_without_principal:
        print(f"\n🧪 Testing principal join for school without principal: {school_without_principal['name']}")
        result = test_request_principal_join(school_without_principal['id'], test_email)
        
        if result and result.get('request_id'):
            print("\n" + "="*50)
            
            # 5. Test admin workflow
            print("\n🧪 Testing admin approval workflow...")
            pending_requests = test_get_pending_principal_requests()
            
            if pending_requests:
                # Approve the first pending request
                print(f"\n🧪 Approving request ID: {pending_requests[0]['id']}")
                test_approve_principal_request(pending_requests[0]['id'])
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    run_full_test()
