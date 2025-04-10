from typing import Dict

from src.clients.base import SearchClientBase

class ClusterClient(SearchClientBase):
    def get_cluster_health(self) -> Dict:
        """Get cluster health information from OpenSearch."""
        return self.client.cluster.health()
    
    def get_cluster_stats(self) -> Dict:
        """Get cluster statistics from OpenSearch."""
        return self.client.cluster.stats()