from abc import ABC
import logging
import warnings
from typing import Dict

class SearchClientBase(ABC):
    def __init__(self, config: Dict, engine_type: str):
        """
        Initialize the search client.
        
        Args:
            config: Configuration dictionary with connection parameters
            engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        """
        self.logger = logging.getLogger()
        self.config = config
        self.engine_type = engine_type
        
        # Extract common configuration
        hosts = config.get("hosts")
        username = config.get("username")
        password = config.get("password")
        verify_certs = config.get("verify_certs", False)
        
        # Disable insecure request warnings if verify_certs is False
        if not verify_certs:
            warnings.filterwarnings("ignore", message=".*verify_certs=False is insecure.*")
            warnings.filterwarnings("ignore", message=".*Unverified HTTPS request is being made to host.*")
            
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass
        
        # Initialize client based on engine type
        if engine_type == "elasticsearch":
            from elasticsearch import Elasticsearch
            self.client = Elasticsearch(
                hosts=hosts,
                basic_auth=(username, password) if username and password else None,
                verify_certs=verify_certs
            )
            self.logger.info(f"Elasticsearch client initialized with hosts: {hosts}")
        elif engine_type == "opensearch":
            from opensearchpy import OpenSearch
            self.client = OpenSearch(
                hosts=hosts,
                http_auth=(username, password) if username and password else None,
                verify_certs=verify_certs
            )
            self.logger.info(f"OpenSearch client initialized with hosts: {hosts}")
        else:
            raise ValueError(f"Unsupported engine type: {engine_type}")
