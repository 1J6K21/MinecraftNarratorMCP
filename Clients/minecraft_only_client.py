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

# Configuration
EXPLICIT = True  # Set to False for family-friendly mode
MIN_BATCH_SIZE = 5  # Minimum events before generating narration

# Cooldown audio paths
COOLDOWN_AUDIO_EXPLICIT = Path("./Resources/CoolDownAudios/CoolDown_explicit.mp3")
COOLDOWN_AUDIO_NICE = Path("./Resources/CoolDownAudios/CoolDown_nice.mp3")

# SFX Cache directory
SFX_CACHE_DIR = SCREENSHOT_DIR / "sfx_cache"
SFX_CACHE_DIR.mkdir(exist_ok=True)

# Global state for pipeline
event_queue = []  # Raw events waiting to be narrated
audio_queue = []  # Generated audio ready to play
is_playing_audio = False
is_generating_narration = False  # Singleton flag: only one generation at a time
event_lock = threading.Lock()
audio_lock = threading.Lock()

def sanitize_filename(title: str) -> str:
    """Convert SFX title to safe filename"""
    import re
    # Remove special characters, keep alphanumeric and spaces
    safe = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    safe = re.sub(r'\s+', '_', safe)
    # Limit length
    return safe[:50].lower()

def download_sfx(mp3_url: str, title: str) -> Path:
    """
    Download sound effect from URL with caching.
    
    Sound effects provided by MyInstants API (https://github.com/abdipr/myinstants-api)
    Sounds sourced from MyInstants.com. Used with attribution for non-commercial purposes.
    """
    # Create cache filename from title
    cache_filename = f"{sanitize_filename(title)}.mp3"
    sfx_path = SFX_CACHE_DIR / cache_filename
    
    # Check if already cached
    if sfx_path.exists():
        print(f"✅ Using cached SFX: {cache_filename}")
        return sfx_path
    
    # Download if not cached
    try:
        print(f"📥 Downloading new SFX: {title}")
        response = requests.get(mp3_url, timeout=10)
        response.raise_for_status()
        with open(sfx_path, 'wb') as f:
            f.write(response.content)
        print(f"💾 Cached SFX: {cache_filename}")
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
        args=["../mcp_server.py"],
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
        error_str = str(e)
        if not any(x in error_str for x in ["Process group termination", "TaskGroup", "Operation not permitted"]):
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
        # Wait if not enough events OR already generating (singleton)
        current_queue_size = len(event_queue)
        if current_queue_size < MIN_BATCH_SIZE:
            if current_queue_size > 0:
                print(f"⏳ Waiting for more events ({current_queue_size}/{MIN_BATCH_SIZE})...")
            await asyncio.sleep(0.5)
            continue
        
        if is_generating_narration:
            await asyncio.sleep(0.5)
            continue
        
        # Set singleton flag - only one generation at a time
        is_generating_narration = True
        
        # Get ALL queued events and generate ONE narration from them
        with event_lock:
            if len(event_queue) < MIN_BATCH_SIZE:
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
            args=["../mcp_server.py"],
            env={**os.environ, "SCREENSHOT_DIR": str(SCREENSHOT_DIR)}
        )
        
        rate_limited = False
        
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
                    
                    raw_response = result.content[0].text
                    print(f"🔍 Raw MCP response: {raw_response[:200]}...")
                    
                    response_data = json.loads(raw_response)
                    print(f"📦 Parsed response keys: {list(response_data.keys())}")
                    
                    narration = response_data["narration"]
                    sfx_info = response_data.get("sfx")
                    print(f"🎵 SFX info type: {type(sfx_info)}, value: {sfx_info}")
                    
                    # Check for rate limit in narration response
                    if "429" in narration or "quota exceeded" in narration.lower() or "rate limit" in narration.lower():
                        print("⏱️  Rate limit detected - playing cooldown audio")
                        rate_limited = True
                    else:
                        print(f"📝 Narration: {narration[:80]}...")
                        if sfx_info:
                            print(f"🎵 SFX selected: {sfx_info['title']} (query: {sfx_info.get('query', 'N/A')})")
                        else:
                            print(f"⚠️  No SFX info in response")
                        
                        # Generate audio
                        audio_filename = f"narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                        tts_result = await session.call_tool("tts", {"text": narration, "output_file": audio_filename})
                        print(f"🎙️  TTS result: {tts_result.content[0].text if tts_result.content else 'No response'}")
                        
                        audio_path = SCREENSHOT_DIR / audio_filename
                        
                        # Wait a moment for file to be written
                        await asyncio.sleep(0.5)
                        
                        # Download/cache SFX
                        sfx_path = None
                        if sfx_info:
                            sfx_path = download_sfx(sfx_info['mp3'], sfx_info['title'])
                            if sfx_path:
                                print(f"✅ SFX downloaded: {sfx_path}")
                            else:
                                print(f"❌ SFX download failed")
                        
                        # Add to audio queue
                        if audio_path.exists():
                            with audio_lock:
                                audio_queue.append({"audio_path": audio_path, "sfx_path": sfx_path})
                            print(f"✅ Audio ready ({len(audio_queue)} in queue)")
                        else:
                            print(f"⚠️  Audio file not found: {audio_path}")
                    
        except Exception as e:
            error_str = str(e)
            # Check if it's a rate limit error
            if "429" in error_str or "quota exceeded" in error_str.lower() or "rate limit" in error_str.lower():
                print("⏱️  Rate limit detected - playing cooldown audio")
                rate_limited = True
            # Suppress expected cleanup errors
            elif any(x in error_str for x in ["Process group termination", "TaskGroup", "Operation not permitted"]):
                pass  # Expected during cleanup, ignore silently
            else:
                print(f"❌ Error: {e}")
        
        # Play cooldown audio if rate limited
        if rate_limited:
            cooldown_audio = COOLDOWN_AUDIO_EXPLICIT if EXPLICIT else COOLDOWN_AUDIO_NICE
            if cooldown_audio.exists():
                with audio_lock:
                    audio_queue.append({"audio_path": cooldown_audio, "sfx_path": None})
                print(f"🔊 Cooldown audio queued")
            else:
                print(f"⚠️  Cooldown audio not found: {cooldown_audio}")
        
        # Release singleton flag
        is_generating_narration = False

