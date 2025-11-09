#!/usr/bin/env python3
"""Test the MyInstants API integration"""

import requests
import json

def test_search(query):
    print(f"\n🔍 Searching for: {query}")
    try:
        response = requests.get(
            "https://myinstants-api.vercel.app/search",
            params={"q": query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # print(f"📦 Raw response: {json.dumps(data, indent=2)}")
        
        if "data" in data and data["data"]:
            print(f"✅ Found {len(data['data'])} results:")
            for i, sound in enumerate(data["data"][:3], 1):
                print(f"\n{i}. {sound.get('title', 'Unknown')}")
                print(f"   MP3: {sound.get('mp3', 'N/A')}")
                print(f"   URL: {sound.get('url', 'N/A')}")
        else:
            print("❌ No results found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test various sound effects
    test_search("bruh")
    test_search("laugh")
    test_search("explosion")
    test_search("wow")
