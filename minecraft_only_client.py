#!/usr/bin/env python3
"""
Minecraft-Only Narrator Client
Narrates Minecraft gameplay events without screenshots (performance test branch)
"""

import os
import sys
import time
import subprocess
import platform
import asyncio
import threading
import json
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
MINECRAFT_DATA_FILE = SCREENSHOT_DIR / "minecraft_data.json"
CHECK_INTERVAL = 2  # Check for new events every 2 seconds

# Global state for pipeline
event_queue = []  # Raw events waiting to be narrated
audio_queue = []  # Generated audio ready to play
is_playing_audio = False
is_generating_narration = False  # Singleton flag: only one generation at a time
event_lock = threading.Lock()
audio_lock = threading.Lock()

def download_sfx(mp3_url: str, filename: str) -> Path:
    """
    Download sound effect from URL.
    
    Sound effects provided by MyInstants API (https://github.com/abdipr/myinstants-api)
    Sounds sourced from MyInstants.com. Used with attribution for non-commercial purposes.
    """
    sfx_path = SCREENSHOT_DIR / filename
    try:
        response = requests.get(mp3_url, timeout=10)
        response.raise_for_status()
        with open(sfx_path, 'wb') as f:
            f.write(response.content)
        return sfx_path
    except Exception as e:
        print(f"⚠️  Failed to download SFX: {e}")
        return None

