#!/usr/bin/env python3
"""
Demo: Complete SFX Integration
Shows how sound effects are automatically selected and played with narrations
"""

import asyncio
import os
import json
import requests
import subprocess
import platform
from pathlib import Path
from datetime import datetime
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
        response = requests.get(mp3_url, timeout=10)
        response.raise_for_status()
        with open(sfx_path, 'wb') as f:
            f.write(response.content)
        return sfx_path
    except Exception as e:
        print(f"⚠️  Failed to download SFX: {e}")
        return None

def play_audio(audio_file: Path):
    """Play audio file"""
    if not audio_file.exists():
        return
    
    system = platform.system()
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", str(audio_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def get_sfx_for_narration(narration: str):
    """Get appropriate sound effect based on narration content"""
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
                
                # Determine search query based on narration keywords
                query = "bruh"  # default
                narration_lower = narration.lower()
                
                if any(word in narration_lower for word in ["laugh", "funny", "hilarious", "joke"]):
                    query = "laugh"
                elif any(word in narration_lower for word in ["fail", "died", "death", "damage"]):
                    query = "bruh"
                elif any(word in narration_lower for word in ["explosion", "explode", "boom", "tnt"]):
                    query = "explosion"
                elif any(word in narration_lower for word in ["wow", "amazing", "incredible"]):
                    query = "wow"
                
                # Get sound effects
                result = await session.call_tool("get_sfx", {
                    "query": query,
                    "limit": 1
                })
                
                sfx_data = json.loads(result.content[0].text)
                if sfx_data and len(sfx_data) > 0:
                    return sfx_data[0], query
                return None, query
                
    except Exception as e:
        print(f"⚠️  Error getting SFX: {e}")
        return None, None

async def generate_tts(text: str):
    """Generate TTS audio"""
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
                
                audio_filename = f"demo_narration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                await session.call_tool("tts", {
                    "text": text,
                    "output_file": audio_filename
                })
                
                return SCREENSHOT_DIR / audio_filename
    except Exception as e:
        print(f"❌ Error generating TTS: {e}")
        return None

async def demo_narration_with_sfx(narration: str):
    """Demo: Play narration with automatic SFX"""
    print(f"\n{'='*70}")
    print(f"📝 Narration: {narration}")
    print(f"{'='*70}")
    
    # Get appropriate sound effect
    print(f"🔍 Analyzing narration for sound effects...")
    sfx_info, query = await get_sfx_for_narration(narration)
    
    if sfx_info:
        print(f"✅ Selected SFX category: '{query}'")
        print(f"🎵 Sound effect: {sfx_info['title']}")
        
        # Download SFX
        sfx_path = download_sfx(sfx_info['mp3'], f"demo_sfx_{datetime.now().strftime('%H%M%S')}.mp3")
        
        # Generate TTS
        print(f"🎤 Generating narration audio...")
        narration_path = await generate_tts(narration)
        
        if sfx_path and narration_path:
            # Play both in parallel for faster playback
            print(f"🔊 Playing sound effect + narration in parallel...")
            
            # Start SFX
            sfx_task = asyncio.create_task(asyncio.to_thread(play_audio, sfx_path))
            
            # Small delay so SFX starts first
            await asyncio.sleep(0.1)
            
            # Start narration (will overlap with SFX)
            narration_task = asyncio.create_task(asyncio.to_thread(play_audio, narration_path))
            
            # Wait for both to complete
            await asyncio.gather(sfx_task, narration_task)
            
            print(f"✅ Complete!")
        else:
            print(f"❌ Failed to generate audio")
    else:
        print(f"⚠️  No sound effect found")
    
    print()

async def main():
    """Run demo with various narration examples"""
    print("🎬 SFX Integration Demo")
    print("=" * 70)
    print("This demo shows how sound effects are automatically selected")
    print("and played based on narration content.")
    print("=" * 70)
    
    # Demo narrations showcasing different SFX categories
    narrations = [
        "This absolute dumbass just died falling into lava with all his diamonds.",
        "Look at this moron laughing at his own terrible joke.",
        "The idiot just blew up his entire base with TNT.",
        "Wow, this genius actually managed to beat the Ender Dragon on the first try!",
    ]
    
    for narration in narrations:
        await demo_narration_with_sfx(narration)
        await asyncio.sleep(1)
    
    print("=" * 70)
    print("✅ Demo complete!")
    print("\nThe system automatically:")
    print("  1. Analyzes narration keywords")
    print("  2. Selects appropriate sound effect category")
    print("  3. Searches MyInstants API")
    print("  4. Downloads the sound effect")
    print("  5. Plays SFX followed by narration")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
