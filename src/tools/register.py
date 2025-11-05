import logging
from typing import List, Type

from fastmcp import FastMCP

from src.clients import SearchClient
from src.clients.exceptions import with_exception_handling
from src.risk_config import risk_manager

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
            
            # Check if risk management is enabled (high-risk operations are disabled)
            if risk_manager.high_risk_ops_disabled:
                # Add risk manager attributes for filtering
                tool_instance.risk_manager = risk_manager
                tool_instance.tool_class_name = tool_class.__name__
                # Register tools with risk filtering
                self._register_with_risk_filter(tool_instance)
            else:
                # Register tools with just exception handling (original way)
                with_exception_handling(tool_instance, self.mcp)
    
    def _register_with_risk_filter(self, tool_instance):
        """
        Register tools with risk filtering applied.
        Only called when risk management is enabled.
        
        Args:
            tool_instance: The tool instance to register
        """
        # Save the original mcp.tool method
        original_tool = self.mcp.tool
        
        # Create a wrapper that filters based on risk
        def risk_filter_wrapper(*args, **kwargs):
            # Get the original decorator
            decorator = original_tool(*args, **kwargs)
            
            def risk_check_decorator(func):
                operation_name = func.__name__
                
                # Check if operation is allowed
                if not risk_manager.is_operation_allowed(tool_instance.tool_class_name, operation_name):
                    # Don't register disabled tools - return a no-op function
                    def no_op(*args, **kwargs):
                        pass
                    return no_op
                
                # If allowed, use the original decorator
                return decorator(func)
            
            return risk_check_decorator
        
        try:
            self.mcp.tool = risk_filter_wrapper
            # This will wrap our risk_filter_wrapper with exception handling
            with_exception_handling(tool_instance, self.mcp)
        finally:
            # Restore the original mcp.tool
            self.mcp.tool = original_tool
