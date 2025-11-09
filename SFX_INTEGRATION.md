# Sound Effects Integration Guide

This document explains how the MyInstants API integration works for adding comedic sound effects to narrations.

## Overview

The system automatically selects and plays sound effects based on the content of the narration. Sound effects are played before the narration audio for maximum comedic impact.

## How It Works

### 1. MyInstants API

We use the public MyInstants API hosted at: `https://myinstants-api.vercel.app`

**Search Endpoint**: `GET /search?q={query}`

Returns a list of sound effects matching the query, including:
- `title`: Name of the sound effect
- `mp3`: Direct URL to the MP3 file
- `url`: Link to the MyInstants page
- `id`: Unique identifier

### 2. MCP Tool: `get_sfx`

The MCP server provides a `get_sfx` tool that searches for sound effects:

```python
result = await session.call_tool("get_sfx", {
    "query": "bruh",
    "limit": 3  # optional, default 3
})
```

Returns JSON array of sound effects:
```json
[
  {
    "title": "BRUH",
    "mp3": "https://www.myinstants.com/media/sounds/movie_1.mp3",
    "url": "https://www.myinstants.com/en/instant/bruh"
  }
]
```

### 3. Keyword Matching

The `get_sfx_for_narration()` function analyzes narration text and selects appropriate sound effects:

| Keywords | SFX Query | Example Sounds |
|----------|-----------|----------------|
| fail, died, death, damage | bruh | "BRUH", "Bruh meme" |
| laugh, funny, hilarious, joke | laugh | "oh no no no laugh", "baby laughing meme" |
| explosion, explode, boom, tnt | explosion | "FBI OPEN UP", "Explosion meme" |
| wow, amazing, incredible | wow | "Anime Wow", "oh my god, wow!" |

### 4. Download and Playback

1. Download MP3 from MyInstants URL
2. Save to screenshots directory with timestamp
3. Play sound effect using platform-specific audio player
4. Wait 0.3 seconds
5. Play narration audio

## Implementation Details

### Client-Side (screenshot_client.py, minecraft_only_client.py)

```python
# Get SFX based on narration
sfx_info = await get_sfx_for_narration(narration_text)

# Download MP3
sfx_path = download_sfx(sfx_info['mp3'], f"sfx_{timestamp}.mp3")

# Play SFX then narration
await asyncio.to_thread(play_audio, sfx_path)
await asyncio.sleep(0.3)
await asyncio.to_thread(play_audio, narration_path)
```

### Server-Side (mcp_server.py)

```python
elif name == "get_sfx":
    query = arguments["query"]
    limit = arguments.get("limit", 3)
    
    response = requests.get(
        "https://myinstants-api.vercel.app/search",
        params={"q": query},
        timeout=10
    )
    data = response.json()
    
    # Extract and return sound effects
    sounds = data["data"][:limit]
    return [TextContent(type="text", text=json.dumps(sounds))]
```

## Customization

### Adding New Keywords

Edit the `get_sfx_for_narration()` function in both client files:

```python
# Add new keyword category
elif any(word in narration_lower for word in ["victory", "win", "success"]):
    query = "victory"
```

### Changing Default SFX

Modify the default query:

```python
query = "bruh"  # Change to your preferred default
```

### Adjusting Timing

Change the pause between SFX and narration:

```python
await asyncio.sleep(0.3)  # Increase for longer pause
```

## Testing

Run the test scripts to verify functionality:

```bash
# Test MyInstants API directly
python3 test_sfx.py

# Test MCP get_sfx tool
python3 test_mcp_sfx.py

# Test full integration flow
python3 test_full_sfx_flow.py

# Test download and playback
python3 test_sfx_download.py
```

## Troubleshooting

### No sound effects found
- Check internet connection
- Verify MyInstants API is accessible: `curl https://myinstants-api.vercel.app/search?q=bruh`
- Try different search queries

### Download fails
- Check firewall settings
- Verify requests library is installed: `pip install requests`
- Check MyInstants.com is not blocked

### Playback issues
- Verify audio file was downloaded: `ls screenshots/sfx_*.mp3`
- Test playback manually: `afplay screenshots/sfx_*.mp3` (macOS)
- Check platform-specific audio player is available

## API Credits & Attribution

This integration uses the [MyInstants REST API](https://github.com/abdipr/myinstants-api) by abdiputranar, which scrapes sound data from [MyInstants.com](https://www.myinstants.com).

### Compliance with MyInstants API Disclaimer

Per the API's requirements:

> ⚠️ **Disclaimer**: The sounds contained in this API are obtained from the original MyInstants website by web scraping. Developers using this API must follow the applicable regulations by mentioning this project or the official owner in their projects and are prohibited from abusing this API for personal benefits.

This project complies by:
- ✅ Providing proper attribution to the MyInstants API and MyInstants.com
- ✅ Mentioning the API creator (abdiputranar) in documentation and code
- ✅ Using the API for non-commercial, educational, and entertainment purposes only
- ✅ Not abusing the API for personal commercial benefits
- ✅ Respecting API usage limits and MyInstants.com terms of service

**If you fork or use this project, please maintain this attribution and follow the same guidelines.**
