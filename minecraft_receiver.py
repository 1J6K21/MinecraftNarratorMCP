#!/usr/bin/env python3
"""
Minecraft Mod Data Receiver
Receives events from Minecraft mod via HTTP and stores them
"""

from flask import Flask, request, jsonify, Response
import json
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv
import queue
import threading

load_dotenv()

app = Flask(__name__)

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
MINECRAFT_DATA_FILE = SCREENSHOT_DIR / "minecraft_data.json"

# Store events in memory
minecraft_events = []

# SSE listeners
listeners = []
listeners_lock = threading.Lock()

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
        
        # Notify SSE listeners
        with listeners_lock:
            for q in listeners[:]:
                try:
                    q.put(event)
                except:
                    listeners.remove(q)
        
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

@app.route('/stream')
def stream():
    """Server-Sent Events stream of Minecraft events"""
    def event_stream():
        q = queue.Queue()
        
        with listeners_lock:
            listeners.append(q)
        
        try:
            # Send recent events first
            for event in minecraft_events[-10:]:
                yield f"data: {json.dumps(event)}\n\n"
            
            # Stream new events
            while True:
                event = q.get()
                yield f"data: {json.dumps(event)}\n\n"
        except GeneratorExit:
            with listeners_lock:
                if q in listeners:
                    listeners.remove(q)
    
    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/')
def index():
    """Show simple HTML page with event stream"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Minecraft Events Stream</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            margin: 0;
        }
        h1 {
            color: #4ec9b0;
            border-bottom: 2px solid #4ec9b0;
            padding-bottom: 10px;
        }
        .event {
            background: #252526;
            border-left: 4px solid #007acc;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        .timestamp {
            color: #858585;
            font-size: 0.9em;
        }
        .event-type {
            color: #569cd6;
            font-weight: bold;
            font-size: 1.2em;
        }
        .event-source {
            color: #ce9178;
            font-size: 1.1em;
        }
        #status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            background: #007acc;
            color: white;
            border-radius: 20px;
            font-weight: bold;
        }
        #status.connected {
            background: #4ec9b0;
        }
        #events {
            margin-top: 20px;
        }
        .curl-info {
            background: #252526;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            border: 1px solid #007acc;
        }
        code {
            background: #1e1e1e;
            padding: 2px 6px;
            border-radius: 3px;
            color: #ce9178;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }
        .stat {
            background: #252526;
            padding: 15px;
            border-radius: 4px;
            flex: 1;
        }
        .stat-value {
            font-size: 2em;
            color: #4ec9b0;
            font-weight: bold;
        }
        .stat-label {
            color: #858585;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <h1>🎮 Minecraft Events - Live Stream</h1>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value" id="eventCount">0</div>
            <div class="stat-label">Total Events</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="listeners">0</div>
            <div class="stat-label">Connected Clients</div>
        </div>
    </div>
    
    <div class="curl-info">
        <strong>📡 Stream via curl:</strong><br>
        <code>curl http://localhost:8080/stream</code><br><br>
        <strong>📊 Get events (JSON):</strong><br>
        <code>curl http://localhost:8080/mcp/events</code>
    </div>
    
    <div id="events"></div>
    
    <script>
        const eventsDiv = document.getElementById('events');
        const statusDiv = document.getElementById('status');
        const eventCountDiv = document.getElementById('eventCount');
        let eventCount = 0;
        
        const eventSource = new EventSource('/stream');
        
        eventSource.onopen = () => {
            statusDiv.textContent = '🟢 Connected';
            statusDiv.className = 'connected';
        };
        
        eventSource.onerror = () => {
            statusDiv.textContent = '🔴 Disconnected';
            statusDiv.className = '';
        };
        
        eventSource.onmessage = (e) => {
            const event = JSON.parse(e.data);
            eventCount++;
            eventCountDiv.textContent = eventCount;
            
            const eventDiv = document.createElement('div');
            eventDiv.className = 'event';
            
            eventDiv.innerHTML = `
                <div class="timestamp">${new Date(event.timestamp).toLocaleString()}</div>
                <div class="event-type">⚡ ${event.event_type}</div>
                <div class="event-source">📍 ${event.event_source}</div>
            `;
            
            eventsDiv.insertBefore(eventDiv, eventsDiv.firstChild);
            
            // Keep only last 20 events visible
            while (eventsDiv.children.length > 20) {
                eventsDiv.removeChild(eventsDiv.lastChild);
            }
        };
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("🎮 Minecraft Mod Receiver Started")
    print("📡 Listening on http://localhost:8080/mcp")
    print("Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=8080, debug=False)
