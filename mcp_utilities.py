#!/usr/bin/env python3
"""
Utility functions for the Narrator MCP Server
Helper functions used internally by MCP tools
An LLM has indirect access to these via the MCP tools
"""

import os
import base64
from pathlib import Path


def cleanup_old_screenshots(screenshot_dir: Path, max_screenshots: int = 5):
    """Keep only the last MAX_SCREENSHOTS images"""
    screenshots = sorted(screenshot_dir.glob("*.png"), key=os.path.getmtime)
    while len(screenshots) > max_screenshots:
        oldest = screenshots.pop(0)
        oldest.unlink()


def cleanup_old_audio(screenshot_dir: Path, max_audio: int = 2):
    """Keep only the last N audio files"""
    audio_files = sorted(screenshot_dir.glob("*.mp3"), key=os.path.getmtime)
    while len(audio_files) > max_audio:
        oldest = audio_files.pop(0)
        oldest.unlink()


def encode_image(image_path: Path) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_sfx_query_from_narration(narration: str) -> str:
    """
    Fallback function to extract keyword from narration if AI doesn't provide one.
    
    Sound effects provided by MyInstants API (https://github.com/abdipr/myinstants-api)
    Sounds sourced from MyInstants.com via web scraping.
    """
    narration_lower = narration.lower()
    
    # Simple keyword matching as fallback
    if any(word in narration_lower for word in ["laugh", "funny", "hilarious", "laughing"]):
        return "laugh"
    elif any(word in narration_lower for word in ["died", "death", "fail", "falling", "fell"]):
        return "bruh"
    elif any(word in narration_lower for word in ["explosion", "explode", "boom", "tnt", "blew"]):
        return "explosion"
    elif any(word in narration_lower for word in ["wow", "amazing", "incredible"]):
        return "wow"
    elif any(word in narration_lower for word in ["scream", "yell", "shout"]):
        return "scream"
    elif any(word in narration_lower for word in ["crash", "smash", "break"]):
        return "crash"
    else:
        return "bruh"  # default


def get_last_screenshots(screenshot_dir: Path, count: int = 2):
    """Get the last N screenshots from the directory"""
    screenshots = sorted(screenshot_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
    return screenshots[:count]
