from typing import Dict

from fastmcp import FastMCP

class ClusterTools:
    def __init__(self, search_client):
        self.search_client = search_client
    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def get_cluster_health() -> Dict:
            """Returns basic information about the health of the cluster."""
            return self.search_client.get_cluster_health()

        @mcp.tool()
        def get_cluster_stats() -> Dict:
            """Returns high-level overview of cluster statistics."""
            return self.search_client.get_cluster_stats()