def play_audio(audio_file: Path, max_duration: float = None):
    """Play audio file (cross-platform, no window on Windows)
    
    Args:
        audio_file: Path to audio file
        max_duration: Maximum duration in seconds (None = play full file)
    """
    if not audio_file.exists():
        return
    
    print(f"🔊 Playing audio: {audio_file}")
    system = platform.system()
    
    if system == "Darwin":  # macOS
        process = subprocess.Popen(["afplay", str(audio_file)])
        if max_duration:
            try:
                process.wait(timeout=max_duration)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                print(f"⏱️  Audio cut off after {max_duration}s")
        else:
            process.wait()
    elif system == "Windows":
        # Use ffplay with duration limit (hidden window)
        try:
            cmd = ["ffplay", "-nodisp", "-autoexit", str(audio_file)]
            if max_duration:
                cmd.extend(["-t", str(max_duration)])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if max_duration:
                try:
                    process.wait(timeout=max_duration + 1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    print(f"⏱️  Audio cut off after {max_duration}s")
            else:
                process.wait()
        except FileNotFoundError:
            # Fallback: use PowerShell with timeout
            try:
                timeout_cmd = f"-t {int(max_duration)}" if max_duration else ""
                subprocess.run([
                    "powershell", "-WindowStyle", "Hidden", "-Command",
                    f"Add-Type -AssemblyName presentationCore; "
                    f"$mediaPlayer = New-Object System.Windows.Media.MediaPlayer; "
                    f"$mediaPlayer.Open('{audio_file.absolute()}'); "
                    f"$mediaPlayer.Play(); "
                    f"Start-Sleep -Seconds {int(max_duration) if max_duration else '([int]($mediaPlayer.NaturalDuration.TimeSpan.TotalSeconds + 1))'}"
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=max_duration + 1 if max_duration else None)
            except:
                print("⚠️  Could not play audio")
    else:  # Linux
        # Try various Linux audio players
        for player in ["paplay", "mpg123", "ffplay", "aplay"]:
            try:
                process = subprocess.Popen([player, str(audio_file)], 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
                if max_duration:
                    try:
                        process.wait(timeout=max_duration)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        print(f"⏱️  Audio cut off after {max_duration}s")
                else:
                    process.wait()
                break
            except FileNotFoundError:
                continue

async def generate_audio_file(batch_narrations):
    """Generate audio file from narrations"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    server_params = StdioServerParameters(
        command=python_cmd,
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Summarize all narrations into one
                result = await session.call_tool("summarize_narrations", {
                    "narrations": batch_narrations
                })
                summarized_text = result.content[0].text
                print(f"📝 Summary: {summarized_text}")
                
                audio_filename = f"narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                result = await session.call_tool("tts", {
                    "text": summarized_text,
                    "output_file": audio_filename
                })
                
                return SCREENSHOT_DIR / audio_filename
    except KeyboardInterrupt:
        raise
    except Exception as e:
        # Suppress process termination errors - they're expected during cleanup
        if "Process group termination" not in str(e) and "TaskGroup" not in str(e):
            print(f"❌ Error generating audio: {e}")
        return None

async def minecraft_event_loop():
    """Monitor Minecraft events and add them to event queue"""
    last_timestamp = None
    
    while True:
        # Check if Minecraft data file exists and has new events
        if MINECRAFT_DATA_FILE.exists():
            try:
                with open(MINECRAFT_DATA_FILE, 'r') as f:
                    import json
                    events = json.load(f)
                
                if not events:
                    # Reset timestamp when events are empty - stay silent
                    last_timestamp = None
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                # Get the most recent event timestamp
                latest_event = events[-1]  # Last event is newest
                current_timestamp = latest_event.get('timestamp')
                
                # If timestamp changed, add event to queue (don't generate yet)
                if current_timestamp != last_timestamp:
                    print(f"🎮 New event: {latest_event.get('event_type')} - {latest_event.get('event_source')}")
                    
                    with event_lock:
                        event_queue.append(latest_event)
                    
                    last_timestamp = current_timestamp
                        
            except Exception as e:
                print(f"⚠️  Error reading events: {e}")
        else:
            # Reset timestamp if file doesn't exist
            last_timestamp = None
        
        await asyncio.sleep(CHECK_INTERVAL)

async def generate_audio_pipeline():
    """Pipeline: Batch events and generate audio while previous audio plays"""
    global is_generating_narration
    
    while True:
        # Wait if no events queued OR already generating (singleton)
        if not event_queue or is_generating_narration:
            await asyncio.sleep(0.5)
            continue
        
        # Set singleton flag - only one generation at a time
        is_generating_narration = True
        
        # Get ALL queued events and generate ONE narration from them
        with event_lock:
            if not event_queue:
                is_generating_narration = False
                continue
            batch_events = event_queue.copy()
            event_queue.clear()
        
        print(f"\n{'='*50}")
        print(f"🎤 Generating narration for {len(batch_events)} event(s)...")
        print(f"{'='*50}")
        
        # Generate single narration from all batched events
        python_cmd = "python" if platform.system() == "Windows" else "python3"
        server_params = StdioServerParameters(
            command=python_cmd,
            args=["mcp_server.py"],
            env={**os.environ, "SCREENSHOT_DIR": str(SCREENSHOT_DIR)}
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Load current Minecraft data
                    with open(MINECRAFT_DATA_FILE, 'r') as f:
                        minecraft_data = f.read()
                    
                    await session.call_tool("get_minecraft_input", {"minecraft_data": minecraft_data})
                    
                    # Generate ONE narration for all events
                    result = await session.call_tool("describe_for_narration", {
                        "image_count": 0,
                        "include_minecraft": True
                    })
                    
                    response_data = json.loads(result.content[0].text)
                    narration = response_data["narration"]
                    sfx_info = response_data.get("sfx")
                    
                    print(f"📝 Narration: {narration[:80]}...")
                    if sfx_info:
                        print(f"🎵 SFX: {sfx_info['title']}")
                    
                    # Generate audio
                    audio_filename = f"narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                    await session.call_tool("tts", {"text": narration, "output_file": audio_filename})
                    audio_path = SCREENSHOT_DIR / audio_filename
                    
                    # Download SFX
                    sfx_path = None
                    if sfx_info:
                        sfx_path = download_sfx(sfx_info['mp3'], f"sfx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                    
                    # Add to audio queue
                    if audio_path.exists():
                        with audio_lock:
                            audio_queue.append({"audio_path": audio_path, "sfx_path": sfx_path})
                        print(f"✅ Audio ready ({len(audio_queue)} in queue)")
                    
        except Exception as e:
            if "Process group termination" not in str(e):
                print(f"❌ Error: {e}")
        
        # Release singleton flag
        is_generating_narration = False

async def play_audio_pipeline():
    """Pipeline: Play audio as soon as it's ready"""
    global is_playing_audio
    
    while True:
        # Wait if no audio ready
        if not audio_queue:
            await asyncio.sleep(0.5)
            continue
        
        # Get next audio to play
        with audio_lock:
            if not audio_queue:
                continue
            audio_item = audio_queue.pop(0)
        
        audio_path = audio_item["audio_path"]
        sfx_path = audio_item["sfx_path"]
        
        is_playing_audio = True
        
        try:
            # Play narration first, then SFX
            print(f"🎵 Playing narration...")
            await asyncio.to_thread(play_audio, audio_path)
            
            # Then play sound effect after narration finishes (max 5 seconds)
            if sfx_path and sfx_path.exists():
                print(f"🎵 Playing sound effect (max 5s)...")
                await asyncio.to_thread(play_audio, sfx_path, 5.0)
            
            print(f"✅ Audio playback completed")
        except Exception as e:
            print(f"❌ Error playing audio: {e}")
            import traceback
            traceback.print_exc()
        
        is_playing_audio = False
        print(f"{'='*50}\n")

def start_minecraft_receiver():
    """Start the Minecraft receiver server in background"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    try:
        # Check if receiver is already running
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()
        
        if result == 0:
            print("🎮 Minecraft receiver already running on port 8080")
            return None
        
        # Start receiver in background
        receiver_process = subprocess.Popen(
            [python_cmd, "minecraft_receiver.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        print("🎮 Minecraft receiver started on port 8080")
        return receiver_process
    except Exception as e:
        print(f"⚠️  Could not start Minecraft receiver: {e}")
        return None

async def main():
    """Main entry point"""
    print("🚀 Minecraft-Only Narrator Started (Performance Test)")
    print(f"📁 Data directory: {SCREENSHOT_DIR}")
    print(f"⏱️  Checking for Minecraft events every {CHECK_INTERVAL} seconds")
    print("📝 No screenshots - Minecraft events only!")
    print("\n🎵 Sound Effects: MyInstants API (https://github.com/abdipr/myinstants-api)")
    print("   Sounds from MyInstants.com - Used with attribution")
    
    # Start Minecraft receiver automatically
    receiver_process = start_minecraft_receiver()
    
    print("\nPress Ctrl+C to stop\n")
    
    try:
        # Run all pipeline stages concurrently
        await asyncio.gather(
            minecraft_event_loop(),      # Stage 1: Detect & batch events
            generate_audio_pipeline(),   # Stage 2: Generate audio
            play_audio_pipeline()        # Stage 3: Play audio
        )
    except KeyboardInterrupt:
        print("\n\n👋 Stopping Minecraft narrator...")
        
        # Stop Minecraft receiver if we started it
        if receiver_process:
            print("🛑 Stopping Minecraft receiver...")
            receiver_process.terminate()
            receiver_process.wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
