# Quick Start: Sound Effects Integration

Get up and running with automatic sound effects in 3 minutes!

## Prerequisites

Make sure you have the basic setup complete:
- Python 3.8+
- API keys in `.env` file (Gemini, ElevenLabs)
- Dependencies installed: `pip install -r requirements.txt`

## Step 1: Install Dependencies

The SFX integration requires the `requests` library:

```bash
pip install requests
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## Step 2: Test the Integration

Run the demo to see it in action:

```bash
python3 demo_sfx.py
```

This will:
1. Generate 4 different narrations
2. Automatically select appropriate sound effects
3. Play each SFX followed by the narration

## Step 3: Use in Your Clients

The SFX integration is already built into both clients!

### Screenshot Client
```bash
python3 screenshot_client.py
```

### Minecraft-Only Client
```bash
python3 minecraft_only_client.py
```

Both clients will now:
- Analyze narration content
- Automatically select sound effects
- Play SFX before narration audio

## How It Works

The system automatically detects keywords in narrations:

| Narration Contains | Sound Effect |
|-------------------|--------------|
| died, death, fail, damage | "bruh" sound |
| laugh, funny, hilarious | "laugh" sound |
| explosion, boom, tnt | "explosion" sound |
| wow, amazing, incredible | "wow" sound |

## Example

```
Narration: "This dumbass just died falling into lava"
         ↓
Keyword detected: "died"
         ↓
SFX selected: "BRUH"
         ↓
Playback: [BRUH!] → [pause] → [narration]
```

## Customization

Want different sound effects? Edit the keyword detection in `get_sfx_for_narration()`:

```python
# In screenshot_client.py or minecraft_only_client.py
if any(word in narration_lower for word in ["victory", "win"]):
    query = "victory"  # Search for victory sounds
```

## Testing Individual Components

### Test MyInstants API
```bash
python3 test_sfx.py
```

### Test MCP Tool
```bash
python3 test_mcp_sfx.py
```

### Test Download & Playback
```bash
python3 test_sfx_download.py
```

### Test Full Flow
```bash
python3 test_full_sfx_flow.py
```

## Troubleshooting

### No sound effects playing
- Check internet connection
- Verify MyInstants API: `curl https://myinstants-api.vercel.app/search?q=bruh`
- Check console for error messages

### Download fails
- Ensure `requests` is installed: `pip install requests`
- Check firewall settings
- Verify MyInstants.com is accessible

### Audio doesn't play
- macOS: Verify `afplay` works: `afplay screenshots/test_bruh.mp3`
- Check audio files exist: `ls screenshots/sfx_*.mp3`
- Verify volume is not muted

## What's Next?

- Read [SFX_INTEGRATION.md](SFX_INTEGRATION.md) for detailed documentation
- Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
- Customize keyword detection for your use case
- Add new sound effect categories

## Need Help?

1. Check the test scripts to isolate issues
2. Review error messages in console
3. Verify all dependencies are installed
4. Check API accessibility

Enjoy your narrations with automatic comedic sound effects! 🎵
