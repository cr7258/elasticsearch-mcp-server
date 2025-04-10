import logging
from typing import List, Type

from fastmcp import FastMCP

from src.clients import SearchClient
from src.clients.exceptions import with_exception_handling

class ToolsRegister:
    """Class to handle registration of MCP tools."""
    
    def __init__(self, logger: logging.Logger, search_client: SearchClient, mcp: FastMCP):
        """
        Initialize the tools register.
        
        Args:
            logger: Logger instance
            search_client: Search client instance
            mcp: FastMCP instance
        """
        self.logger = logger
        self.search_client = search_client
        self.mcp = mcp
    
    def register_all_tools(self, tool_classes: List[Type]):
        """
        Register all tools with the MCP server.
        
        Args:
            tool_classes: List of tool classes to register
        """
        for tool_class in tool_classes:
            self.logger.info(f"Registering tools from {tool_class.__name__}")
            tool_instance = tool_class(self.search_client)
            
            # Set logger and client attributes
            tool_instance.logger = self.logger
            tool_instance.search_client = self.search_client
            
            # Register tools with automatic exception handling
            with_exception_handling(tool_instance, self.mcp)
