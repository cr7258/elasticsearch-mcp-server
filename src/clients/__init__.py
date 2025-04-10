import os

from dotenv import load_dotenv

from src.clients.common.client import SearchClient
from src.clients.exceptions import handle_search_exceptions

def create_search_client(engine_type: str) -> SearchClient:
    """
    Create a search client for the specified engine type.
    
    Args:
        engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        
    Returns:
        A search client instance
    """
    # Load configuration from environment variables
    load_dotenv()
    
    # Get configuration from environment variables
    prefix = engine_type.upper()
    hosts_str = os.environ.get(f"{prefix}_HOSTS", "https://localhost:9200")
    hosts = [host.strip() for host in hosts_str.split(",")]
    username = os.environ.get(f"{prefix}_USERNAME")
    password = os.environ.get(f"{prefix}_PASSWORD")
    verify_certs = os.environ.get(f"{prefix}_VERIFY_CERTS", "false").lower() == "true"
    
    config = {
        "hosts": hosts,
        "username": username,
        "password": password,
        "verify_certs": verify_certs
    }
    
    return SearchClient(config, engine_type)

__all__ = [
    'create_search_client',
    'handle_search_exceptions',
    'SearchClient',
]
