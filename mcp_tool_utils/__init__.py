"""
MCP Tool Utilities Package
Contains tool definitions and handlers for the Narrator MCP Server
"""

#Defines this package and where to get the definitions
from .tool_definitions import ToolDefinitions
from .tool_handlers import ToolHandlers

#When importing all these will be imported
__all__ = ['ToolDefinitions', 'ToolHandlers']
