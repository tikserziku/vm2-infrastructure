#!/usr/bin/env python3
# Test Google Sheets Integration

import requests
import json

# Configuration
BASE_URL = "http://localhost:10000"
TEST_VIDEO = "https://www.tiktok.com/@test/video/123456"  # Replace with real URL
API_KEY = "YOUR_GEMINI_API_KEY"  # Replace with your key

def test_sheets_integration():
    """Test Google Sheets integration"""
    
    # 1. Check config
    print("1. Checking configuration...")
    response = requests.get(f"{BASE_URL}/config")
    config = response.json()
    print(f"   Google Sheets connected: {config['google_sheets_connected']}")
    print(f"   Transcriber available: {config['has_transcriber']}")
    
    # 2. Test creating a new spreadsheet
    print("\n2. Testing spreadsheet creation...")
    response = requests.post(f"{BASE_URL}/sheets/create", json={
        "title": "Test TikTok Transcriptions"
    })
    
    if response.status_code == 200:
        result = response.json()
        if 'spreadsheet' in result:
            sheet_id = result['spreadsheet'].get('id')
            sheet_url = result['spreadsheet'].get('url')
            print(f"   ✅ Spreadsheet created!")
            print(f"   ID: {sheet_id}")
            print(f"   URL: {sheet_url}")
        else:
            print(f"   ❌ Error: {result}")
    else:
        print(f"   ❌ HTTP Error: {response.status_code}")
        print(f"   Response: {response.text}")
    
    print("\n✅ Test complete!")
    print("Now you can:")
    print("1. Open http://158.180.56.74 in your browser")
    print("2. Enter a TikTok video URL")
    print("3. Enter your Gemini API key")
    print("4. The transcription will be saved to Google Sheets automatically")

if __name__ == "__main__":
    test_sheets_integration()

