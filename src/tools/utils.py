from typing import Optional


def get_search_client(search_client, cluster: Optional[str] = None):
    """Resolve a named cluster when a client manager is provided."""
    if hasattr(search_client, "get_client"):
        return search_client.get_client(cluster)
    return search_client
