from typing import Dict, Optional
from fastmcp import FastMCP

from src.tools.utils import get_search_client

class DataStreamTools:    
    def __init__(self, search_client):
        self.search_client = search_client
    
    def register_tools(self, mcp: FastMCP):
        """Register data stream tools with the MCP server."""
        
        @mcp.tool()
        def create_data_stream(name: str, cluster: Optional[str] = None) -> Dict:
            """Create a new data stream.
            
            This creates a new data stream with the specified name.
            The data stream must have a matching index template before creation.
            
            Args:
                name: Name of the data stream to create
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).create_data_stream(
                name=name
            )
        
        @mcp.tool()
        def get_data_stream(
            name: Optional[str] = None, cluster: Optional[str] = None
        ) -> Dict:
            """Get information about one or more data streams.
            
            Retrieves configuration, mappings, settings, and other information
            about the specified data streams.
            
            Args:
                name: Name of the data stream(s) to retrieve.
                      Can be a comma-separated list or wildcard pattern.
                      If not provided, retrieves all data streams.
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).get_data_stream(
                name=name
            )
        
        @mcp.tool()
        def delete_data_stream(name: str, cluster: Optional[str] = None) -> Dict:
            """Delete one or more data streams.
            
            Permanently deletes the specified data streams and all their backing indices.
            
            Args:
                name: Name of the data stream(s) to delete.
                      Can be a comma-separated list or wildcard pattern.
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).delete_data_stream(
                name=name
            )
