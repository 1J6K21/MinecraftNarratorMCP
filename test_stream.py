#!/usr/bin/env python3
"""Test the stream server"""

import requests
import time

# Send some test events
events = [
    {
        "type": "narration",
        "data": {
            "text": "This dumbass just fell off a cliff",
            "sfx": {
                "title": "BRUH",
                "query": "bruh",
                "mp3": "https://example.com/bruh.mp3"
            }
        }
    },
    {
        "type": "sfx",
        "data": {
            "title": "BRUH",
            "query": "bruh"
        }
    },
    {
        "type": "audio",
        "data": {
            "message": "Playing SFX + narration"
        }
    }
]

print("📡 Sending test events to stream server...")
for event in events:
    response = requests.post("http://localhost:5001/broadcast", json=event)
    print(f"✅ Sent {event['type']}: {response.json()}")
    time.sleep(1)

print("\n📊 Getting latest events...")
response = requests.get("http://localhost:5001/events")
print(response.json())

print("\n✅ Test complete!")
print("📺 View in browser: http://localhost:5001")
print("📡 Stream with curl: curl http://localhost:5001/stream")
