#!/usr/bin/env python3
"""Test the full SFX integration flow"""

import asyncio
import os
import json
import requests
import subprocess
import platform
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)

def download_sfx(mp3_url: str, filename: str) -> Path:
    """Download sound effect from URL"""
    sfx_path = SCREENSHOT_DIR / filename
    try:
        print(f"📥 Downloading SFX...")
        response = requests.get(mp3_url, timeout=10)
        response.raise_for_status()
        with open(sfx_path, 'wb') as f:
            f.write(response.content)
        return sfx_path
    except Exception as e:
        print(f"❌ Failed to download SFX: {e}")
        return None

def play_audio(audio_file: Path):
    """Play audio file"""
    if not audio_file.exists():
        return
    
    print(f"🔊 Playing: {audio_file.name}")
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", str(audio_file)])

async def test_sfx_with_narration():
    """Test getting SFX based on narration content"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    server_params = StdioServerParameters(
        command=python_cmd,
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    # Test narrations with different keywords
    test_cases = [
        ("This dumbass just died falling off a cliff", "bruh"),
        ("Look at this moron laughing at his own joke", "laugh"),
        ("The idiot just blew up his entire house with TNT", "explosion"),
        ("Wow, this genius actually figured it out", "wow"),
    ]
    
    for narration, expected_query in test_cases:
        print(f"\n{'='*60}")
        print(f"📝 Narration: {narration}")
        print(f"🎯 Expected SFX type: {expected_query}")
        print(f"{'='*60}")
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Determine query based on keywords
                query = "bruh"
                narration_lower = narration.lower()
                
                if any(word in narration_lower for word in ["laugh", "funny", "hilarious", "joke"]):
                    query = "laugh"
                elif any(word in narration_lower for word in ["fail", "died", "death", "damage"]):
                    query = "bruh"
                elif any(word in narration_lower for word in ["explosion", "explode", "boom", "tnt"]):
                    query = "explosion"
                elif any(word in narration_lower for word in ["wow", "amazing", "incredible"]):
                    query = "wow"
                
                print(f"🔍 Searching for: {query}")
                
                # Get sound effect
                result = await session.call_tool("get_sfx", {
                    "query": query,
                    "limit": 1
                })
                
                sfx_data = json.loads(result.content[0].text)
                if sfx_data and len(sfx_data) > 0:
                    sfx_info = sfx_data[0]
                    print(f"✅ Found: {sfx_info['title']}")
                    
                    # Download and play
                    sfx_path = download_sfx(sfx_info['mp3'], f"test_{query}.mp3")
                    if sfx_path:
                        play_audio(sfx_path)
                        print(f"✅ Played successfully")
                else:
                    print(f"❌ No SFX found")
        
        await asyncio.sleep(1)

if __name__ == "__main__":
    print("🎵 Testing SFX Integration")
    print("This will play different sound effects based on narration content\n")
    asyncio.run(test_sfx_with_narration())
    print("\n✅ All tests complete!")
