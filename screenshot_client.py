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

def play_audio(audio_file: Path):
    """Play audio file (cross-platform, no window on Windows)"""
    if not audio_file.exists():
        return
    
    print(f"🔊 Playing audio: {audio_file}")
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", str(audio_file)])
    elif system == "Windows":
        # Use playsound for silent MP3 playback (no window)
        try:
            from playsound import playsound
            playsound(str(audio_file))
        except ImportError:
            print("⚠️  playsound not installed. Install with: pip install playsound")
            print("   Opening default player (may show window)...")
            os.startfile(str(audio_file))
            time.sleep(5)
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
                
                # Describe changes
                result = await session.call_tool("describe", {
                    "image_count": 2,
                    "include_minecraft": include_minecraft
                })
                description = result.content[0].text
                
                # Generate narration
                result = await session.call_tool("narrate", {"description": description})
                narration = result.content[0].text
                
                # Add to queue
                with queue_lock:
                    narration_queue.append(narration)
                    print(f"📝 Narration queued ({len(narration_queue)} in queue): {narration[:50]}...")
                
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
        
        # Get all queued narrations
        with queue_lock:
            if not narration_queue:
                continue
            batch_narrations = narration_queue.copy()
            narration_queue.clear()
        
        # Combine narrations
        combined_text = " ... ".join(batch_narrations)
        print(f"\n{'='*50}")
        print(f"🎤 Converting {len(batch_narrations)} narration(s) to speech...")
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
                    
                    audio_filename = f"narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                    result = await session.call_tool("tts", {
                        "text": combined_text,
                        "output_file": audio_filename
                    })
                    
                    # Play audio in separate thread to not block
                    audio_path = SCREENSHOT_DIR / audio_filename
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
    
    # Start Minecraft receiver automatically
    receiver_process = start_minecraft_receiver()
    
    print("Press Ctrl+C to stop\n")
    
    # Run both loops concurrently
    await asyncio.gather(
        screenshot_loop(receiver_process),
        process_audio_queue()
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
