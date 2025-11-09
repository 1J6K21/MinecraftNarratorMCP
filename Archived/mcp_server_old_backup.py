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
from tool_definitions import ToolDefinitions
from tool_handlers import ToolHandlers
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
    #view all tools that are definied in tool_definitions.py
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
        screenshots = get_last_screenshots(SCREENSHOT_DIR, 2)
        
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
            screenshots = get_last_screenshots(SCREENSHOT_DIR, image_count)
        
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

Generate 1-2 sentences of funny, sarcastic narration (like a sports commentator or David Attenborough). Be brief and entertaining. Be insulting, personal, and dont hold back comments, dark humor encouraged. Make sure to overly use words like dumbass, refere to the subject as 'this fucker' and for other words use this word bank: [birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso]"""
        
        response = gemini_model.generate_content(prompt)
        narration = response.text
        return [TextContent(type="text", text=narration)]
    
    elif name == "describe_for_narration":
        image_count = arguments.get("image_count", 2)
        include_minecraft = arguments.get("include_minecraft", False)
        
        # Get screenshots if requested
        screenshots = []
        if image_count > 0:
            screenshots = get_last_screenshots(SCREENSHOT_DIR, image_count)
        
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
            prompt = f"""Look at these two screenshots (FIRST is older, SECOND is MOST RECENT) and these Minecraft events: {minecraft_context}

Focus on what's happening in the SECOND (newest) screenshot. Generate ONE SHORT sentence of funny, sarcastic narration about the CURRENT activity. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile,fatass, fatso. KEEP IT BRIEF - ONE SENTENCE ONLY.

Then on a new line, write "SFX:" followed by ONE WORD that would make the best comedic sound effect for this narration (like: crash, laugh, explosion, scream, bell, drum, bruh, oof, etc).

Format:
[narration sentence]
SFX: [word]"""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 2:
            # Only screenshots
            prompt = """Look at these two screenshots (FIRST is older, SECOND is MOST RECENT).

Focus on what's happening in the SECOND (newest) screenshot. Generate ONE SHORT sentence of funny, sarcastic narration about the CURRENT activity. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso. KEEP IT BRIEF - ONE SENTENCE ONLY.

Then on a new line, write "SFX:" followed by ONE WORD that would make the best comedic sound effect for this narration (like: crash, laugh, explosion, scream, bell, drum, bruh, oof, etc).

Format:
[narration sentence]
SFX: [word]"""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 1 and minecraft_context:
            # Single screenshot with Minecraft data
            prompt = f"""Look at this screenshot and these Minecraft events: {minecraft_context}

Generate ONE SHORT sentence of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso. KEEP IT BRIEF - ONE SENTENCE ONLY.

Then on a new line, write "SFX:" followed by ONE WORD that would make the best comedic sound effect for this narration (like: crash, laugh, explosion, scream, bell, drum, bruh, oof, etc).

Format:
[narration sentence]
SFX: [word]"""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        elif len(screenshots) == 1:
            # Only single screenshot
            prompt = """Look at this screenshot.

Generate ONE SHORT sentence of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso. KEEP IT BRIEF - ONE SENTENCE ONLY.

Then on a new line, write "SFX:" followed by ONE WORD that would make the best comedic sound effect for this narration (like: crash, laugh, explosion, scream, bell, drum, bruh, oof, etc).

Format:
[narration sentence]
SFX: [word]"""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        else:
            # Only Minecraft data
            prompt = f"""Based on these Minecraft events: {minecraft_context}

Generate ONE SHORT sentence of funny, sarcastic narration. Be a sports commentator or David Attenborough. Be insulting, personal, dark humor encouraged. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso. KEEP IT BRIEF - ONE SENTENCE ONLY.

Then on a new line, write "SFX:" followed by ONE WORD that would make the best comedic sound effect for this narration (like: crash, laugh, explosion, scream, bell, drum, bruh, oof, etc).

