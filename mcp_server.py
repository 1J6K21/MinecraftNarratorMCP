#!/usr/bin/env python3
"""
Screenshot Narrator MCP Server
Takes screenshots, describes changes, generates funny narration, and converts to speech
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

# Minecraft mod data storage
MINECRAFT_DATA_FILE = SCREENSHOT_DIR / "minecraft_data.json"
last_minecraft_data = None

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
            name="get_minecraft_input",
            description="Get Minecraft mod input data (damage, blocks placed/broken, biome, day/night cycle)",
            inputSchema={
                "type": "object",
                "properties": {
                    "minecraft_data": {
                        "type": "string",
                        "description": "JSON string containing Minecraft events"
                    }
                },
                "required": ["minecraft_data"]
            }
        ),
        Tool(
            name="describe",
            description="Describes changes from screenshots and/or Minecraft mod data. At least one input required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_count": {
                        "type": "number",
                        "description": "Number of images to analyze (0, 1, or 2)",
                        "default": 2
                    },
                    "include_minecraft": {
                        "type": "boolean",
                        "description": "Include Minecraft mod data in description",
                        "default": False
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
            name="describe_for_narration",
            description="Combined tool: analyzes screenshots/Minecraft data and generates narration in one step (faster)",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_count": {
                        "type": "number",
                        "description": "Number of images to analyze (0, 1, or 2)",
                        "default": 2
                    },
                    "include_minecraft": {
                        "type": "boolean",
                        "description": "Include Minecraft mod data in narration",
                        "default": False
                    }
                },
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
    
    elif name == "get_minecraft_input":
        global last_minecraft_data
        minecraft_data_str = arguments.get("minecraft_data", "{}")
        
        try:
            current_data = json.loads(minecraft_data_str)
            
            # Save current data
            with open(MINECRAFT_DATA_FILE, 'w') as f:
                json.dump(current_data, f)
            
            # Calculate diff if we have previous data
            diff_info = ""
            if last_minecraft_data:
                diff_info = f"\nPrevious: {json.dumps(last_minecraft_data)}\nCurrent: {json.dumps(current_data)}"
            else:
                diff_info = f"\nFirst data: {json.dumps(current_data)}"
            
            last_minecraft_data = current_data
            
            return [TextContent(type="text", text=f"Minecraft data received{diff_info}")]
        except json.JSONDecodeError:
            return [TextContent(type="text", text="Invalid JSON data")]
    
    elif name == "describe":
        image_count = arguments.get("image_count", 2)
        include_minecraft = arguments.get("include_minecraft", False)
        
        # Get screenshots if requested
        screenshots = []
        if image_count > 0:
            screenshots = get_last_screenshots(image_count)
        
        # Get Minecraft data if requested
        minecraft_context = ""
        if include_minecraft and last_minecraft_data:
            minecraft_context = f"\n\nMinecraft events: {json.dumps(last_minecraft_data)}"
        
        # Validate at least one input
        if not screenshots and not minecraft_context:
            return [TextContent(type="text", text="No data available. Need screenshots or Minecraft data.")]
        
        # Build prompt for Gemini - integrate both sources when available
        content = []
        
        if len(screenshots) == 2 and minecraft_context:
            # Both screenshots and Minecraft data
            prompt = f"""In 1-2 sentences, describe in detail what is happening by combining:
1. In sequence the visuals of the two screenshots (first is older, second is newer)
2. Minecraft gameplay events: {minecraft_context}

Connect the on-screen activity with the in-game actions to tell a cohesive story."""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 2:
            # Only screenshots
            prompt = "In 1-2 sentences, describe what is happening within the last two screenshots as a sequence in detail (first is older, second is newer)."
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 1 and minecraft_context:
            # Single screenshot with Minecraft data
            prompt = f"""In 1-2 sentences, describe in detail what's happening by combining:
1. What's visible in this screenshot
2. Minecraft gameplay events: {minecraft_context}

