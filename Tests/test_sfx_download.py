#!/usr/bin/env python3
"""Test downloading and playing a sound effect"""

import requests
import subprocess
import platform
from pathlib import Path

SCREENSHOT_DIR = Path("./screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

def download_sfx(mp3_url: str, filename: str) -> Path:
    """Download sound effect from URL"""
    sfx_path = SCREENSHOT_DIR / filename
    try:
        print(f"📥 Downloading: {mp3_url}")
        response = requests.get(mp3_url, timeout=10)
        response.raise_for_status()
        with open(sfx_path, 'wb') as f:
            f.write(response.content)
        print(f"✅ Downloaded to: {sfx_path}")
        return sfx_path
    except Exception as e:
        print(f"❌ Failed to download SFX: {e}")
        return None

def play_audio(audio_file: Path):
    """Play audio file"""
    if not audio_file.exists():
        print(f"❌ File not found: {audio_file}")
        return
    
    print(f"🔊 Playing: {audio_file}")
    system = platform.system()
    
    if system == "Darwin":  # macOS
        subprocess.run(["afplay", str(audio_file)])
        print("✅ Playback complete")
    else:
        print("⚠️  Playback only implemented for macOS in this test")

if __name__ == "__main__":
    # Download and play a "bruh" sound effect
    sfx_url = "https://www.myinstants.com/media/sounds/movie_1.mp3"
    sfx_path = download_sfx(sfx_url, "test_bruh.mp3")
    
    if sfx_path:
        play_audio(sfx_path)
