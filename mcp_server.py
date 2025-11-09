#!/usr/bin/env python3
"""
Narrator MCP Server
Takes screenshots, describes changes, generates funny narration, and converts to speech

Sound Effects Attribution:
- MyInstants API: https://github.com/abdipr/myinstants-api (by abdiputranar)
- MyInstants.com: https://www.myinstants.com
Sounds obtained via web scraping. Used with attribution for non-commercial purposes.
"""

import os
import glob
import base64
import json
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent
from mcp_utilities import (
    cleanup_old_screenshots,
    cleanup_old_audio,
    encode_image,
    get_sfx_query_from_narration,
    get_last_screenshots
)
from mcp_tool_utils import ToolDefinitions, ToolHandlers
import mcp.server.stdio
from PIL import Image
import subprocess
from elevenlabs import ElevenLabs
import requests

# Initialize clients for API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-2.5-flash')
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Screenshot directory - created at runtime if it doesn't exist
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
MAX_SCREENSHOTS = 5

# Minecraft mod data storage - file created by minecraft_receiver.py when events arrive
MINECRAFT_DATA_FILE = SCREENSHOT_DIR / "minecraft_data.json"

app = Server("narrator")

# Initialize tool handlers
handlers = ToolHandlers(
    screenshot_dir=SCREENSHOT_DIR,
    max_screenshots=MAX_SCREENSHOTS,
    gemini_model=gemini_model,
    elevenlabs_client=elevenlabs_client,
    minecraft_data_file=MINECRAFT_DATA_FILE
)

# Describe tools given to the LLM
@app.list_tools()
async def list_tools() -> list[Tool]:
    """View all tools that are defined in tool_definitions.py"""
    return ToolDefinitions.get_all_tools()

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Dispatch tool calls to appropriate handlers"""
    # Map tool names to handler methods
    tool_map = {
        "get_screenshot": handlers.handle_get_screenshot,
        "get_minecraft_input": handlers.handle_get_minecraft_input,
        "describe": handlers.handle_describe,
        "narrate": handlers.handle_narrate,
        "describe_for_narration": handlers.handle_describe_for_narration,
        "summarize_narrations": handlers.handle_summarize_narrations,
        "get_sfx": handlers.handle_get_sfx,
        "tts": handlers.handle_tts
    }
    
    # Dispatch to appropriate handler
    handler = tool_map.get(name)
    if handler:
        return await handler(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
