"""
Test script for Video Call and Transcription API
Run this to test your endpoints after starting the server
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoints():
    """Test the video call endpoints"""
    
    print("🧪 Testing Video Call & Transcription API")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Services: {response.json().get('services', [])}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Test 2: Check if video-calls endpoints are available
    print("\n2. Testing API documentation...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ API documentation available at /docs")
        else:
            print(f"❌ API docs not available: {response.status_code}")
    except Exception as e:
        print(f"❌ API docs error: {e}")
    
    # Test 3: Try to access protected endpoint (should fail without auth)
    print("\n3. Testing authentication (should fail)...")
    try:
        response = requests.get(f"{BASE_URL}/video-calls/my-rooms")
        if response.status_code == 401:
            print("✅ Authentication protection working")
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth test error: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Next steps:")
    print("1. Start your server: python main.py")
    print("2. Visit http://localhost:8000/docs to see all endpoints")
    print("3. Get an auth token from your user backend")
    print("4. Test the endpoints with proper authentication")
    print("\n📋 Available endpoints:")
    print("- POST /video-calls/create-room")
    print("- GET  /video-calls/room/{room_id}")
    print("- GET  /video-calls/my-rooms")
    print("- GET  /video-calls/active-rooms")
    print("- POST /video-calls/room/{room_id}/start-transcription")
    print("- GET  /video-calls/session/{session_id}/transcript")
    print("- GET  /video-calls/session/{session_id}/analyze")
    print("- WS   /video-calls/room/{room_id}/ws")

if __name__ == "__main__":
    test_endpoints()
