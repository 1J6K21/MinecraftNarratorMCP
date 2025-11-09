#!/usr/bin/env python3
"""
MCP Tool Definitions
Defines all available tools for the Narrator MCP Server
"""

from mcp.types import Tool


class ToolDefinitions:
    """Container for all MCP tool definitions"""
    
    @staticmethod
    def get_screenshot() -> Tool:
        return Tool(
            name="get_screenshot",
            description="Gets the last two screenshots from the specified directory and returns them",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    
    @staticmethod
    def get_minecraft_input() -> Tool:
        return Tool(
            name="get_minecraft_input",
            description="Receives Minecraft mod data (events like block breaks, placements, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "minecraft_data": {
                        "type": "string",
                        "description": "JSON string containing Minecraft events"
                    }
                },
                "required": ["minecraft_data"]
            }
        )
    
    @staticmethod
    def describe() -> Tool:
        return Tool(
            name="describe",
            description="Describes changes from screenshots and/or Minecraft mod data. At least one input required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_count": {
                        "type": "number",
                        "description": "Number of recent screenshots to analyze (0-5, default 2)"
                    },
                    "include_minecraft": {
                        "type": "boolean",
                        "description": "Whether to include Minecraft mod data in the description"
                    }
                },
                "required": []
            }
        )
    
    @staticmethod
    def describe_for_narration() -> Tool:
        return Tool(
            name="describe_for_narration",
            description="Combined tool: analyzes screenshots/Minecraft data, generates narration, and automatically selects appropriate sound effect. Returns JSON with narration and SFX info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_count": {
                        "type": "number",
                        "description": "Number of recent screenshots to analyze (0-5, default 2)"
                    },
                    "include_minecraft": {
                        "type": "boolean",
                        "description": "Whether to include Minecraft mod data"
                    }
                },
                "required": []
            }
        )
    
    @staticmethod
    def narrate() -> Tool:
        return Tool(
            name="narrate",
            description="Generates funny, sarcastic narration from a description",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of what's happening"
                    }
                },
                "required": ["description"]
            }
        )
    
    @staticmethod
    def summarize_narrations() -> Tool:
        return Tool(
            name="summarize_narrations",
            description="Summarizes multiple narrations into one concise sentence",
            inputSchema={
                "type": "object",
                "properties": {
                    "narrations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of narration strings to summarize"
                    }
                },
                "required": ["narrations"]
            }
        )
    
    @staticmethod
    def tts() -> Tool:
        return Tool(
            name="tts",
            description="Converts text to speech using ElevenLabs TTS",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to convert to speech"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Output filename (e.g., 'narration.mp3')"
                    }
                },
                "required": ["text", "output_file"]
            }
        )
    
    @staticmethod
    def get_sfx() -> Tool:
        return Tool(
            name="get_sfx",
            description="Search for sound effects from MyInstants API. Returns JSON with title, mp3 URL, and search query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for sound effect (e.g., 'bruh', 'explosion', 'laugh')"
                    }
                },
                "required": ["query"]
            }
        )
    
    @classmethod
    def get_all_tools(cls) -> list[Tool]:
        """Returns all tool definitions"""
        return [
            cls.get_screenshot(),
            cls.get_minecraft_input(),
            cls.describe(),
            cls.describe_for_narration(),
            cls.narrate(),
            cls.summarize_narrations(),
            cls.tts(),
            cls.get_sfx()
        ]