async def play_audio_pipeline():
    """Pipeline: Play audio as soon as it's ready"""
    global is_playing_audio
    
    print("🎧 Audio playback pipeline started")
    
    while True:
        # Wait if no audio ready OR currently playing
        if not audio_queue:
            await asyncio.sleep(0.5)
            continue
        
        if is_playing_audio:
            print(f"⏸️  Waiting for current playback to finish...")
            await asyncio.sleep(0.5)
            continue
        
        print(f"🎵 Audio queue has {len(audio_queue)} item(s), is_playing={is_playing_audio}")
        
        # Get next audio to play
        with audio_lock:
            if not audio_queue:
                continue
            audio_item = audio_queue.pop(0)
        
        audio_path = audio_item["audio_path"]
        sfx_path = audio_item["sfx_path"]
        
        print(f"🎬 Playing: narration={audio_path.name}, sfx={sfx_path.name if sfx_path else 'None'}")
        
        is_playing_audio = True
        print(f"🔒 Playback lock acquired (is_playing={is_playing_audio})")
        
        try:
            # Play narration first, then SFX
            print(f"🎵 Playing narration...")
            await asyncio.to_thread(play_audio, audio_path)
            
            # Then play sound effect after narration finishes (max 5 seconds)
            if sfx_path:
                if sfx_path.exists():
                    print(f"🎵 Playing sound effect: {sfx_path.name} (max 5s)...")
                    await asyncio.to_thread(play_audio, sfx_path, 5.0)
                else:
                    print(f"⚠️  SFX file not found: {sfx_path}")
            else:
                print(f"ℹ️  No SFX for this narration")
            
            print(f"✅ Audio playback completed")
        except Exception as e:
            print(f"❌ Error playing audio: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Small delay to ensure audio is fully finished
            await asyncio.sleep(0.3)
            is_playing_audio = False
            print(f"🔓 Playback lock released (is_playing={is_playing_audio})")
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
            [python_cmd, "../minecraft_receiver.py"],
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
