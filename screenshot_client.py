#!/usr/bin/env python3
"""
Screenshot Client
Takes screenshots every 10 seconds and uses MCP to generate narrated audio
Processes descriptions in background while audio plays
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
from PIL import ImageGrab

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
INTERVAL = 10  # seconds

# Global state for batching narrations
narration_queue = []
is_playing_audio = False
queue_lock = threading.Lock()

def take_screenshot():
    """Take a screenshot and save to directory (cross-platform)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
    
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["screencapture", "-x", str(filename)], check=True)
    elif system == "Windows":
        # Use PIL ImageGrab for Windows
        screenshot = ImageGrab.grab()
        screenshot.save(filename)
    else:  # Linux
        # Try using scrot or gnome-screenshot
        try:
            subprocess.run(["scrot", str(filename)], check=True)
        except FileNotFoundError:
            try:
                subprocess.run(["gnome-screenshot", "-f", str(filename)], check=True)
            except FileNotFoundError:
                # Fallback to PIL
                screenshot = ImageGrab.grab()
                screenshot.save(filename)
    
    print(f"📸 Screenshot saved: {filename}")
    return filename

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

def play_audio(audio_file: Path):
    """Play audio file (cross-platform, no window on Windows)"""
    if not audio_file.exists():
        return
    
    print(f"🔊 Playing audio: {audio_file}")
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", str(audio_file)])
    elif system == "Windows":
        # Use Windows Media Player command line (hidden, synchronous)
        try:
            # Use PowerShell to play MP3 with Windows Media Player (no window)
            subprocess.run([
                "powershell", "-WindowStyle", "Hidden", "-Command",
                f"Add-Type -AssemblyName presentationCore; "
                f"$mediaPlayer = New-Object System.Windows.Media.MediaPlayer; "
                f"$mediaPlayer.Open('{audio_file.absolute()}'); "
                f"$mediaPlayer.Play(); "
                f"Start-Sleep -Seconds ([int]($mediaPlayer.NaturalDuration.TimeSpan.TotalSeconds + 1))"
            ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except:
            # Fallback: use playsound
            try:
                from playsound import playsound
                playsound(str(audio_file), block=True)
            except:
                print("⚠️  Could not play audio silently")
    else:  # Linux
        # Try various Linux audio players
        for player in ["paplay", "mpg123", "ffplay", "aplay"]:
            try:
                subprocess.run([player, str(audio_file)], check=True)
                break
            except FileNotFoundError:
                continue

async def generate_narration(include_minecraft=False):
    """Generate narration for current screenshots (runs in background)"""
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
                
                # Get screenshots
                result = await session.call_tool("get_screenshot", {})
                
                # Check for Minecraft data
                minecraft_data_file = SCREENSHOT_DIR / "minecraft_data.json"
                if include_minecraft and minecraft_data_file.exists():
                    with open(minecraft_data_file, 'r') as f:
                        minecraft_data = f.read()
                    await session.call_tool("get_minecraft_input", {
                        "minecraft_data": minecraft_data
                    })
                
                # Use combined describe_for_narration tool (faster - one API call)
                # This now returns JSON with narration + SFX info
                result = await session.call_tool("describe_for_narration", {
                    "image_count": 2,
                    "include_minecraft": include_minecraft
                })
                
                # Parse JSON response
                response_data = json.loads(result.content[0].text)
                narration = response_data["narration"]
                sfx_info = response_data.get("sfx")
                
                # Add to queue with SFX info
                with queue_lock:
                    narration_queue.append({
                        "narration": narration,
                        "sfx": sfx_info
                    })
                    sfx_text = f" (SFX: {sfx_info['query']})" if sfx_info else ""
                    print(f"📝 Narration queued ({len(narration_queue)} in queue): {narration[:50]}...{sfx_text}")
                
    except Exception as e:
        print(f"❌ Error generating narration: {e}")

async def process_audio_queue():
    """Process queued narrations and play audio"""
    global is_playing_audio
    
    while True:
        # Wait if no narrations queued
        if not narration_queue:
            await asyncio.sleep(1)
            continue
        
        # Get ALL queued narrations
        with queue_lock:
            if not narration_queue:
                continue
            batch_items = narration_queue.copy()
            narration_queue.clear()
        
        # Extract narrations and get first SFX (they should all be similar)
        batch_narrations = [item["narration"] for item in batch_items]
        sfx_info = batch_items[0].get("sfx") if batch_items else None
        
        print(f"\n{'='*50}")
        print(f"🎤 Summarizing {len(batch_narrations)} narration(s) into one sentence...")
        if sfx_info:
            print(f"🎵 SFX selected: {sfx_info['title']} ({sfx_info['query']})")
        print(f"{'='*50}")
        
        # Generate audio
        is_playing_audio = True
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
                    
                    # Use summarize_narrations tool to condense all into one sentence
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
                    
                    audio_path = SCREENSHOT_DIR / audio_filename
                    
                # Download sound effect if available
                sfx_path = None
                if sfx_info:
                    print(f"📥 Downloading SFX: {sfx_info['title']}")
                    sfx_path = download_sfx(sfx_info['mp3'], f"sfx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                
                # Play both audio files in parallel for faster playback
                if audio_path.exists():
                    if sfx_path and sfx_path.exists():
                        print(f"🎵 Playing sound effect + narration...")
                        
                        # Start both audio files in parallel
                        sfx_task = asyncio.create_task(asyncio.to_thread(play_audio, sfx_path))
                        
                        # Small delay so SFX starts first, then start narration
                        await asyncio.sleep(0.1)
                        narration_task = asyncio.create_task(asyncio.to_thread(play_audio, audio_path))
                        
                        # Wait for both to complete
                        await asyncio.gather(sfx_task, narration_task)
                    else:
                        # No SFX, just play narration
                        print(f"🎵 Playing narration...")
                        await asyncio.to_thread(play_audio, audio_path)
                    
        except Exception as e:
            print(f"❌ Error processing audio: {e}")
        finally:
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
        time.sleep(1)  # Give it time to start
        print("🎮 Minecraft receiver started on port 8080")
        return receiver_process
    except Exception as e:
        print(f"⚠️  Could not start Minecraft receiver: {e}")
        return None

async def screenshot_loop(receiver_process):
    """Main loop: take screenshots and generate narrations in background"""
    minecraft_data_file = SCREENSHOT_DIR / "minecraft_data.json"
    screenshot_count = 0
    
    try:
        while True:
            # Take screenshot
            take_screenshot()
            screenshot_count += 1
            
            # Check if Minecraft data exists
            include_minecraft = minecraft_data_file.exists()
            
            # Process every 2 screenshots (so we have before/after)
            if screenshot_count >= 2:
                # Generate narration in background (doesn't block)
                asyncio.create_task(generate_narration(include_minecraft=include_minecraft))
            
            # Wait for next screenshot
            await asyncio.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopping screenshot narrator...")
        
        # Stop Minecraft receiver if we started it
        if receiver_process:
            print("🛑 Stopping Minecraft receiver...")
            receiver_process.terminate()
            receiver_process.wait()

async def main():
    """Main entry point"""
    print("🚀 Screenshot Narrator Client Started")
    print(f"📁 Screenshots directory: {SCREENSHOT_DIR}")
    print(f"⏱️  Taking screenshots every {INTERVAL} seconds")
    print("📝 Narrations are queued and batched while audio plays")
    print("\n🎵 Sound Effects: MyInstants API (https://github.com/abdipr/myinstants-api)")
    print("   Sounds from MyInstants.com - Used with attribution")
    
    # Start Minecraft receiver automatically
    receiver_process = start_minecraft_receiver()
    
    print("\nPress Ctrl+C to stop\n")
    
    # Run both loops concurrently
    await asyncio.gather(
        screenshot_loop(receiver_process),
        process_audio_queue()
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
