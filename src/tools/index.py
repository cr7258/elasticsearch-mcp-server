from typing import Dict, List, Optional

from fastmcp import FastMCP
from mcp.types import TextContent


class IndexTools:

    def __init__(self, search_client):
        self.search_client = search_client

    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def list_indices() -> List[Dict]:
            """List all indices."""
            return self.search_client.list_indices()

        @mcp.tool()
        def get_index(index: str) -> Dict:
            """
            Returns information (mappings, settings, aliases) about one or more indices.

            Args:
                index: Name of the index
            """
            return self.search_client.get_index(index=index)

        @mcp.tool()
        def create_index(index: str, body: Optional[Dict] = None) -> Dict:
            """
            Create a new index.

            Args:
                index: Name of the index
                body: Optional index configuration including mappings and settings
            """
            return self.search_client.create_index(index=index, body=body)

        @mcp.tool(description="Create new index with the same mapping as existing_index")
        def create_index_copy(index: str, existing_index: str) -> list[TextContent]:
            """
            Create index with mapping of existing_index
            """
            self.logger.info(f"Creating index: {index} with mapping of {existing_index} existing index")
            mapping = self.search_client.get_mapping(index=existing_index)
            settings = self.search_client.get_settings(index=existing_index)
            return self.search_client.create_index(index=index, mappings=mapping, settings=settings)

        @mcp.tool()
        def delete_index(index: str) -> Dict:
            """
            Delete an index.

            Args:
                index: Name of the index
            """
            return self.search_client.delete_index(index=index)
