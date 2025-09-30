"""
Production Deployment Monitor & Debugger
Monitor the reading assistant progress endpoint deployment and help debug issues
"""

import requests
import time
import json
from datetime import datetime

# Production server URL
PRODUCTION_URL = "https://brainink-backend.onrender.com"
PROGRESS_ENDPOINT = f"{PRODUCTION_URL}/after-school/reading-assistant/progress"
CONTENT_ENDPOINT = f"{PRODUCTION_URL}/after-school/reading-assistant/content"

# Test JWT token from your mobile app logs
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmFtZSI6IkJyYW5pcyIsImlkIjoyLCJhY2NfdHlwZSI6InVzZXIiLCJleHAiOjE3NTg4ODU1Mzl9.wWA5-qoKnCege9OnvaidrTN74Gmm1JBDVp5NKc-BbWA"

def test_endpoint(url, token, description):
    """Test an endpoint and return detailed results"""
    print(f"\n🔍 Testing {description}...")
    print(f"🌐 URL: {url}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"⏱️  Response Time: {response.elapsed.total_seconds():.2f}s")
        print(f"📋 Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print(f"✅ SUCCESS: {description}")
            try:
                data = response.json()
                if isinstance(data, dict):
                    print(f"📄 Response keys: {list(data.keys())}")
                    if 'items' in data:
                        print(f"📊 Items count: {len(data['items'])}")
                else:
                    print(f"📄 Response type: {type(data)}")
            except:
                print(f"📄 Response (text): {response.text[:200]}...")
                
        elif response.status_code == 500:
            print(f"❌ SERVER ERROR: {description}")
            print(f"📝 Error response: {response.text}")
            
        elif response.status_code == 401:
            print(f"🔒 AUTHENTICATION ERROR: {description}")
            print("💡 Token may be expired or invalid")
            
        else:
            print(f"⚠️  UNEXPECTED STATUS: {response.status_code}")
            print(f"📝 Response: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT: {description} took too long")
        return False
    except requests.exceptions.ConnectionError:
        print(f"🌐 CONNECTION ERROR: Cannot reach {description}")
        return False
    except Exception as e:
        print(f"❌ UNKNOWN ERROR: {str(e)}")
        return False

def monitor_deployment():
    """Monitor the deployment status of the reading assistant endpoints"""
    
    print("🚀 Reading Assistant Production Deployment Monitor")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Production Server: {PRODUCTION_URL}")
    
    # Test content endpoint (should work)
    content_working = test_endpoint(
        f"{CONTENT_ENDPOINT}?grade_level=K&limit=10", 
        TEST_TOKEN, 
        "Content Endpoint (Working Baseline)"
    )
    
    # Test progress endpoint (the problematic one)
    progress_working = test_endpoint(
        f"{PROGRESS_ENDPOINT}?student_id=1", 
        TEST_TOKEN, 
        "Progress Endpoint (The Fix We're Testing)"
    )
    
    print(f"\n📋 DEPLOYMENT STATUS SUMMARY:")
    print(f"✅ Content Endpoint: {'WORKING' if content_working else 'FAILED'}")
    print(f"{'✅' if progress_working else '❌'} Progress Endpoint: {'WORKING' if progress_working else 'FAILED'}")
    
    if not progress_working:
        print(f"\n🔧 TROUBLESHOOTING STEPS:")
        print(f"1. Check if Render has finished redeploying (can take 2-10 minutes)")
        print(f"2. Verify the database tables exist in production")
        print(f"3. Check production server logs for specific error details")
        print(f"4. Consider running database migration in production")
        
    return progress_working

def continuous_monitor(interval_seconds=30, max_attempts=10):
    """Continuously monitor until the progress endpoint works"""
    
    print(f"\n🔄 Starting continuous monitoring (every {interval_seconds}s, max {max_attempts} attempts)")
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n📅 Attempt {attempt}/{max_attempts} at {datetime.now().strftime('%H:%M:%S')}")
        
        if monitor_deployment():
            print(f"\n🎉 SUCCESS! Progress endpoint is now working after {attempt} attempts!")
            break
        else:
            if attempt < max_attempts:
                print(f"⏳ Waiting {interval_seconds}s before next check...")
                time.sleep(interval_seconds)
            else:
                print(f"\n⚠️  Reached maximum attempts. The progress endpoint still needs manual intervention.")

def diagnose_specific_issues():
    """Run specific diagnostic tests"""
    
    print(f"\n🔬 Running Specific Diagnostics...")
    
    # Test without authentication to see different error
    print(f"\n🔍 Testing without authentication (should get 401)...")
    try:
        response = requests.get(f"{PROGRESS_ENDPOINT}?student_id=1", timeout=5)
        print(f"📊 No-auth status: {response.status_code} (expected 401)")
        if response.status_code != 401:
            print(f"⚠️  Unexpected: {response.text}")
    except Exception as e:
        print(f"❌ No-auth test failed: {e}")
    
    # Test with different student IDs
    student_ids = [1, 2, 999]
    for student_id in student_ids:
        test_endpoint(
            f"{PROGRESS_ENDPOINT}?student_id={student_id}",
            TEST_TOKEN,
            f"Progress with student_id={student_id}"
        )

if __name__ == "__main__":
    try:
        # Run immediate check
        working = monitor_deployment()
        
        if not working:
            # Run diagnostics
            diagnose_specific_issues()
            
            # Ask if user wants continuous monitoring
            print(f"\n❓ Would you like to start continuous monitoring?")
            print(f"   This will check every 30 seconds until the endpoint works.")
            print(f"   Press Ctrl+C to stop at any time.")
            
            user_input = input("\nStart monitoring? (y/n): ").strip().lower()
            if user_input in ['y', 'yes']:
                continuous_monitor()
        else:
            print(f"\n🎉 All endpoints are working! Your mobile app should work now.")
            
    except KeyboardInterrupt:
        print(f"\n🛑 Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Monitor crashed: {e}")
        
    print(f"\n✅ Monitor completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")