Connect the visual with the gameplay."""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        elif len(screenshots) == 1:
            # Only single screenshot
            prompt = "In 1-2 sentences, describe in detail what's happening in this screenshot."
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        else:
            # Only Minecraft data
            prompt = f"In 1-2 sentences, describe these Minecraft events:{minecraft_context}"
            content.append(prompt)
        
        response = gemini_model.generate_content(content)
        description = response.text
        return [TextContent(type="text", text=description)]
    
    elif name == "narrate":
        description = arguments["description"]
        
        prompt = f"""Based on this: {description}

Generate 1-2 sentences of funny, sarcastic narration (like a sports commentator or David Attenborough). Be brief and entertaining. Be insulting, personal, and dont hold back comments, dark humor encouraged. Make sure to overly use words like dumbass, refere to the subject as 'this fucker' and for other words use this word bank: [birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile]"""
        
        response = gemini_model.generate_content(prompt)
        narration = response.text
        return [TextContent(type="text", text=narration)]
    
    elif name == "describe_for_narration":
        image_count = arguments.get("image_count", 2)
        include_minecraft = arguments.get("include_minecraft", False)
        
        # Get screenshots if requested
        screenshots = []
        if image_count > 0:
            screenshots = get_last_screenshots(image_count)
        
        # Get Minecraft data if requested
        minecraft_context = ""
        if include_minecraft and last_minecraft_data:
            minecraft_context = f"\n\nMinecraft events: {json.dumps(last_minecraft_data)}"
        
        # Validate at least one input
        if not screenshots and not minecraft_context:
            return [TextContent(type="text", text="No data available. Need screenshots or Minecraft data.")]
        
        # Build combined prompt for Gemini (describe + narrate in one call)
        content = []
        
        if len(screenshots) == 2 and minecraft_context:
            # Both screenshots and Minecraft data
            prompt = f"""Look at these two screenshots (first is older, second is newer) and these Minecraft events: {minecraft_context}

Generate 1-2 sentences of funny, sarcastic narration about what's happening. Be a sports commentator or David Attenborough narrating this person's mundane activities. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile."""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 2:
            # Only screenshots
            prompt = """Look at these two screenshots (first is older, second is newer).

Generate 1-2 sentences of funny, sarcastic narration about what changed. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile."""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 1 and minecraft_context:
            # Single screenshot with Minecraft data
            prompt = f"""Look at this screenshot and these Minecraft events: {minecraft_context}

Generate 1-2 sentences of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile."""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        elif len(screenshots) == 1:
            # Only single screenshot
            prompt = """Look at this screenshot.

Generate 1-2 sentences of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile."""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        else:
            # Only Minecraft data
            prompt = f"""Based on these Minecraft events: {minecraft_context}

Generate 1-2 sentences of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile."""
            content.append(prompt)
        
        response = gemini_model.generate_content(content)
        narration = response.text
        return [TextContent(type="text", text=narration)]
    
    elif name == "tts":
        text = arguments["text"]
        output_file = arguments.get("output_file", "narration.mp3")
        output_path = SCREENSHOT_DIR / output_file
        
        # Cleanup old audio files first
        cleanup_old_audio()
        
        # Use ElevenLabs TTS with custom voice ID and settings
        from elevenlabs import VoiceSettings
        
        try:
            audio = elevenlabs_client.text_to_speech.convert(
                voice_id="nPczCjzI2devNBz1zQrb",
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.10,  # 10% style exaggeration
                    use_speaker_boost=True
                )
            )
            
            # Save the audio as MP3
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
                    
        except Exception as e:
            # Fallback to macOS 'say' command if ElevenLabs fails (quota/credits)
            print(f"⚠️  ElevenLabs error: {e}")
            print("🔄 Falling back to macOS 'say' command...")
            output_path = output_path.with_suffix('.aiff')
            subprocess.run([
                "say",
                "-v", "Daniel",
                "-o", str(output_path),
                text
            ])
            return [TextContent(type="text", text=f"Audio saved (fallback): {output_path}")]
        
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
