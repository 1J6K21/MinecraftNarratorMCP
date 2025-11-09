#!/usr/bin/env python3
"""
Stream Server for Screenshot Narrator
Provides HTTP endpoint to stream narration events in real-time
"""

from flask import Flask, Response, jsonify
import json
import time
from pathlib import Path
from datetime import datetime
import threading
import queue

app = Flask(__name__)

# Global queue for events
event_queue = queue.Queue()
latest_events = []
MAX_EVENTS = 50

class EventBroadcaster:
    """Broadcasts events to all connected clients"""
    def __init__(self):
        self.listeners = []
        self.lock = threading.Lock()
    
    def add_listener(self, q):
        with self.lock:
            self.listeners.append(q)
    
    def remove_listener(self, q):
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)
    
    def broadcast(self, event):
        with self.lock:
            # Add to latest events
            latest_events.append(event)
            if len(latest_events) > MAX_EVENTS:
                latest_events.pop(0)
            
            # Broadcast to all listeners
            dead_listeners = []
            for listener in self.listeners:
                try:
                    listener.put(event)
                except:
                    dead_listeners.append(listener)
            
            # Remove dead listeners
            for listener in dead_listeners:
                self.listeners.remove(listener)

broadcaster = EventBroadcaster()

def add_event(event_type, data):
    """Add an event to the broadcast queue"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "data": data
    }
    broadcaster.broadcast(event)

@app.route('/')
def index():
    """Show simple HTML page with event stream"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Screenshot Narrator Stream</title>
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
        }
        .event.narration {
            border-left-color: #4ec9b0;
        }
        .event.sfx {
            border-left-color: #ce9178;
        }
        .event.audio {
            border-left-color: #dcdcaa;
        }
        .timestamp {
            color: #858585;
            font-size: 0.9em;
        }
        .type {
            color: #569cd6;
            font-weight: bold;
            text-transform: uppercase;
        }
        .data {
            margin-top: 10px;
            color: #d4d4d4;
        }
        .narration-text {
            color: #ce9178;
            font-size: 1.1em;
            font-style: italic;
        }
        .sfx-info {
            color: #4ec9b0;
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
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <h1>🎬 Screenshot Narrator - Live Stream</h1>
    
    <div class="curl-info">
        <strong>📡 Stream via curl:</strong><br>
        <code>curl http://localhost:5001/stream</code><br><br>
        <strong>📊 Get latest events (JSON):</strong><br>
        <code>curl http://localhost:5001/events</code>
    </div>
    
    <div id="events"></div>
    
    <script>
        const eventsDiv = document.getElementById('events');
        const statusDiv = document.getElementById('status');
        
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
            const eventDiv = document.createElement('div');
            eventDiv.className = 'event ' + event.type;
            
            let content = `
                <div class="timestamp">${new Date(event.timestamp).toLocaleString()}</div>
                <div class="type">${event.type}</div>
                <div class="data">
            `;
            
            if (event.type === 'narration') {
                content += `<div class="narration-text">"${event.data.text}"</div>`;
                if (event.data.sfx) {
                    content += `<div class="sfx-info">🎵 SFX: ${event.data.sfx.title} (${event.data.sfx.query})</div>`;
                }
            } else if (event.type === 'sfx') {
                content += `<div class="sfx-info">🎵 ${event.data.title}</div>`;
                content += `<div>Query: ${event.data.query}</div>`;
            } else if (event.type === 'audio') {
                content += `<div>🔊 ${event.data.message}</div>`;
            } else {
                content += `<pre>${JSON.stringify(event.data, null, 2)}</pre>`;
            }
            
            content += '</div>';
            eventDiv.innerHTML = content;
            
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

@app.route('/stream')
def stream():
    """Server-Sent Events stream"""
    def event_stream():
        # Create a queue for this client
        q = queue.Queue()
        broadcaster.add_listener(q)
        
        try:
            # Send recent events first
            for event in latest_events[-10:]:
                yield f"data: {json.dumps(event)}\n\n"
            
            # Then stream new events
            while True:
                event = q.get()
                yield f"data: {json.dumps(event)}\n\n"
        except GeneratorExit:
            broadcaster.remove_listener(q)
    
    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/events')
def get_events():
    """Get latest events as JSON"""
    return jsonify({
        "events": latest_events[-20:],
        "count": len(latest_events)
    })

@app.route('/broadcast', methods=['POST'])
def broadcast():
    """Receive events from clients"""
    from flask import request
    try:
        data = request.get_json()
        event_type = data.get('type', 'unknown')
        event_data = data.get('data', {})
        add_event(event_type, event_data)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "listeners": len(broadcaster.listeners),
        "events": len(latest_events)
    })

def run_server(port=5001):
    """Run the Flask server"""
    print(f"🌐 Stream server starting on http://localhost:{port}")
    print(f"📺 Web UI: http://localhost:{port}")
    print(f"📡 Stream: curl http://localhost:{port}/stream")
    print(f"📊 Events: curl http://localhost:{port}/events")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)

if __name__ == "__main__":
    run_server()
