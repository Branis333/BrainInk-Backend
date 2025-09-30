"""
Debug Mobile App Content Loading Issue
Check both backend response and mobile app parsing
"""

import requests
import json
from datetime import datetime

# Production server URL  
PRODUCTION_URL = "https://brainink-backend.onrender.com"
CONTENT_ENDPOINT = f"{PRODUCTION_URL}/after-school/reading-assistant/content"

# Test JWT token
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmFtZSI6IkJyYW5pcyIsImlkIjoyLCJhY2NfdHlwZSI6InVzZXIiLCJleHAiOjE3NTg4ODU1Mzl9.wWA5-qoKnCege9OnvaidrTN74Gmm1JBDVp5NKc-BbWA"

def debug_mobile_app_request():
    """Debug the exact request your mobile app is making"""
    
    print("🔍 DEBUGGING MOBILE APP CONTENT LOADING")
    print("=" * 60)
    print(f"⏰ Debug Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exact same request as mobile app
    mobile_url = f"{CONTENT_ENDPOINT}?grade_level=K&limit=10"
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    print(f"\n📱 MOBILE APP REQUEST:")
    print(f"URL: {mobile_url}")
    print(f"Headers: Authorization: Bearer {TEST_TOKEN[:20]}...")
    
    try:
        print(f"\n🌐 Making request...")
        response = requests.get(mobile_url, headers=headers, timeout=15)
        
        print(f"📊 RESPONSE ANALYSIS:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Time: {response.elapsed.total_seconds():.2f}s")
        print(f"   Content-Type: {response.headers.get('content-type', 'Not set')}")
        print(f"   Content-Length: {len(response.text)} characters")
        
        if response.status_code == 200:
            print(f"\n✅ SUCCESS - Analyzing response structure...")
            
            try:
                data = response.json()
                print(f"\n📋 RESPONSE STRUCTURE:")
                print(f"   Type: {type(data)}")
                print(f"   Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                
                # Check each field your mobile app expects
                if isinstance(data, dict):
                    success = data.get('success', 'NOT FOUND')
                    total_count = data.get('total_count', 'NOT FOUND')
                    items = data.get('items', 'NOT FOUND')
                    
                    print(f"\n🔍 FIELD ANALYSIS:")
                    print(f"   success: {success} (type: {type(success)})")
                    print(f"   total_count: {total_count} (type: {type(total_count)})")
                    print(f"   items: {type(items)} with {len(items) if isinstance(items, list) else 'N/A'} items")
                    
                    if isinstance(items, list) and len(items) > 0:
                        print(f"\n📚 FIRST ITEM STRUCTURE:")
                        first_item = items[0]
                        print(f"   Type: {type(first_item)}")
                        if isinstance(first_item, dict):
                            print(f"   Keys: {list(first_item.keys())}")
                            print(f"   Title: {first_item.get('title', 'NO TITLE')}")
                            print(f"   Content Preview: {first_item.get('content', 'NO CONTENT')[:50]}...")
                            print(f"   Reading Level: {first_item.get('reading_level', 'NO LEVEL')}")
                            print(f"   Content Type: {first_item.get('content_type', 'NO TYPE')}")
                    
                    print(f"\n🎯 MOBILE APP PARSING CHECK:")
                    # Simulate mobile app parsing logic
                    if success and items and isinstance(items, list):
                        print(f"   ✅ Mobile app should see {len(items)} items")
                        print(f"   ✅ Success flag: {success}")
                        print(f"   ✅ Items array: {len(items)} items")
                    else:
                        print(f"   ❌ Mobile app parsing issue detected!")
                        print(f"       - success check: {bool(success)}")
                        print(f"       - items check: {bool(items and isinstance(items, list))}")
                
                print(f"\n📄 FULL RESPONSE (formatted):")
                print(json.dumps(data, indent=2)[:1000] + "..." if len(json.dumps(data)) > 1000 else json.dumps(data, indent=2))
                
            except json.JSONDecodeError:
                print(f"❌ INVALID JSON RESPONSE:")
                print(f"Raw response: {response.text[:500]}...")
                
        else:
            print(f"\n❌ REQUEST FAILED:")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:300]}...")
            
    except Exception as e:
        print(f"❌ REQUEST ERROR: {e}")
        
    print(f"\n" + "=" * 60)

def show_mobile_app_debugging_tips():
    """Show debugging tips for mobile app"""
    
    print(f"\n🔧 MOBILE APP DEBUGGING TIPS:")
    print(f"""
1. **Add More Logging in Your Mobile App:**
   ```javascript
   console.log('📊 Raw API response:', response);
   console.log('📊 Response status:', response.status);
   console.log('📊 Response headers:', response.headers);
   
   const data = await response.json();
   console.log('📊 Parsed JSON:', data);
   console.log('📊 Data type:', typeof data);
   console.log('📊 Data keys:', Object.keys(data));
   console.log('📊 Items array:', data.items);
   console.log('📊 Items length:', data.items ? data.items.length : 'No items');
   ```

2. **Check Your Content Parsing Logic:**
   ```javascript
   // Make sure you're checking the right fields
   if (data.success && data.items && Array.isArray(data.items)) {{
       console.log(`✅ Found ${{data.items.length}} reading items`);
       return data.items;
   }} else {{
       console.log('❌ Invalid response structure:', data);
       return [];
   }}
   ```

3. **Test Response Format:**
   The API returns this structure:
   ```json
   {{
     "success": true,
     "total_count": 4,
     "items": [...],
     "pagination": {{...}}
   }}
   ```
""")

if __name__ == "__main__":
    debug_mobile_app_request()
    show_mobile_app_debugging_tips()