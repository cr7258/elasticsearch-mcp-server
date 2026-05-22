from typing import Dict, Optional

from fastmcp import FastMCP

from src.tools.utils import get_search_client

class ClusterTools:
    def __init__(self, search_client):
        self.search_client = search_client
    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def get_cluster_health(cluster: Optional[str] = None) -> Dict:
            """
            Returns basic information about the health of the cluster.

            Args:
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).get_cluster_health()

        @mcp.tool()
        def get_cluster_stats(cluster: Optional[str] = None) -> Dict:
            """
            Returns high-level overview of cluster statistics.

            Args:
                cluster: Optional cluster name. Uses the default cluster if omitted.
            """
            return get_search_client(self.search_client, cluster).get_cluster_stats()
