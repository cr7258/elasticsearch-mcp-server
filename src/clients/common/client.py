from typing import Dict

from src.clients.common.alias import AliasClient
from src.clients.common.cluster import ClusterClient
from src.clients.common.document import DocumentClient
from src.clients.common.index import IndexClient

class SearchClient(IndexClient, DocumentClient, ClusterClient, AliasClient):
    """
    Unified search client that combines all search functionality.
    
    This class uses multiple inheritance to combine all specialized client implementations
    (index, document, cluster, alias) into a single unified client.
    """
    
    def __init__(self, config: Dict, engine_type: str):
        """
        Initialize the search client.
        
        Args:
            config: Configuration dictionary with connection parameters
            engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        """
        super().__init__(config, engine_type)
        self.logger.info(f"Initialized the {engine_type} client")
