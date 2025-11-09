# System Architecture

Complete architecture diagram showing all components and data flow.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Screenshot Narrator System                   │
│                    with Sound Effects Integration                │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Screenshot  │     │  Minecraft   │     │  MyInstants  │
│   Capture    │     │     Mod      │     │     API      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       │                    │                     │
       ▼                    ▼                     │
┌─────────────────────────────────────────┐      │
│         MCP Server (mcp_server.py)      │      │
│  ┌────────────────────────────────────┐ │      │
│  │ Tools:                             │ │      │
│  │ • get_screenshot                   │ │      │
│  │ • get_minecraft_input              │ │      │
│  │ • describe                         │ │      │
│  │ • narrate                          │ │      │
│  │ • describe_for_narration           │ │      │
│  │ • summarize_narrations             │ │      │
│  │ • get_sfx ◄────────────────────────┼──┼──────┘
│  │ • tts                              │ │
│  └────────────────────────────────────┘ │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Clients (screenshot_client.py,         │
│           minecraft_only_client.py)     │
│  ┌────────────────────────────────────┐ │
│  │ 1. Capture/Receive Input           │ │
│  │ 2. Generate Narration              │ │
│  │ 3. Get Sound Effect                │ │
│  │ 4. Generate TTS                    │ │
│  │ 5. Play SFX + Narration            │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Detailed Component Flow

### 1. Input Sources

```
┌─────────────────┐
│   Screenshots   │
│  (macOS/Win/    │
│    Linux)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Screenshot     │     │  Minecraft Mod   │
│  Directory      │     │  (MinecraftMCP)  │
│  ./screenshots/ │     └────────┬─────────┘
└────────┬────────┘              │
         │                       │ HTTP POST
         │                       ▼
         │              ┌──────────────────┐
         │              │ Flask Receiver   │
         │              │ (Port 8080)      │
         │              └────────┬─────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │ minecraft_data   │
         │              │     .json        │
         │              └────────┬─────────┘
         │                       │
         └───────────────────────┘
                    │
                    ▼
         ┌──────────────────┐
         │   MCP Server     │
         └──────────────────┘
```

### 2. MCP Server Processing

```
┌────────────────────────────────────────────────────────┐
│                    MCP Server                          │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Input Tools:                                          │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ get_screenshot   │  │get_minecraft_    │          │
│  │                  │  │    input         │          │
│  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │
│           └──────────┬──────────┘                     │
│                      ▼                                │
│           ┌──────────────────┐                        │
│           │    describe      │                        │
│           │  (Gemini 2.5)    │                        │
│           └────────┬─────────┘                        │
│                    ▼                                  │
│           ┌──────────────────┐                        │
│           │    narrate       │                        │
│           │  (Gemini 2.5)    │                        │
│           └────────┬─────────┘                        │
│                    │                                  │
│  ┌─────────────────┴─────────────────┐               │
│  │                                   │               │
│  ▼                                   ▼               │
│ ┌──────────────────┐      ┌──────────────────┐      │
│ │   get_sfx        │      │       tts        │      │
│ │ (MyInstants API) │      │  (ElevenLabs)    │      │
│ └────────┬─────────┘      └────────┬─────────┘      │
│          │                         │                 │
│          └──────────┬──────────────┘                 │
│                     ▼                                │
│            ┌──────────────────┐                      │
│            │  Audio Files     │                      │
│            │  (MP3)           │                      │
│            └──────────────────┘                      │
└────────────────────────────────────────────────────────┘
```

### 3. Sound Effects Integration

```
┌────────────────────────────────────────────────────────┐
│              Sound Effects Flow                        │
└────────────────────────────────────────────────────────┘

Narration Text
      │
      ▼
┌──────────────────┐
│ Keyword Analysis │
│                  │
│ • died → bruh    │
│ • laugh → laugh  │
│ • boom → explode │
│ • wow → wow      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  get_sfx Tool    │
│  (MCP Server)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ MyInstants API   │
│ GET /search?q=X  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  JSON Response   │
│  {title, mp3,    │
│   url}           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Download MP3    │
│  (requests lib)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Save to         │
│  screenshots/    │
│  sfx_*.mp3       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Play Audio      │
│  (afplay/etc)    │
└──────────────────┘
```

### 4. Client Playback Flow

