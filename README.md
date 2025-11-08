# Screenshot Narrator MCP

A fun MCP server that takes screenshots, describes what changed, generates hilarious narration, and plays it back as audio!

## Features

- **Get Screenshot**: Retrieves the last two screenshots from a directory
- **Describe**: Uses Claude to analyze screenshots and describe changes
- **Narrate**: Generates funny, sarcastic narration about what you're doing
- **TTS**: Converts narration to speech with OpenAI's TTS API
- **Auto-cleanup**: Only keeps the last 5 screenshots

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your API keys:

```bash
cp .env.example .env
# Edit .env and add your API keys
```

3. Get API keys:
   - Gemini API key: https://aistudio.google.com/app/apikey (FREE!)
   - ElevenLabs API key: https://elevenlabs.io/app/settings/api-keys (10k chars/month free)

## Usage

### Run the Client

The client takes screenshots every 5 seconds and generates narrated audio:

```bash
python screenshot_client.py
```

This will:

1. Take a screenshot every 5 seconds
2. After 2 screenshots, compare them
3. Generate a funny narration about what changed
4. Convert to speech and play it automatically

### Minecraft Mod Integration (Optional)

To include Minecraft gameplay events in the narration:

1. Install the Minecraft Fabric mod (see `MinecraftMCP.java`)
2. Run the screenshot client (it automatically starts the receiver):

```bash
python screenshot_client.py
```

3. Launch Minecraft - the mod will send events automatically

The narrator will describe both what's happening on screen AND in-game events like:

- Blocks placed/broken
- Damage taken
- Biome changes
- Day/night cycle

**Note:** The Minecraft receiver runs automatically in the background. No need to start it separately!

┌─────────────────┐
│ Minecraft Mod │ (Java)
│ (in game) │
└────────┬────────┘
│ HTTP POST
▼
┌─────────────────────┐
│ minecraft_receiver │ (Flask HTTP server)
│ Port 8080 │ Saves to minecraft_data.json
└────────┬────────────┘
│ File write
▼
┌─────────────────────┐
│ minecraft_data.json │ (Shared file)
└────────┬────────────┘
│ File read
▼
┌─────────────────────┐
│ screenshot_client │ Reads file, calls MCP tool
└────────┬────────────┘
│ MCP call
▼
┌─────────────────────┐
│ mcp_server.py │ Processes data via get_minecraft_input tool
└─────────────────────┘

### Use as MCP Server

You can also use this as an MCP server in Kiro or other MCP clients:

```json
{
  "mcpServers": {
    "screenshot-narrator": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your_key",
        "ELEVENLABS_API_KEY": "your_key",
        "SCREENSHOT_DIR": "./screenshots"
      }
    }
  }
}
```

## How It Works

1. **Screenshots**: Uses macOS `screencapture` to grab screenshots
2. **Analysis**: Gemini 1.5 Flash analyzes images and describes changes (fast & free!)
3. **Narration**: Gemini generates sarcastic commentary
4. **Speech**: ElevenLabs TTS converts text to audio with high-quality voice
5. **Playback**: macOS `afplay` plays the audio

## Example Output

```
📸 Screenshot saved: screenshots/screenshot_20251108_143022.png
📸 Screenshot saved: screenshots/screenshot_20251108_143027.png

==================================================
🎬 Processing screenshots...
==================================================
📋 Getting screenshots...
🔍 Describing changes...
Description: The user has switched from their code editor to a web browser,
apparently giving up on debugging to search Stack Overflow instead.

🎭 Generating funny narration...
Narration: And here we observe the developer in their natural habitat,
abandoning all hope of solving the problem themselves and turning to the
ancient wisdom of strangers on the internet. Truly magnificent.

🎤 Converting to speech...
🔊 Playing audio: screenshots/narration_20251108_143030.mp3
```

## Notes

- **Cross-platform**: Works on macOS, Windows, and Linux
- Costs: Gemini is FREE + ElevenLabs has 10k chars/month free tier
- Gemini 2.5 Flash is super fast for vision tasks
- ElevenLabs voices are incredibly realistic and expressive
- Press Ctrl+C to stop the client

### Platform-specific details:

- **macOS**: Uses native `screencapture` and `afplay` commands
- **Windows**: Uses PIL for screenshots and pygame for audio
- **Linux**: Uses `scrot`/`gnome-screenshot` for screenshots, various audio players

## Customization

- Change `INTERVAL` in `screenshot_client.py` to adjust screenshot frequency
- Modify the narration prompt in `mcp_server.py` for different comedy styles
- Change TTS voice in `mcp_server.py` (ElevenLabs voices: Adam, Antoni, Arnold, Bella, Domi, Elli, Josh, Rachel, Sam, and more)
