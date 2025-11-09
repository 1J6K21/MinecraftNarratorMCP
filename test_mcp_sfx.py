#!/usr/bin/env python3
"""Test the get_sfx MCP tool"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import platform

load_dotenv()

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))

async def test_get_sfx():
    """Test the get_sfx tool"""
    python_cmd = "python" if platform.system() == "Windows" else "python3"
    
    server_params = StdioServerParameters(
        command=python_cmd,
        args=["mcp_server.py"],
        env={
            **os.environ,
            "SCREENSHOT_DIR": str(SCREENSHOT_DIR),
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Test various queries
            queries = ["bruh", "laugh", "explosion", "wow"]
            
            for query in queries:
                print(f"\n🔍 Testing query: {query}")
                result = await session.call_tool("get_sfx", {
                    "query": query,
                    "limit": 2
                })
                print(f"✅ Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test_get_sfx())
