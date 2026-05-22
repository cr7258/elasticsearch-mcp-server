from typing import Dict, Optional

from fastmcp import FastMCP

from src.tools.utils import get_search_client


class IndexTools:
    def __init__(self, search_client):
        self.search_client = search_client

    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def list_indices(cluster: Optional[str] = None) -> str:
            """
            List all indices.

            Args:
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).list_indices()

        @mcp.tool()
        def get_index(index: str, cluster: Optional[str] = None) -> Dict:
            """
            Returns information (mappings, settings, aliases) about one or more indices.

            Args:
                index: Name of the index
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).get_index(index=index)

        @mcp.tool()
        def create_index(
            index: str, body: Optional[Dict] = None, cluster: Optional[str] = None
        ) -> Dict:
            """
            Create a new index.

            Args:
                index: Name of the index
                body: Optional index configuration including mappings and settings
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).create_index(
                index=index, body=body
            )

        @mcp.tool()
        def delete_index(index: str, cluster: Optional[str] = None) -> Dict:
            """
            Delete an index.

            Args:
                index: Name of the index
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).delete_index(index=index)
