#!/usr/bin/env python3
"""
Minecraft Mod Data Receiver
Receives events from Minecraft mod via HTTP and stores them
"""

from flask import Flask, request, jsonify
import json
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
MINECRAFT_DATA_FILE = SCREENSHOT_DIR / "minecraft_data.json"

# Store events in memory
minecraft_events = []

@app.route('/mcp', methods=['POST'])
def receive_minecraft_event():
    """Receive Minecraft mod events in format: event_type, event_source"""
    try:
        data = request.json
        
        # Extract event data - new format: event_type and event_source
        # event_type = data.get('event_type', data.get('tool_name', 'unknown'))
        # event_source = data.get('event_source', data.get('parameters', {}).get('blockName', 'unknown'))
        
        event_type = data.get('parameters').get('event')
        event_source = data.get('parameters').get('source')

        
        # Create event record
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'event_source': event_source
        }
        
        # Add to events list (keep last 10)
        minecraft_events.append(event)
        if len(minecraft_events) > 10:
            minecraft_events.pop(0)
        
        # Save to file
        with open(MINECRAFT_DATA_FILE, 'w') as f:
            json.dump(minecraft_events, f, indent=2)
        
        print(f"📦 Minecraft event: {event_type} - {event_source}")
        
        return jsonify({
            "status": "success",
            "message": "Event received"
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

@app.route('/mcp/events', methods=['GET'])
def get_events():
    """Get all stored events"""
    return jsonify(minecraft_events)

@app.route('/mcp/clear', methods=['POST'])
def clear_events():
    """Clear all events"""
    minecraft_events.clear()
    if MINECRAFT_DATA_FILE.exists():
        MINECRAFT_DATA_FILE.unlink()
    return jsonify({"status": "success", "message": "Events cleared"})

if __name__ == '__main__':
    print("🎮 Minecraft Mod Receiver Started")
    print("📡 Listening on http://localhost:8080/mcp")
    print("Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=8080, debug=False)