Format:
[narration sentence]
SFX: [word]"""
            content.append(prompt)
        
        response = gemini_model.generate_content(content)
        response_text = response.text.strip()
        
        # Parse the response to extract narration and SFX keyword
        # Format: "[narration]\nSFX: [word]"
        if "SFX:" in response_text:
            parts = response_text.split("SFX:")
            narration = parts[0].strip()
            sfx_query = parts[1].strip().lower()
            # Clean up the keyword
            sfx_query = sfx_query.replace('"', '').replace("'", '').replace('.', '').replace(',', '').strip()
            if ' ' in sfx_query:
                sfx_query = sfx_query.split()[0]
            print(f"🎯 AI selected SFX keyword: '{sfx_query}'")
        else:
            # Fallback if format not followed
            narration = response_text
            sfx_query = get_sfx_query_from_narration(narration)
        
        # Using MyInstants API: https://github.com/abdipr/myinstants-api
        # Sounds from MyInstants.com (used with attribution for non-commercial purposes)
        
        try:
            # Search for sound effect
            sfx_response = requests.get(
                "https://myinstants-api.vercel.app/search",
                params={"q": sfx_query},
                timeout=10
            )
            sfx_response.raise_for_status()
            sfx_data = sfx_response.json()
            
            # Pick a random sound effect from results for variety
            if "data" in sfx_data and sfx_data["data"]:
                import random
                # Get up to 10 results and pick one randomly
                available_sounds = sfx_data["data"][:10]
                sfx_info = random.choice(available_sounds)
                
                print(f"🎲 Randomly selected: '{sfx_info.get('title')}' from {len(available_sounds)} options")
                
                # Return narration with SFX info as JSON
                result = {
                    "narration": narration,
                    "sfx": {
                        "title": sfx_info.get("title", "Unknown"),
                        "mp3": sfx_info.get("mp3", ""),
                        "url": sfx_info.get("url", ""),
                        "query": sfx_query
                    }
                }
                return [TextContent(type="text", text=json.dumps(result))]
            else:
                # No SFX found, return just narration
                result = {
                    "narration": narration,
                    "sfx": None
                }
                return [TextContent(type="text", text=json.dumps(result))]
        except Exception as e:
            # If SFX lookup fails, return just narration
            result = {
                "narration": narration,
                "sfx": None
            }
            return [TextContent(type="text", text=json.dumps(result))]
    
    elif name == "summarize_narrations":
        narrations = arguments["narrations"]
        
        if len(narrations) == 1:
            # Just return the single narration
            return [TextContent(type="text", text=narrations[0])]
        
        # Combine all narrations and ask Gemini to summarize
        all_narrations = "\n".join([f"- {n}" for n in narrations])
        
        prompt = f"""Here are {len(narrations)} narration sentences about what someone has been doing:

{all_narrations}

Combine ALL the key information into ONE SHORT, funny, sarcastic sentence. Keep the insulting tone and dark humor. Use words like: dumbass, this fucker, birdbrain, asshole, bimbo, bonehead, cocksucker, cunt, wanker, dick, dipshit, dork, fatso, pisser, turd, twat, wimp, wuss, bozo, buffoon, moron, goon, imbecile, fatass, fatso. 

ONE SENTENCE ONLY that captures everything important."""
        
        response = gemini_model.generate_content(prompt)
        summary = response.text
        return [TextContent(type="text", text=summary)]
    
    elif name == "get_sfx":
        query = arguments["query"]
        limit = arguments.get("limit", 3)
        
        try:
            # Search MyInstants API
            response = requests.get(
                "https://myinstants-api.vercel.app/search",
                params={"q": query},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract sound effects (API uses "data" key)
            if "data" in data and data["data"]:
                sounds = data["data"][:limit]
                result = []
                for sound in sounds:
                    result.append({
                        "title": sound.get("title", "Unknown"),
                        "mp3": sound.get("mp3", ""),
                        "url": sound.get("url", "")
                    })
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                return [TextContent(type="text", text=f"No sound effects found for: {query}")]
                
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching sound effects: {str(e)}")]
    
    elif name == "tts":
        text = arguments["text"]
        output_file = arguments.get("output_file", "narration.mp3")
        output_path = SCREENSHOT_DIR / output_file
        
        # Cleanup old audio files first
        cleanup_old_audio(SCREENSHOT_DIR, 2)
        
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
"""

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
