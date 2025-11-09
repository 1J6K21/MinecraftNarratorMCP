#!/usr/bin/env python3
"""Test if Minecraft receiver is getting data"""

import json
import time
from pathlib import Path

MINECRAFT_DATA_FILE = Path("./screenshots/minecraft_data.json")

print("🎮 Monitoring Minecraft data file...")
print(f"📁 File: {MINECRAFT_DATA_FILE}")
print("=" * 60)

if not MINECRAFT_DATA_FILE.exists():
    print("❌ File doesn't exist yet. Waiting for Minecraft events...")
else:
    print("✅ File exists!")

last_content = None
last_timestamp = None

try:
    while True:
        if MINECRAFT_DATA_FILE.exists():
            with open(MINECRAFT_DATA_FILE, 'r') as f:
                content = f.read()
                
            if content != last_content:
                print(f"\n🔄 File updated at {time.strftime('%H:%M:%S')}")
                try:
                    events = json.loads(content)
                    print(f"📊 Total events: {len(events)}")
                    
                    if events:
                        latest = events[-1]
                        print(f"📝 Latest event:")
                        print(f"   Type: {latest.get('event_type')}")
                        print(f"   Time: {latest.get('timestamp')}")
                        print(f"   Details: {latest.get('details')}")
                        
                        if latest.get('timestamp') != last_timestamp:
                            print("   ✅ NEW EVENT!")
                            last_timestamp = latest.get('timestamp')
                except json.JSONDecodeError:
                    print("⚠️  Invalid JSON")
                
                last_content = content
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n👋 Stopped monitoring")
