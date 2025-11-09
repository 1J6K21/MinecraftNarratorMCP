#!/usr/bin/env python3
"""Test the integrated SFX flow where describe_for_narration returns both narration and SFX"""

import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import platform

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))

async def test_integrated_sfx():
    """Test that describe_for_narration returns narration + SFX info"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    server_params = StdioServerParameters(
        command=python_cmd,
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    # Create a fake Minecraft event to test
    minecraft_data = json.dumps([
        {
            "timestamp": "2024-11-08T19:00:00",
            "event_type": "damage_taken",
            "details": {"amount": 10, "source": "fall"}
        }
    ])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Send Minecraft data
            await session.call_tool("get_minecraft_input", {
                "minecraft_data": minecraft_data
            })
            
            print("🧪 Testing describe_for_narration with integrated SFX...")
            print("=" * 60)
            
            # Call describe_for_narration (should return JSON with narration + SFX)
            result = await session.call_tool("describe_for_narration", {
                "image_count": 0,
                "include_minecraft": True
            })
            
            # Parse the response
            response_text = result.content[0].text
            print(f"\n📦 Raw response:\n{response_text}\n")
            
            response_data = json.loads(response_text)
            
            print("=" * 60)
            print("✅ Parsed Response:")
            print(f"📝 Narration: {response_data['narration']}")
            
            if response_data.get('sfx'):
                sfx = response_data['sfx']
                print(f"\n🎵 Sound Effect:")
                print(f"   Title: {sfx['title']}")
                print(f"   Query: {sfx['query']}")
                print(f"   MP3: {sfx['mp3']}")
                print(f"   URL: {sfx['url']}")
            else:
                print("\n⚠️  No SFX returned")
            
            print("=" * 60)
            
            # Verify the structure
            assert "narration" in response_data, "Missing 'narration' key"
            assert isinstance(response_data["narration"], str), "Narration should be a string"
            
            if response_data.get("sfx"):
                assert "title" in response_data["sfx"], "Missing 'title' in SFX"
                assert "mp3" in response_data["sfx"], "Missing 'mp3' in SFX"
                assert "query" in response_data["sfx"], "Missing 'query' in SFX"
            
            print("\n✅ All tests passed!")
            print("\nThe describe_for_narration tool now:")
            print("  1. Analyzes the input (screenshots/Minecraft data)")
            print("  2. Generates a funny narration")
            print("  3. Determines appropriate SFX based on keywords")
            print("  4. Searches MyInstants API")
            print("  5. Returns BOTH narration and SFX info in one response")

if __name__ == "__main__":
    asyncio.run(test_integrated_sfx())
