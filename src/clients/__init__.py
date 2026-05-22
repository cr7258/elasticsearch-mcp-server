import os
import json
from typing import Dict, Optional

from dotenv import load_dotenv

from src.clients.common.client import SearchClient
from src.clients.exceptions import handle_search_exceptions


class SearchClientManager:
    """Manages search clients for one or more named clusters."""

    def __init__(
        self,
        clients: Dict[str, SearchClient],
        default_cluster: str = "default",
    ):
        if not clients:
            raise ValueError("At least one search cluster must be configured")
        if default_cluster not in clients:
            raise ValueError(
                f"Default cluster '{default_cluster}' is not configured. "
                f"Available clusters: {', '.join(clients.keys())}"
            )
        self._clients = clients
        self.default_cluster = default_cluster

    def get_client(self, cluster: Optional[str] = None) -> SearchClient:
        """Return the client for the requested cluster, or the default cluster."""
        cluster_name = cluster or self.default_cluster
        try:
            return self._clients[cluster_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown cluster '{cluster_name}'. "
                f"Available clusters: {', '.join(self._clients.keys())}"
            ) from exc

    def list_clusters(self) -> list[str]:
        """Return the configured cluster names."""
        return list(self._clients.keys())

    def __getattr__(self, name: str):
        """Proxy existing single-cluster calls to the default cluster."""
        return getattr(self.get_client(), name)


def _parse_timeout(timeout_value: Optional[object]) -> Optional[float]:
    if timeout_value in (None, ""):
        return None
    try:
        return float(timeout_value)
    except (TypeError, ValueError):
        return None


def _parse_bool(value: Optional[object], default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _normalize_hosts(hosts: object) -> list[str]:
    if isinstance(hosts, str):
        return [host.strip() for host in hosts.split(",") if host.strip()]
    if isinstance(hosts, list):
        return [str(host).strip() for host in hosts if str(host).strip()]
    return ["https://localhost:9200"]


def _build_config(cluster_config: Dict, engine_type: str) -> Dict:
    prefix = engine_type.upper()
    verify_certs = _parse_bool(
        cluster_config.get("verify_certs"),
        default=os.environ.get("VERIFY_CERTS", "false").lower() == "true",
    )
    timeout = _parse_timeout(cluster_config.get("timeout"))
    if timeout is None:
        timeout = _parse_timeout(os.environ.get("REQUEST_TIMEOUT"))

    return {
        "hosts": _normalize_hosts(cluster_config.get("hosts")),
        "username": cluster_config.get("username") or os.environ.get(f"{prefix}_USERNAME"),
        "password": cluster_config.get("password") or os.environ.get(f"{prefix}_PASSWORD"),
        "api_key": cluster_config.get("api_key") or os.environ.get(f"{prefix}_API_KEY"),
        "verify_certs": verify_certs,
        "timeout": timeout,
    }

def create_search_client(engine_type: str) -> SearchClient:
    """
    Create a search client for the specified engine type.
    
    Args:
        engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        
    Returns:
        A search client instance
    """
    return create_search_client_manager(engine_type).get_client()


def _load_clusters_config(engine_type: str) -> Optional[Dict]:
    """Return the parsed clusters config, or ``None`` if no multi-cluster
    environment variable is set.

    Precedence:
        1. ``<ENGINE>_CLUSTERS_FILE`` — path to a JSON file with the clusters
           object. Easier to read because it avoids JSON-in-JSON escaping
           inside an MCP configuration file.
        2. ``<ENGINE>_CLUSTERS`` — inline JSON object.
    """
    prefix = engine_type.upper()
    clusters_file = os.environ.get(f"{prefix}_CLUSTERS_FILE")
    if clusters_file:
        with open(clusters_file, "r") as handle:
            clusters_config = json.load(handle)
        if not isinstance(clusters_config, dict):
            raise ValueError(
                f"{prefix}_CLUSTERS_FILE must contain a JSON object"
            )
        return clusters_config

    clusters_str = os.environ.get(f"{prefix}_CLUSTERS")
    if clusters_str:
        clusters_config = json.loads(clusters_str)
        if not isinstance(clusters_config, dict):
            raise ValueError(f"{prefix}_CLUSTERS must be a JSON object")
        return clusters_config

    return None


def create_search_client_manager(engine_type: str) -> SearchClientManager:
    """
    Create a search client manager for the specified engine type.

    Supports a multi-cluster JSON file (``ELASTICSEARCH_CLUSTERS_FILE`` /
    ``OPENSEARCH_CLUSTERS_FILE``) or inline JSON env var
    (``ELASTICSEARCH_CLUSTERS`` / ``OPENSEARCH_CLUSTERS``). When neither is
    set, falls back to the existing single-cluster environment variables.
    """
    load_dotenv()

    clusters_config = _load_clusters_config(engine_type)

    if clusters_config is not None:
        clients = {
            cluster_name: SearchClient(
                _build_config(cluster_config or {}, engine_type), engine_type
            )
            for cluster_name, cluster_config in clusters_config.items()
        }
        default_cluster = os.environ.get("DEFAULT_CLUSTER") or next(iter(clients), "default")
        return SearchClientManager(clients, default_cluster=default_cluster)

    prefix = engine_type.upper()
    config = _build_config(
        {"hosts": os.environ.get(f"{prefix}_HOSTS", "https://localhost:9200")},
        engine_type,
    )
    return SearchClientManager(
        {"default": SearchClient(config, engine_type)},
        default_cluster="default",
    )

__all__ = [
    'create_search_client',
    'create_search_client_manager',
    'handle_search_exceptions',
    'SearchClient',
    'SearchClientManager',
]
