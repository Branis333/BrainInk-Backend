"""
Test script for Reading Assistant endpoints
Run this to verify the API is working correctly
"""

import requests
import json
import os
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your server runs on different port
TEST_USER_TOKEN = None  # You'll need to get this from login

def get_auth_headers():
    """Get authentication headers for requests"""
    if not TEST_USER_TOKEN:
        print("❌ Please set TEST_USER_TOKEN with a valid JWT token")
        return None
    return {"Authorization": f"Bearer {TEST_USER_TOKEN}"}

def test_health_check():
    """Test the health check endpoint"""
    print("\n🔍 Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/after-school/reading-assistant/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data['status']}")
            print(f"   Features: {', '.join(data['features'])}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

def test_content_list():
    """Test getting reading content list"""
    print("\n📚 Testing content list...")
    
    headers = get_auth_headers()
    if not headers:
        return
    
    try:
        response = requests.get(
            f"{BASE_URL}/after-school/reading-assistant/content",
            headers=headers,
            params={"reading_level": "kindergarten", "page": 1, "size": 5}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Content list retrieved: {data['total_count']} items")
            
            if data['items']:
                first_item = data['items'][0]
                print(f"   Sample: '{first_item['title']}' ({first_item['reading_level']})")
            else:
                print("   No content found - you may need to populate the database")
        else:
            print(f"❌ Content list failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Content list error: {e}")

def test_content_generation():
    """Test AI content generation"""
    print("\n🤖 Testing AI content generation...")
    
    headers = get_auth_headers()
    if not headers:
        return
    
    payload = {
        "reading_level": "kindergarten",
        "difficulty_level": "beginner",
        "content_type": "sentence",
        "topic": "pets",
        "word_count_target": 15
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/after-school/reading-assistant/content/generate",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Content generated: '{data['title']}'")
            print(f"   Content: {data['content'][:50]}...")
            print(f"   Words: {data['word_count']}")
        else:
            print(f"❌ Content generation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Content generation error: {e}")

def test_reading_session():
    """Test starting a reading session"""
    print("\n📖 Testing reading session...")
    
    headers = get_auth_headers()
    if not headers:
        return
    
    # First, get available content
    try:
        content_response = requests.get(
            f"{BASE_URL}/after-school/reading-assistant/content",
            headers=headers,
            params={"page": 1, "size": 1}
        )
        
        if content_response.status_code != 200:
            print("❌ Cannot get content for session test")
            return
            
        content_data = content_response.json()
        if not content_data['items']:
            print("❌ No content available for session test")
            return
            
        content_id = content_data['items'][0]['id']
        
        # Start reading session
        session_payload = {
            "content_id": content_id,
            "session_type": "practice"
        }
        
        session_response = requests.post(
            f"{BASE_URL}/after-school/reading-assistant/sessions/start",
            headers=headers,
            json=session_payload
        )
        
        if session_response.status_code == 200:
            session_data = session_response.json()
            print(f"✅ Reading session started: ID {session_data['id']}")
            print(f"   Content: {content_data['items'][0]['title']}")
            return session_data['id']
        else:
            print(f"❌ Reading session failed: {session_response.status_code}")
            print(f"   Response: {session_response.text}")
            
    except Exception as e:
        print(f"❌ Reading session error: {e}")

def test_progress_dashboard():
    """Test getting student progress dashboard"""
    print("\n📊 Testing progress dashboard...")
    
    headers = get_auth_headers()
    if not headers:
        return
    
    try:
        response = requests.get(
            f"{BASE_URL}/after-school/reading-assistant/dashboard",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            progress = data['current_progress']
            print(f"✅ Dashboard retrieved")
            print(f"   Level: {progress['current_reading_level']}")
            print(f"   Sessions: {progress['total_sessions']}")
            print(f"   Accuracy: {progress['average_accuracy'] or 'N/A'}%")
        else:
            print(f"❌ Dashboard failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

def test_recommendations():
    """Test content recommendations"""
    print("\n💡 Testing content recommendations...")
    
    headers = get_auth_headers()
    if not headers:
        return
    
    try:
        response = requests.get(
            f"{BASE_URL}/after-school/reading-assistant/recommendations",
            headers=headers,
            params={"limit": 3}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Recommendations retrieved: {len(data)} items")
            
            for i, item in enumerate(data[:2], 1):
                print(f"   {i}. {item['title']} ({item['reading_level']}/{item['difficulty_level']})")
        else:
            print(f"❌ Recommendations failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Recommendations error: {e}")

def run_all_tests():
    """Run all reading assistant tests"""
    print("🧪 Running Reading Assistant API Tests")
    print("=" * 50)
    
    # Basic connectivity
    test_health_check()
    
    if not TEST_USER_TOKEN:
        print("\n⚠️  Skipping authenticated tests - no token provided")
        print("\nTo run full tests:")
        print("1. Start the server: uvicorn main:app --reload")
        print("2. Get a JWT token by logging in")
        print("3. Set TEST_USER_TOKEN in this script")
        print("4. Run the tests again")
        return
    
    # Authenticated endpoints
    test_content_list()
    test_content_generation()
    test_reading_session()
    test_progress_dashboard()
    test_recommendations()
    
    print("\n" + "=" * 50)
    print("🎉 Reading Assistant tests completed!")

if __name__ == "__main__":
    run_all_tests()