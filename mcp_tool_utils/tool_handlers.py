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
        self.recent_sfx = []  # Sliding window of last 10 SFX IDs/titles
        self.max_recent_sfx = 10
    
    def _select_unique_sfx(self, available_sounds: list, max_attempts: int = 5) -> Optional[dict]:
        """
        Select a random SFX that hasn't been used recently.
        Uses sliding window to avoid repetition.
        
        Args:
            available_sounds: List of SFX dicts from API
            max_attempts: Maximum reroll attempts before giving up
        
        Returns:
            Selected SFX dict or None if all are recently used
        """
        import random
        
        if not available_sounds:
            return None
        
        # Try to find a unique SFX
        for attempt in range(max_attempts):
            sfx = random.choice(available_sounds)
            sfx_id = sfx.get("title", "")  # Use title as unique identifier
            
            # Check if this SFX was used recently
            if sfx_id not in self.recent_sfx:
                # Add to recent list
                self.recent_sfx.append(sfx_id)
                
                # Maintain sliding window size
                if len(self.recent_sfx) > self.max_recent_sfx:
                    self.recent_sfx.pop(0)
                
                print(f"🎲 Selected: '{sfx_id}' (attempt {attempt + 1}, {len(self.recent_sfx)} in history)")
                return sfx
        
        # If all attempts failed, just pick one and reset the window
        print(f"⚠️  All SFX recently used, resetting window")
        sfx = random.choice(available_sounds)
        self.recent_sfx = [sfx.get("title", "")]
        return sfx
    
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
        is_repetitive = arguments.get("is_repetitive", False)
        activity_mode = arguments.get("activity_mode", "unknown")
        
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
            # Check for repetitive activity
            repetition_context = ""
            if is_repetitive:
                repetition_context = f"""

IMPORTANT: The player has been doing '{activity_mode}' repeatedly! Instead of normal narration, pick ONE of these special modes:
1. SING: Make up a short silly song about their repetitive behavior (2 lines max)
2. THERAPY: Act like their therapist, asking why they keep doing this
3. DAD JOKE: Tell a dad joke related to their activity, then roast them with it
4. FUN FACT: Share a fun fact, then use it to roast them (e.g., "Did you know pigs don't shower? Does that make you a pig?")

Be creative and mean in a funny way, this is where you show your empathy, but you still dont hold back invasive comments!"""
            
            prompt = f"""Based on these Minecraft events: {minecraft_context}{repetition_context}

Generate ONE sentence of funny, sarcastic sports-commentator-style narration.
Then suggest ONE sound effect keyword.

Respond in JSON format:
{{"narration": "your funny narration here", "sfx_keyword": "keyword"}}

Sound effect keywords: bruh, laugh, explosion, wow, scream, crash, fail, epic, oof, yeet"""
            content.append(prompt)
        
        # Generate narration + SFX keyword
        response = self.gemini_model.generate_content(content)
        response_text = response.text.strip()
        
        print(f"🤖 Gemini response: {response_text[:100]}...")
        
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
            
            print(f"✅ Parsed JSON - narration: {narration[:50]}..., sfx: {sfx_keyword}")
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            print(f"⚠️  JSON parse failed: {e}, using fallback")
            narration = response_text
            sfx_keyword = get_sfx_query_from_narration(narration)
        
        # Search for sound effect
        try:
            print(f"🔍 Searching SFX for keyword: '{sfx_keyword}'")
            sfx_response = requests.get(
                "https://myinstants-api.vercel.app/search",
                params={"q": sfx_keyword},  # Note: parameter is 'q' not 'query'
                timeout=5
            )
            sfx_data = sfx_response.json()
            
            if sfx_data.get("data"):  # Note: key is 'data' not 'results'
                print(f"✅ Found {len(sfx_data['data'])} SFX options")
                # Use sliding window to select unique SFX
                available_sounds = sfx_data["data"]
                sfx = self._select_unique_sfx(available_sounds)
                
                if sfx:
                    result = {
                        "narration": narration,
                        "sfx": {
                            "title": sfx.get("title", "Unknown"),
                            "mp3": sfx.get("mp3", ""),
                            "query": sfx_keyword
                        }
                    }
                    print(f"🎵 Selected SFX: {sfx.get('title')} - URL: {sfx.get('mp3', 'NO URL')[:50]}")
                else:
                    print(f"⚠️  No unique SFX found")
                    result = {"narration": narration, "sfx": None}
            else:
                print(f"⚠️  No SFX results from API")
                result = {"narration": narration, "sfx": None}
        except Exception as e:
            print(f"❌ SFX search error: {e}")
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
                "https://myinstants-api.vercel.app/search",
                params={"q": query},
                timeout=5
            )
            data = response.json()
            
            if not data.get("data"):
                return [TextContent(type="text", text=f"No sound effects found for '{query}'")]
            
            results = []
            for sfx in data["data"][:limit]:  # Limit results manually
                results.append({
                    "title": sfx.get("title", "Unknown"),
                    "mp3": sfx.get("mp3", ""),
                    "query": query
                })
            
            return [TextContent(type="text", text=json.dumps(results))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching sound effects: {str(e)}")]
    
    async def handle_tts(self, arguments: dict) -> list[TextContent | ImageContent]:
        """Convert text to speech"""
        text = arguments["text"]
        output_file = arguments.get("output_file", "narration.mp3")
        
        # Cleanup old narration files (SFX cache is preserved)
        cleanup_old_audio(self.screenshot_dir, 10)
        
        # Use ElevenLabs TTS with custom voice ID and settings
        try:
            audio = self.elevenlabs_client.text_to_speech.convert(
                voice_id="nPczCjzI2devNBz1zQrb",  # Brian voice
                text=text,
                model_id="eleven_multilingual_v2"
            )
            
            # Save audio file
            output_path = self.screenshot_dir / output_file
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            
            return [TextContent(type="text", text=f"Audio saved to {output_file}")]
        except Exception as e:
            return [TextContent(type="text", text=f"TTS Error: {str(e)}")]
