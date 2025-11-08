#!/usr/bin/env python3
"""
Screenshot Client
Takes screenshots every 5 seconds and uses MCP to generate narrated audio
"""

import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
INTERVAL = 5  # seconds

def take_screenshot():
    """Take a screenshot and save to directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
    
    # macOS screenshot command
    subprocess.run(["screencapture", "-x", str(filename)], check=True)
    print(f"📸 Screenshot saved: {filename}")
    return filename

def play_audio(audio_file: Path):
    """Play audio file using macOS afplay"""
    if audio_file.exists():
        print(f"🔊 Playing audio: {audio_file}")
        subprocess.run(["afplay", str(audio_file)])

async def process_screenshots():
    """Use MCP to process screenshots and generate narration"""
    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Get screenshots
            print("📋 Getting screenshots...")
            result = await session.call_tool("get_screenshot", {})
            print(result.content[0].text)
            
            # Describe changes
            print("🔍 Describing changes...")
            result = await session.call_tool("describe", {"image_count": 2})
            description = result.content[0].text
            print(f"Description: {description}")
            
            # Generate narration
            print("🎭 Generating funny narration...")
            result = await session.call_tool("narrate", {"description": description})
            narration = result.content[0].text
            print(f"Narration: {narration}")
            
            # Convert to speech
            print("🎤 Converting to speech...")
            audio_filename = f"narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            result = await session.call_tool("tts", {
                "text": narration,
                "output_file": audio_filename
            })
            print(result.content[0].text)
            
            # Play the audio
            audio_path = SCREENSHOT_DIR / audio_filename
            play_audio(audio_path)

async def main():
    """Main loop: take screenshots and process them"""
    print("🚀 Screenshot Narrator Client Started")
    print(f"📁 Screenshots directory: {SCREENSHOT_DIR}")
    print(f"⏱️  Taking screenshots every {INTERVAL} seconds")
    print("Press Ctrl+C to stop\n")
    
    screenshot_count = 0
    
    try:
        while True:
            # Take screenshot
            take_screenshot()
            screenshot_count += 1
            
            # Process every 2 screenshots (so we have before/after)
            if screenshot_count >= 2:
                print("\n" + "="*50)
                print("🎬 Processing screenshots...")
                print("="*50)
                
                try:
                    await process_screenshots()
                except Exception as e:
                    print(f"❌ Error processing: {e}")
                
                print("\n" + "="*50 + "\n")
            
            # Wait for next screenshot
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopping screenshot narrator...")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
