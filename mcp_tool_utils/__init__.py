"""
MCP Tool Utilities Package
Contains tool definitions, handlers, and utilities for the Narrator MCP Server
"""

# Defines this package and where to get the definitions
from .tool_definitions import ToolDefinitions
from .tool_handlers import ToolHandlers
from .utilities import (
    cleanup_old_screenshots,
    cleanup_old_audio,
    encode_image,
    get_sfx_query_from_narration,
    get_last_screenshots
)

# When importing all these will be imported
__all__ = [
    'ToolDefinitions',
    'ToolHandlers',
    'cleanup_old_screenshots',
    'cleanup_old_audio',
    'encode_image',
    'get_sfx_query_from_narration',
    'get_last_screenshots'
]
