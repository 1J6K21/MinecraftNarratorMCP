#!/usr/bin/env python3
"""
Screenshot Narrator MCP Server
Takes screenshots, describes changes, generates funny narration, and converts to speech
"""

import os
import glob
import base64
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent
import mcp.server.stdio
from PIL import Image
import subprocess
from elevenlabs import ElevenLabs

# Initialize clients
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-2.5-flash')
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Screenshot directory
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
MAX_SCREENSHOTS = 5

app = Server("screenshot-narrator")

def cleanup_old_screenshots():
    """Keep only the last MAX_SCREENSHOTS images"""
    screenshots = sorted(SCREENSHOT_DIR.glob("*.png"), key=os.path.getmtime)
    while len(screenshots) > MAX_SCREENSHOTS:
        oldest = screenshots.pop(0)
        oldest.unlink()

def cleanup_old_audio():
    """Keep only the last 2 audio files"""
    audio_files = sorted(SCREENSHOT_DIR.glob("*.mp3"), key=os.path.getmtime)
    while len(audio_files) > 2:
        oldest = audio_files.pop(0)
        oldest.unlink()

def get_last_screenshots(count: int = 2):
    """Get the last N screenshots from the directory"""
    screenshots = sorted(SCREENSHOT_DIR.glob("*.png"), key=os.path.getmtime, reverse=True)
    return screenshots[:count]

def encode_image(image_path: Path) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_screenshot",
            description="Gets the last two screenshots from the specified directory and returns them",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="describe",
            description="Describes what's in a screenshot. If 2 images are given, describes the changes between them",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_count": {
                        "type": "number",
                        "description": "Number of images to analyze (1 or 2)",
                        "default": 2
                    }
                },
            }
        ),
        Tool(
            name="narrate",
            description="Generates funny, insulting narration text based on the description of what changed",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "The description of changes to narrate"
                    }
                },
                "required": ["description"]
            }
        ),
        Tool(
            name="tts",
            description="Converts narration text to audio file with a funny voice and returns mp3",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to convert to speech"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Output filename for the mp3",
                        "default": "narration.mp3"
                    }
                },
                "required": ["text"]
            }
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    if name == "get_screenshot":
        cleanup_old_screenshots()
        screenshots = get_last_screenshots(2)
        
        if not screenshots:
            return [TextContent(type="text", text="No screenshots found")]
        
        result = [TextContent(type="text", text=f"Found {len(screenshots)} screenshot(s)")]
        for img in screenshots:
            result.append(TextContent(type="text", text=f"Screenshot: {img.name}"))
        
        return result
    
    elif name == "describe":
        image_count = arguments.get("image_count", 2)
        screenshots = get_last_screenshots(image_count)
        
        if not screenshots:
            return [TextContent(type="text", text="No screenshots available")]
        
        # Build prompt for Gemini
        if len(screenshots) == 2:
            prompt = "In 1-2 sentences, describe what changed between these screenshots (first is older, second is newer)."
            images = [Image.open(img) for img in reversed(screenshots)]
            response = gemini_model.generate_content([prompt] + images)
        else:
            prompt = "In 1-2 sentences, describe what's happening in this screenshot."
            image = Image.open(screenshots[0])
            response = gemini_model.generate_content([prompt, image])
        
        description = response.text
        return [TextContent(type="text", text=description)]
    
    elif name == "narrate":
        description = arguments["description"]
        
        prompt = f"""Based on this: {description}

Generate 1-2 sentences of funny, sarcastic narration (like a sports commentator or David Attenborough). Be brief and entertaining."""
        
        response = gemini_model.generate_content(prompt)
        narration = response.text
        return [TextContent(type="text", text=narration)]
    
    elif name == "tts":
        text = arguments["text"]
        output_file = arguments.get("output_file", "narration.mp3")
        output_path = SCREENSHOT_DIR / output_file
        
        # Cleanup old audio files first
        cleanup_old_audio()
        
        # Use ElevenLabs TTS with custom voice ID
        audio = elevenlabs_client.text_to_speech.convert(
            voice_id="nPczCjzI2devNBz1zQrb",
            text=text,
            model_id="eleven_multilingual_v2"
        )
        
        # Save the audio
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        
        return [TextContent(type="text", text=f"Audio saved to: {output_path}")]
    
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