```
┌────────────────────────────────────────────────────────┐
│              Audio Playback Sequence                   │
└────────────────────────────────────────────────────────┘

Event Detected (Screenshot/Minecraft)
         │
         ▼
┌──────────────────┐
│ Generate         │
│ Narration        │
│ (via MCP)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Get Sound Effect │
│ (analyze keywords│
│  + call get_sfx) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Download SFX MP3 │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Generate TTS     │
│ (via MCP)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Play SFX         │
│ (afplay/etc)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Wait 0.3s        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Play Narration   │
│ (afplay/etc)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Complete!        │
└──────────────────┘
```

## API Integrations

### Gemini AI (Google)
- **Purpose**: Vision analysis and narration generation
- **Model**: gemini-2.5-flash
- **Cost**: FREE
- **Usage**: 
  - Analyze screenshots
  - Generate descriptions
  - Create funny narrations

### ElevenLabs
- **Purpose**: Text-to-speech conversion
- **Voice**: Brian (nPczCjzI2devNBz1zQrb)
- **Cost**: 10k chars/month free
- **Usage**: Convert narration text to audio

### MyInstants API
- **Purpose**: Sound effects library
- **Endpoint**: https://myinstants-api.vercel.app
- **Cost**: FREE
- **Usage**: Search and download sound effects

## File Structure

```
.
├── mcp_server.py              # MCP server with all tools
├── screenshot_client.py       # Screenshot-based client
├── minecraft_only_client.py   # Minecraft-only client
├── minecraft_receiver.py      # Flask HTTP receiver
├── requirements.txt           # Python dependencies
├── .env                       # API keys (not in repo)
├── .env.example              # Example environment file
│
├── screenshots/              # Data directory
│   ├── screenshot_*.png     # Screenshots
│   ├── narration_*.mp3      # Narration audio
│   ├── sfx_*.mp3           # Sound effects
│   └── minecraft_data.json  # Minecraft events
│
├── myinstants-api/          # Cloned API repo
│   ├── api/                # PHP API files
│   └── README.md           # API documentation
│
├── MinecraftMCP.java        # Minecraft Fabric mod
│
├── README.md                # Main documentation
├── QUICKSTART_SFX.md       # Quick start guide
├── SFX_INTEGRATION.md      # SFX integration guide
├── IMPLEMENTATION_SUMMARY.md # Implementation details
├── ARCHITECTURE.md          # This file
│
└── test_*.py               # Test scripts
    ├── test_sfx.py
    ├── test_mcp_sfx.py
    ├── test_sfx_download.py
    ├── test_full_sfx_flow.py
    └── demo_sfx.py
```

## Data Flow Summary

1. **Input**: Screenshots or Minecraft events
2. **Analysis**: Gemini AI describes what's happening
3. **Narration**: Gemini generates funny commentary
4. **SFX Selection**: Keywords analyzed, appropriate sound chosen
5. **SFX Download**: MP3 downloaded from MyInstants
6. **TTS Generation**: ElevenLabs converts narration to speech
7. **Playback**: SFX plays, then narration plays
8. **Cleanup**: Old files removed to save space

## Concurrency Model

```
Main Thread
    │
    ├─► Screenshot Loop (every 10s)
    │   └─► Async: Generate Narration
    │
    ├─► Minecraft Event Loop (every 2s)
    │   └─► Async: Generate Narration
    │
    └─► Audio Playback Loop
        ├─► Async: Get SFX
        ├─► Async: Download SFX
        ├─► Async: Generate TTS
        └─► Thread: Play Audio (blocking)
```

## Error Handling

- **API Failures**: Graceful degradation (skip SFX if unavailable)
- **Download Errors**: Continue without SFX
- **TTS Quota**: Fallback to macOS `say` command
- **Network Issues**: Retry with timeout
- **File Errors**: Log and continue

## Performance Optimizations

1. **Background Processing**: Narrations generated while audio plays
2. **Event Batching**: Multiple events summarized into one narration
3. **File Cleanup**: Only keep last 5 screenshots, 2 audio files
4. **Async Operations**: Non-blocking API calls
5. **Caching**: Could cache downloaded SFX (future enhancement)

## Security Considerations

- API keys stored in `.env` (not in repo)
- No sensitive data in screenshots
- HTTP receiver only accepts JSON
- File operations restricted to screenshots directory
- No arbitrary code execution
