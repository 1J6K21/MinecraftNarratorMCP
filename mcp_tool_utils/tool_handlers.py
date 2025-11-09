#!/usr/bin/env python3
"""
MCP Tool Handlers
Implementation of tool actions for the Narrator MCP Server
"""

import json
import requests
from pathlib import Path
from typing import Optional
from PIL import Image
import google.generativeai as genai
from elevenlabs import ElevenLabs
from mcp.types import TextContent, ImageContent
from .utilities import (
    cleanup_old_screenshots,
    get_last_screenshots,
    cleanup_old_audio,
    get_sfx_query_from_narration
)


class ToolHandlers:
    """Handlers for all MCP tool implementations"""
    
    def __init__(
        self,
        screenshot_dir: Path,
        max_screenshots: int,
        gemini_model,
        elevenlabs_client: ElevenLabs,
        minecraft_data_file: Path
    ):
        self.screenshot_dir = screenshot_dir
        self.max_screenshots = max_screenshots
        self.gemini_model = gemini_model
        self.elevenlabs_client = elevenlabs_client
        self.minecraft_data_file = minecraft_data_file
        self.last_minecraft_data = None
    
    async def handle_get_screenshot(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Get the last screenshots"""
        cleanup_old_screenshots(self.screenshot_dir, self.max_screenshots)
        screenshots = get_last_screenshots(self.screenshot_dir, 2)
        
        if not screenshots:
            return [TextContent(type="text", text="No screenshots found")]
        
        result = [TextContent(type="text", text=f"Found {len(screenshots)} screenshot(s)")]
        for img in screenshots:
            result.append(TextContent(type="text", text=f"Screenshot: {img.name}"))
        
        return result
    
    async def handle_get_minecraft_input(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Receive and store Minecraft mod data"""
        minecraft_data_str = arguments.get("minecraft_data", "{}")
        
        try:
            current_data = json.loads(minecraft_data_str)
            
            # Save current data
            with open(self.minecraft_data_file, 'w') as f:
                json.dump(current_data, f)
            
            # Calculate diff if we have previous data
            diff_info = ""
            if self.last_minecraft_data:
                diff_info = f"\nPrevious: {json.dumps(self.last_minecraft_data)}\nCurrent: {json.dumps(current_data)}"
            else:
                diff_info = f"\nFirst data: {json.dumps(current_data)}"
            
            self.last_minecraft_data = current_data
            
            return [TextContent(type="text", text=f"Minecraft data received{diff_info}")]
        except json.JSONDecodeError:
            return [TextContent(type="text", text="Invalid JSON data")]
    
    async def handle_describe(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Describe changes from screenshots and/or Minecraft data"""
        image_count = arguments.get("image_count", 2)
        include_minecraft = arguments.get("include_minecraft", False)
        
        # Get screenshots if requested
        screenshots = []
        if image_count > 0:
            screenshots = get_last_screenshots(self.screenshot_dir, image_count)
        
        # Get Minecraft data if requested
        minecraft_context = ""
        if include_minecraft and self.last_minecraft_data:
            minecraft_context = f"\n\nMinecraft events: {json.dumps(self.last_minecraft_data)}"
        
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
        elif len(screenshots) == 1:
            # Single screenshot
            prompt = "In 1-2 sentences, describe what is happening in this screenshot in detail."
            if minecraft_context:
                prompt += f"\n\nMinecraft events: {minecraft_context}"
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        else:
            # Only Minecraft data
            prompt = f"In 1-2 sentences, describe what is happening based on these Minecraft events: {minecraft_context}"
            content.append(prompt)
        
        # Generate description
        response = self.gemini_model.generate_content(content)
        description = response.text.strip()
        
        return [TextContent(type="text", text=description)]
    
    async def handle_narrate(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Generate funny narration from description"""
        description = arguments["description"]
        
        prompt = f"Based on this description: '{description}'\n\nGenerate ONE sentence of funny, sarcastic sports-commentator-style narration. Be creative and entertaining!"
        response = self.gemini_model.generate_content(prompt)
        narration = response.text.strip()
        
        return [TextContent(type="text", text=narration)]

    async def handle_describe_for_narration(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Combined tool: analyze, narrate, and select SFX"""
        image_count = arguments.get("image_count", 2)
        include_minecraft = arguments.get("include_minecraft", False)
        
        # Get screenshots if requested
        screenshots = []
        if image_count > 0:
            screenshots = get_last_screenshots(self.screenshot_dir, image_count)
        
        # Get Minecraft data if requested
        minecraft_context = ""
        if include_minecraft and self.last_minecraft_data:
            minecraft_context = f"\n\nMinecraft events: {json.dumps(self.last_minecraft_data)}"
        
        # Validate at least one input
        if not screenshots and not minecraft_context:
            return [TextContent(type="text", text="No data available. Need screenshots or Minecraft data.")]
        
        # Build prompt for Gemini
        content = []
        
        if len(screenshots) == 2 and minecraft_context:
            prompt = f"""Analyze these two screenshots (first is older, second is newer) and Minecraft events: {minecraft_context}

Generate ONE sentence of funny, sarcastic sports-commentator-style narration about what's happening.
Then suggest ONE sound effect keyword that would be funny with this narration.

Respond in JSON format:
{{"narration": "your funny narration here", "sfx_keyword": "keyword"}}

Sound effect keywords: bruh, laugh, explosion, wow, scream, crash, fail, epic, oof, yeet"""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 2:
            prompt = """Analyze these two screenshots (first is older, second is newer).

Generate ONE sentence of funny, sarcastic sports-commentator-style narration about what's happening.
Then suggest ONE sound effect keyword that would be funny with this narration.

Respond in JSON format:
{"narration": "your funny narration here", "sfx_keyword": "keyword"}

Sound effect keywords: bruh, laugh, explosion, wow, scream, crash, fail, epic, oof, yeet"""
            content.append(prompt)
            images = [Image.open(img) for img in reversed(screenshots)]
            content.extend(images)
        elif len(screenshots) == 1:
            prompt = f"""Analyze this screenshot{minecraft_context and f' and Minecraft events: {minecraft_context}' or ''}.

Generate ONE sentence of funny, sarcastic sports-commentator-style narration about what's happening.
Then suggest ONE sound effect keyword that would be funny with this narration.

Respond in JSON format:
{{"narration": "your funny narration here", "sfx_keyword": "keyword"}}

Sound effect keywords: bruh, laugh, explosion, wow, scream, crash, fail, epic, oof, yeet"""
            content.append(prompt)
            content.append(Image.open(screenshots[0]))
        else:
            prompt = f"""Based on these Minecraft events: {minecraft_context}

Generate ONE sentence of funny, sarcastic sports-commentator-style narration about what's happening.
Then suggest ONE sound effect keyword that would be funny with this narration.

Respond in JSON format:
{{"narration": "your funny narration here", "sfx_keyword": "keyword"}}

Sound effect keywords: bruh, laugh, explosion, wow, scream, crash, fail, epic, oof, yeet"""
            content.append(prompt)
        
        # Generate narration + SFX keyword
        response = self.gemini_model.generate_content(content)
        response_text = response.text.strip()
        
        # Parse JSON response
        try:
            # Clean up markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(response_text)
            narration = data.get("narration", response_text)
            sfx_keyword = data.get("sfx_keyword", "bruh")
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            narration = response_text
            sfx_keyword = get_sfx_query_from_narration(narration)
        
        # Search for sound effect
        try:
            sfx_response = requests.get(
                "https://api.myinstants.com/v1/instants/search",
                params={"query": sfx_keyword, "limit": 1},
                timeout=5
            )
            sfx_data = sfx_response.json()
            
            if sfx_data.get("results"):
                sfx = sfx_data["results"][0]
                result = {
                    "narration": narration,
                    "sfx": {
                        "title": sfx.get("title", "Unknown"),
                        "mp3": sfx.get("sound", ""),
                        "query": sfx_keyword
                    }
                }
            else:
                result = {"narration": narration, "sfx": None}
        except Exception:
            result = {"narration": narration, "sfx": None}
        
        return [TextContent(type="text", text=json.dumps(result))]
    
    async def handle_summarize_narrations(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Summarize multiple narrations into one sentence"""
        narrations = arguments["narrations"]
        
        if len(narrations) == 1:
            return [TextContent(type="text", text=narrations[0])]
        
        prompt = f"""Summarize these {len(narrations)} narrations into ONE concise, funny sentence that captures the key action:

{chr(10).join(f'{i+1}. {n}' for i, n in enumerate(narrations))}

Keep the sarcastic sports-commentator style. ONE sentence only!"""
        
        response = self.gemini_model.generate_content(prompt)
        summary = response.text.strip()
        
        return [TextContent(type="text", text=summary)]
    
    async def handle_get_sfx(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Search for sound effects"""
        query = arguments["query"]
        limit = arguments.get("limit", 3)
        
        try:
            response = requests.get(
                "https://api.myinstants.com/v1/instants/search",
                params={"query": query, "limit": limit},
                timeout=5
            )
            data = response.json()
            
            if not data.get("results"):
                return [TextContent(type="text", text=f"No sound effects found for '{query}'")]
            
            results = []
            for sfx in data["results"]:
                results.append({
                    "title": sfx.get("title", "Unknown"),
                    "mp3": sfx.get("sound", ""),
                    "query": query
                })
            
            return [TextContent(type="text", text=json.dumps(results))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching sound effects: {str(e)}")]
    
    async def handle_tts(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Convert text to speech"""
        text = arguments["text"]
        output_file = arguments.get("output_file", "narration.mp3")
        
        # Cleanup old audio files first
        cleanup_old_audio(self.screenshot_dir, 2)
        
        # Use ElevenLabs TTS with custom voice ID and settings
        audio = self.elevenlabs_client.generate(
            text=text,
            voice="pNInz6obpgDQGcFmaJgB",  # Adam voice
            model="eleven_multilingual_v2"
        )
        
        # Save audio file
        output_path = self.screenshot_dir / output_file
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        
        return [TextContent(type="text", text=f"Audio saved to {output_file}")]
