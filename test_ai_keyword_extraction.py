#!/usr/bin/env python3
"""Test AI-powered keyword extraction for SFX selection"""

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

async def test_keyword_extraction():
    """Test that AI extracts good keywords from various narrations"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    server_params = StdioServerParameters(
        command=python_cmd,
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    # Test various Minecraft events to see what keywords AI extracts
    test_cases = [
        {
            "event": "damage_taken",
            "details": {"amount": 10, "source": "fall"}
        },
        {
            "event": "block_placed",
            "details": {"block": "tnt", "count": 5}
        },
        {
            "event": "damage_taken",
            "details": {"amount": 20, "source": "explosion"}
        },
        {
            "event": "biome_changed",
            "details": {"from": "plains", "to": "nether"}
        }
    ]
    
    print("🧪 Testing AI-Powered Keyword Extraction")
    print("=" * 70)
    print("This will generate narrations and let AI pick the best SFX keyword\n")
    
    for i, test_case in enumerate(test_cases, 1):
        minecraft_data = json.dumps([{
            "timestamp": "2024-11-08T19:00:00",
            "event_type": test_case["event"],
            "details": test_case["details"]
        }])
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Send Minecraft data
                await session.call_tool("get_minecraft_input", {
                    "minecraft_data": minecraft_data
                })
                
                print(f"\n{'='*70}")
                print(f"Test {i}: {test_case['event']} - {test_case['details']}")
                print(f"{'='*70}")
                
                # Call describe_for_narration
                result = await session.call_tool("describe_for_narration", {
                    "image_count": 0,
                    "include_minecraft": True
                })
                
                # Parse the response
                response_data = json.loads(result.content[0].text)
                
                print(f"\n📝 Narration: {response_data['narration']}")
                
                if response_data.get('sfx'):
                    sfx = response_data['sfx']
                    print(f"\n🎯 AI Keyword: '{sfx['query']}'")
                    print(f"🎵 Selected SFX: {sfx['title']}")
                    print(f"🔗 URL: {sfx['url']}")
                else:
                    print("\n⚠️  No SFX returned")
        
        await asyncio.sleep(1)
    
    print("\n" + "=" * 70)
    print("✅ Test complete!")
    print("\nThe AI now:")
    print("  1. Reads the narration")
    print("  2. Extracts the BEST single keyword for a sound effect")
    print("  3. Searches MyInstants with that keyword")
    print("  4. Randomly picks from the top 10 results")
    print("\nThis gives much more variety than 4 fixed categories!")

if __name__ == "__main__":
    asyncio.run(test_keyword_extraction())
