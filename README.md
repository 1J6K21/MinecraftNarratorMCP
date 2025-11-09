# Narrator MCP

A fun MCP server that takes screenshots, describes what changed, generates hilarious narration, and plays it back as audio!

## Datathon2025
We made this product in Texas A&M's DATATHON 2025 - A hackathon with the focus of AI, ML, Computer Science, Data Science, and Statistics!
<br></br>
### Contributers:
### Jonathan Kalsky '29 (CS):

www.linkedin.com/in/jonathan-kalsky

### Aaron Yang '29 (CS):

https://www.linkedin.com/in/nianjin-yang/

### Ethan Hince '29 (CS):

https://www.linkedin.com/in/ethan-hince-a831a5381/


<br></br>
### Brief Demo:
[https://youtu.be/umaCNd4jPfY?si=QRRDb36p3LI-7tyr](https://youtu.be/8Ra5xCAM_Yo?si=og1JRhXpG3UWLjHj)
<br></br>

### License
We do not allow the reproducing, forking, or stealing of our idea, code, or intellectual property. For information email jonathan.kalsky@gmail.com

<br></br>
<br></br>

## Features
### Connected to our *custom made and simultaneously programmed* Minecraft Mod that updates a the HTTP port with data
View: https://github.com/nianjindev/MinecraftMCPSender
### There is a UI to view the data on the port. To host the UI, run: 
```
python3 minecraft_reciever.py
```
```
python minecraft_reciever.py (windows)
```
### Otherwise
- **Get Screenshot**: Retrieves the last two screenshots from a directory
- **Describe**: Uses Gemini to analyze screenshots and describe changes
- **Narrate**: Generates funny, sarcastic narration about what you're doing
- **Sound Effects**: Automatically adds comedic sound effects from MyInstants API
- **TTS**: Converts narration to speech with ElevenLabs TTS
- **Auto-cleanup**: Only keeps the last 5 screenshots
<br></br>

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

4. In config/mcp/servers.json:
   - You may need to switch "Python3" to "Python" in the command field

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

### Available MCP Tools

- **get_screenshot**: Get the last N screenshots
- **get_minecraft_input**: Receive Minecraft gameplay events
- **describe**: Analyze screenshots and/or Minecraft data
- **narrate**: Generate funny narration from a description
- **describe_for_narration**: Combined tool (faster) - analyze and narrate in one step
- **summarize_narrations**: Combine multiple narrations into one sentence
- **get_sfx**: Search for sound effects from MyInstants API
- **tts**: Convert text to speech with ElevenLabs

## How It Works

1. **Screenshots**: Uses macOS `screencapture` to grab screenshots
2. **Analysis**: Gemini 2.5 Flash analyzes images and describes changes (fast & free!)
3. **Narration + SFX Keyword**: Gemini generates sarcastic commentary AND extracts the best sound effect keyword in ONE API call (super fast!)
4. **Sound Effect Search**: Searches MyInstants API with the AI-selected keyword and randomly picks from top results
5. **Speech**: ElevenLabs TTS converts text to audio with high-quality voice
6. **Playback**: Plays sound effect and narration audio in parallel for perfect timing

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

## Documentation

- **[QUICKSTART_SFX.md](QUICKSTART_SFX.md)**: Quick start guide for sound effects (3 minutes!)
- **[SFX_INTEGRATION.md](SFX_INTEGRATION.md)**: Complete guide to the sound effects system
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**: Technical implementation details
- **[myinstants-api/README.md](myinstants-api/README.md)**: MyInstants API documentation

## Notes

- **Cross-platform**: Works on macOS, Windows, and Linux
- Costs: Gemini is FREE + ElevenLabs has 10k chars/month free tier
- Gemini 2.5 Flash is super fast for vision tasks
- ElevenLabs voices are incredibly realistic and expressive
- MyInstants API provides free sound effects
- Press Ctrl+C to stop the client

### Platform-specific details:

- **macOS**: Uses native `screencapture` and `afplay` commands
- **Windows**: Uses PIL for screenshots and pygame for audio
- **Linux**: Uses `scrot`/`gnome-screenshot` for screenshots, various audio players

## License & Attribution

This project uses sound effects from:
- **MyInstants API** by abdiputranar: https://github.com/abdipr/myinstants-api
- **MyInstants.com**: https://www.myinstants.com

Sound effects are obtained via web scraping from MyInstants.com. This project:
- Provides proper attribution to the MyInstants API and MyInstants.com
- Is used for non-commercial, educational, and entertainment purposes only
- Complies with the MyInstants API usage requirements
- Does not abuse the API for personal commercial benefits

If you use this project, please maintain this attribution and follow the same guidelines.

## Customization

- Change `INTERVAL` in `screenshot_client.py` to adjust screenshot frequency
- Modify the narration prompt in `mcp_server.py` for different comedy styles
- Change TTS voice in `mcp_server.py` (ElevenLabs voices: Adam, Antoni, Arnold, Bella, Domi, Elli, Josh, Rachel, Sam, and more)
- Customize SFX selection logic in the `get_sfx_for_narration()` function to match different keywords

## Sound Effects

The system uses AI to automatically select the perfect sound effect for each narration:

1. **AI Keyword Extraction**: Gemini analyzes the narration and extracts the single best keyword for a sound effect (e.g., "crash", "laugh", "explosion", "oof", "bruh", "scream", etc.)
2. **MyInstants Search**: Searches the MyInstants API with that keyword
3. **Random Selection**: Picks a random sound from the top 10 results for variety
4. **Parallel Playback**: Plays sound effect and narration simultaneously for perfect comedic timing

This gives unlimited variety - every narration gets a unique, contextually appropriate sound effect!

**Example keywords extracted by AI**: crash, laugh, explosion, scream, bell, drum, bruh, oof, yikes, gasp, applause, horn, punch, falling, and many more!

### Credits

Sound effects are provided by:
- **MyInstants API**: https://github.com/abdipr/myinstants-api (by abdiputranar)
- **MyInstants.com**: https://www.myinstants.com (original sound library)

Sounds are obtained via web scraping from MyInstants.com. This project complies with the API's usage requirements by providing proper attribution and is used for non-commercial, educational purposes only.
