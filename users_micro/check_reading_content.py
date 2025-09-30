"""
Check what reading content exists in the production database
"""

import requests
import json

# Production server URL
PRODUCTION_URL = "https://brainink-backend.onrender.com"
CONTENT_ENDPOINT = f"{PRODUCTION_URL}/after-school/reading-assistant/content"

# Test JWT token from your mobile app logs
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmFtZSI6IkJyYW5pcyIsImlkIjoyLCJhY2NfdHlwZSI6InVzZXIiLCJleHAiOjE3NTg4ODU1Mzl9.wWA5-qoKnCege9OnvaidrTN74Gmm1JBDVp5NKc-BbWA"

def test_content_endpoints():
    """Test different content endpoint variations"""
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    print("🔍 Testing Reading Content Availability")
    print("=" * 50)
    
    # Test variations
    test_cases = [
        ("All content (no filters)", ""),
        ("Mobile app current request", "?grade_level=K&limit=10"),
        ("Correct KINDERGARTEN parameter", "?reading_level=KINDERGARTEN&limit=10"),
        ("All KINDERGARTEN content", "?reading_level=KINDERGARTEN"),
        ("GRADE_1 content", "?reading_level=GRADE_1&limit=10"),
        ("GRADE_2 content", "?reading_level=GRADE_2&limit=10"),
        ("GRADE_3 content", "?reading_level=GRADE_3&limit=10"),
        ("ELEMENTARY difficulty", "?difficulty_level=ELEMENTARY&limit=10"),
        ("Large limit test", "?limit=50")
    ]
    
    for description, params in test_cases:
        print(f"\n🧪 Testing: {description}")
        print(f"🌐 URL: {CONTENT_ENDPOINT}{params}")
        
        try:
            response = requests.get(f"{CONTENT_ENDPOINT}{params}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                total_count = data.get('total_count', 0)
                items_count = len(data.get('items', []))
                
                print(f"✅ SUCCESS: {total_count} total, {items_count} returned")
                
                if items_count > 0:
                    # Show sample of what's available
                    sample = data['items'][0]
                    print(f"   📋 Sample: '{sample.get('title', 'No title')}' - {sample.get('reading_level', 'No level')} - {sample.get('content_type', 'No type')}")
                    
                    if items_count > 1:
                        print(f"   📊 Available levels: {list(set([item.get('reading_level') for item in data['items']]))}")
                        print(f"   📚 Content types: {list(set([item.get('content_type') for item in data['items']]))}")
                
            elif response.status_code == 422:
                print(f"❌ PARAMETER ERROR: Invalid parameters")
                print(f"   Response: {response.text[:200]}")
            else:
                print(f"❌ ERROR {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"❌ REQUEST FAILED: {e}")
    
    print(f"\n" + "=" * 50)

def show_mobile_app_fix():
    """Show how to fix the mobile app request"""
    
    print(f"\n📱 MOBILE APP FIX NEEDED:")
    print(f"Your mobile app is using: ?grade_level=K&limit=10")
    print(f"But the endpoint expects: ?reading_level=KINDERGARTEN&limit=10")
    print(f"\n🔧 Update your mobile app to use:")
    print(f"   - reading_level=KINDERGARTEN (instead of grade_level=K)")
    print(f"   - reading_level=GRADE_1 (instead of grade_level=1)")
    print(f"   - reading_level=GRADE_2 (instead of grade_level=2)")
    print(f"   - reading_level=GRADE_3 (instead of grade_level=3)")

if __name__ == "__main__":
    test_content_endpoints()
    show_mobile_app_fix()