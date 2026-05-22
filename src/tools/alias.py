from typing import Dict, Optional

from fastmcp import FastMCP

from src.tools.utils import get_search_client


class AliasTools:
    def __init__(self, search_client):
        self.search_client = search_client

    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def list_aliases(cluster: Optional[str] = None) -> str:
            """
            List all aliases.

            Args:
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).list_aliases()

        @mcp.tool()
        def get_alias(index: str, cluster: Optional[str] = None) -> Dict:
            """
            Get alias information for a specific index.

            Args:
                index: Name of the index
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).get_alias(index=index)

        @mcp.tool()
        def put_alias(
            index: str, name: str, body: Dict, cluster: Optional[str] = None
        ) -> Dict:
            """
            Create or update an alias for a specific index.

            Args:
                index: Name of the index
                name: Name of the alias
                body: Alias configuration
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).put_alias(
                index=index, name=name, body=body
            )

        @mcp.tool()
        def delete_alias(
            index: str, name: str, cluster: Optional[str] = None
        ) -> Dict:
            """
            Delete an alias for a specific index.

            Args:
                index: Name of the index
                name: Name of the alias
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).delete_alias(
                index=index, name=name
            )
