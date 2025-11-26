"""
Diagnostic script to check if assignment and grade endpoints are properly loaded
Run this script to verify that all endpoints are accessible
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Change this to your server URL

def check_swagger_endpoints():
    """Check if endpoints are visible in OpenAPI spec"""
    print("🔍 Checking OpenAPI specification...")
    
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            openapi_spec = response.json()
            paths = openapi_spec.get("paths", {})
            
            # Look for assignment endpoints
            assignment_endpoints = [path for path in paths.keys() if "/assignments/" in path]
            grade_endpoints = [path for path in paths.keys() if "/grades/" in path]
            
            print(f"✅ OpenAPI spec loaded successfully")
            print(f"📋 Found {len(assignment_endpoints)} assignment endpoints:")
            for endpoint in assignment_endpoints:
                print(f"   - {endpoint}")
            
            print(f"📊 Found {len(grade_endpoints)} grade endpoints:")
            for endpoint in grade_endpoints:
                print(f"   - {endpoint}")
            
            if not assignment_endpoints and not grade_endpoints:
                print("❌ No assignment or grade endpoints found in OpenAPI spec!")
                print("   This suggests the endpoints are not being loaded by FastAPI")
            
            return len(assignment_endpoints) > 0 or len(grade_endpoints) > 0
            
        else:
            print(f"❌ Failed to fetch OpenAPI spec: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking OpenAPI spec: {str(e)}")
        return False

def check_direct_endpoint_access():
    """Try to access assignment endpoints directly"""
    print("\n🎯 Testing direct endpoint access...")
    
    # Test endpoints that don't require authentication
    test_endpoints = [
        "/study-area/assignments/subject/1",  # This might return 403 but should not 404
        "/study-area/grades/my-grades",       # This should return 403 for unauthorized access
    ]
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            print(f"   {endpoint}: Status {response.status_code}")
            
            if response.status_code == 404:
                print(f"      ❌ Endpoint not found - route not loaded!")
            elif response.status_code == 403 or response.status_code == 401:
                print(f"      ✅ Endpoint exists (requires authentication)")
            elif response.status_code == 422:
                print(f"      ✅ Endpoint exists (validation error)")
            else:
                print(f"      ℹ️  Unexpected status code")
                
        except Exception as e:
            print(f"   {endpoint}: Error - {str(e)}")

def check_server_health():
    """Check if the server is running and responding"""
    print("\n🏥 Checking server health...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Server is running and responding")
            data = response.json()
            print(f"   Response: {data}")
            return True
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server is not accessible: {str(e)}")
        return False

def check_swagger_ui():
    """Check if Swagger UI is accessible"""
    print("\n📖 Checking Swagger UI...")
    
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Swagger UI is accessible at /docs")
            
            # Check if the HTML contains references to assignment endpoints
            html_content = response.text
            if "assignments" in html_content.lower():
                print("✅ Assignment endpoints found in Swagger UI HTML")
            else:
                print("❌ Assignment endpoints not found in Swagger UI HTML")
                
            if "grades" in html_content.lower():
                print("✅ Grade endpoints found in Swagger UI HTML")
            else:
                print("❌ Grade endpoints not found in Swagger UI HTML")
                
        else:
            print(f"❌ Swagger UI not accessible: Status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error accessing Swagger UI: {str(e)}")

def main():
    """Run all diagnostic checks"""
    print("🚀 Starting FastAPI Endpoint Diagnostic")
    print("=" * 50)
    
    # Check if server is running
    if not check_server_health():
        print("\n⚠️  Server is not running. Please start your FastAPI server first.")
        return
    
    # Check OpenAPI spec
    endpoints_exist = check_swagger_endpoints()
    
    # Check direct access
    check_direct_endpoint_access()
    
    # Check Swagger UI
    check_swagger_ui()
    
    print("\n" + "=" * 50)
    if endpoints_exist:
        print("✅ Diagnosis: Endpoints are properly loaded!")
        print("💡 If you can't see them in Swagger UI, try:")
        print("   1. Hard refresh your browser (Ctrl+F5)")
        print("   2. Clear browser cache")
        print("   3. Check browser console for JavaScript errors")
        print("   4. Try accessing /docs in incognito mode")
    else:
        print("❌ Diagnosis: Endpoints are NOT loaded!")
        print("💡 Possible solutions:")
        print("   1. Check if the router is properly included in main.py")
        print("   2. Verify all imports are working correctly")
        print("   3. Check for syntax errors in the endpoint file")
        print("   4. Restart your FastAPI server")
        print("   5. Check server logs for error messages")

if __name__ == "__main__":
    print("📋 FastAPI Assignment & Grade Endpoints Diagnostic Tool")
    print("🔧 Make sure your server is running before running this script")
    print()
    
    # Prompt for server URL
    server_url = input(f"Enter your server URL (default: {BASE_URL}): ").strip()
    if server_url:
        BASE_URL = server_url.rstrip('/')
    
    print(f"🌐 Using server URL: {BASE_URL}")
    print()
    
    main()
