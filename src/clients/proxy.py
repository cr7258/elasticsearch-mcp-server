"""
Proxy support for the search clients.

All requests to a cluster can be routed through an HTTP(S) or SOCKS5 proxy,
e.g. ``socks5h://127.0.0.1:1080`` for an SSH dynamic port forward
(``ssh -D 1080``). ``socks5h`` resolves host names on the proxy side, which is
needed when the cluster host name only resolves inside the remote network.

The default urllib3-based transports of elasticsearch-py and opensearch-py do
not support proxies. When a proxy is configured, the clients therefore use
their requests-based transport instead, with the proxy set on its session.
SOCKS support comes from PySocks (``requests[socks]``) and, for the general
REST client, from socksio (``httpx[socks]``).
"""
from typing import Dict, Optional
from urllib.parse import urlsplit

SUPPORTED_PROXY_SCHEMES = ("http", "https", "socks5", "socks5h")


def normalize_proxy_url(proxy: Optional[object]) -> Optional[str]:
    """Validate a proxy URL and return it, or ``None`` if no proxy is set."""
    if proxy is None:
        return None
    proxy_url = str(proxy).strip()
    if not proxy_url:
        return None

    parts = urlsplit(proxy_url)
    if parts.scheme.lower() not in SUPPORTED_PROXY_SCHEMES or not parts.hostname:
        raise ValueError(
            f"Invalid proxy URL '{proxy_url}'. Expected <scheme>://<host>:<port> "
            f"with scheme one of: {', '.join(SUPPORTED_PROXY_SCHEMES)}"
        )
    return proxy_url


def requests_proxies(proxy_url: str) -> Dict[str, str]:
    """Return a requests ``proxies`` mapping that routes all traffic through ``proxy_url``."""
    return {"http": proxy_url, "https": proxy_url}


def elasticsearch_proxy_kwargs(proxy_url: str) -> Dict:
    """Return ``Elasticsearch()`` kwargs that send every request through ``proxy_url``."""
    from elasticsearch import __version__ as es_version

    proxies = requests_proxies(proxy_url)

    if es_version[0] >= 8:
        # elasticsearch-py 8+/9+ selects the HTTP implementation via node_class.
        from elastic_transport import RequestsHttpNode

        class ProxyRequestsHttpNode(RequestsHttpNode):
            def __init__(self, config):
                super().__init__(config)
                self.session.proxies = dict(proxies)

        return {"node_class": ProxyRequestsHttpNode}

    # elasticsearch-py 7 selects it via connection_class.
    from elasticsearch import RequestsHttpConnection

    class ProxyRequestsHttpConnection(RequestsHttpConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session.proxies = dict(proxies)

    return {"connection_class": ProxyRequestsHttpConnection}


def opensearch_proxy_kwargs(proxy_url: str) -> Dict:
    """Return ``OpenSearch()`` kwargs that send every request through ``proxy_url``."""
    # Older opensearch-py releases have no ``proxies`` argument, so set it on
    # the session directly, which works for all versions.
    from opensearchpy import RequestsHttpConnection

    proxies = requests_proxies(proxy_url)

    class ProxyRequestsHttpConnection(RequestsHttpConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session.proxies = dict(proxies)

    return {"connection_class": ProxyRequestsHttpConnection}
