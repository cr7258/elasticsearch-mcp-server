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

    error = (
        f"Invalid proxy URL. Expected <scheme>://<host>:<port> "
        f"with scheme one of: {', '.join(SUPPORTED_PROXY_SCHEMES)}"
    )
    parts = urlsplit(proxy_url)
    if parts.scheme.lower() not in SUPPORTED_PROXY_SCHEMES or not parts.hostname:
        raise ValueError(error)
    try:
        # Accessing .port raises ValueError for non-numeric or out-of-range ports.
        port = parts.port
    except ValueError:
        raise ValueError(f"{error} (port must be a number between 1 and 65535)") from None
    if port == 0:
        raise ValueError(f"{error} (port must be between 1 and 65535)")
    return proxy_url


def requests_proxies(proxy_url: str) -> Dict[str, str]:
    """Return a requests ``proxies`` mapping that routes all traffic through ``proxy_url``."""
    return {"http": proxy_url, "https": proxy_url}


def pin_session_proxies(session, proxy_url: str) -> None:
    """Route all requests of a ``requests.Session`` through ``proxy_url``.

    Setting ``session.proxies`` alone is not enough: the transports call
    ``session.merge_environment_settings()``, which gives ``HTTP_PROXY`` /
    ``HTTPS_PROXY`` / ``NO_PROXY`` precedence over the session proxies. Override
    the proxies in its result so the configured proxy always wins, the same as
    ``httpx.Client(proxy=...)`` does for the general REST client. Other
    environment settings such as ``REQUESTS_CA_BUNDLE`` keep working.
    """
    proxies = requests_proxies(proxy_url)
    session.proxies = dict(proxies)
    merge_environment_settings = session.merge_environment_settings

    def merge_environment_settings_with_pinned_proxy(*args, **kwargs):
        settings = merge_environment_settings(*args, **kwargs)
        settings["proxies"] = dict(proxies)
        return settings

    session.merge_environment_settings = merge_environment_settings_with_pinned_proxy


def elasticsearch_proxy_kwargs(proxy_url: str) -> Dict:
    """Return ``Elasticsearch()`` kwargs that send every request through ``proxy_url``."""
    from elasticsearch import __version__ as es_version

    if es_version[0] >= 8:
        # elasticsearch-py 8+/9+ selects the HTTP implementation via node_class.
        from elastic_transport import RequestsHttpNode

        class ProxyRequestsHttpNode(RequestsHttpNode):
            def __init__(self, config):
                super().__init__(config)
                pin_session_proxies(self.session, proxy_url)

        return {"node_class": ProxyRequestsHttpNode}

    # elasticsearch-py 7 selects it via connection_class.
    from elasticsearch import RequestsHttpConnection

    class ProxyRequestsHttpConnection(RequestsHttpConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            pin_session_proxies(self.session, proxy_url)

    return {"connection_class": ProxyRequestsHttpConnection}


def opensearch_proxy_kwargs(proxy_url: str) -> Dict:
    """Return ``OpenSearch()`` kwargs that send every request through ``proxy_url``."""
    # Older opensearch-py releases have no ``proxies`` argument, so pin it on
    # the session directly, which works for all versions.
    from opensearchpy import RequestsHttpConnection

    class ProxyRequestsHttpConnection(RequestsHttpConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            pin_session_proxies(self.session, proxy_url)

    return {"connection_class": ProxyRequestsHttpConnection}
