import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import StreamRequestHandler, ThreadingTCPServer

import pytest

from src.clients import SearchClient
from src.clients.base import GeneralRestClient
from src.clients.proxy import (
    elasticsearch_proxy_kwargs,
    normalize_proxy_url,
    opensearch_proxy_kwargs,
)

pytestmark = pytest.mark.unit


def _client_config(**overrides):
    config = {
        "hosts": ["http://localhost:9200"],
        "username": None,
        "password": None,
        "api_key": None,
        "verify_certs": False,
        "timeout": None,
        "proxy": None,
    }
    config.update(overrides)
    return config


# --- configuration ---------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "   "])
def test_normalize_proxy_url_returns_none_when_unset(value):
    assert normalize_proxy_url(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "http://proxy.example.com:3128",
        "https://proxy.example.com:3128",
        "socks5://127.0.0.1:1080",
        "socks5h://user:secret@127.0.0.1:1080",
    ],
)
def test_normalize_proxy_url_accepts_supported_schemes(value):
    assert normalize_proxy_url(f"  {value} ") == value


@pytest.mark.parametrize(
    "value",
    [
        "ftp://proxy:21",
        "socks4://proxy:1080",
        "127.0.0.1:1080",
        "socks5h://",
        "socks5h://127.0.0.1:invalid",
        "socks5h://127.0.0.1:99999",
        "http://proxy:0",
    ],
)
def test_normalize_proxy_url_rejects_invalid_urls(value):
    with pytest.raises(ValueError, match="Invalid proxy URL"):
        normalize_proxy_url(value)


def test_proxy_from_env_var_is_applied_to_single_cluster(monkeypatch):
    from src.clients import create_search_client_manager

    created = []
    monkeypatch.delenv("ELASTICSEARCH_CLUSTERS", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_CLUSTERS_FILE", raising=False)
    monkeypatch.setenv("ELASTICSEARCH_HOSTS", "https://es.internal:9200")
    monkeypatch.setenv("ELASTICSEARCH_PROXY", "socks5h://127.0.0.1:1080")
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr(
        "src.clients.SearchClient", lambda config, engine: created.append(config) or object()
    )

    create_search_client_manager("elasticsearch")

    assert created[0]["proxy"] == "socks5h://127.0.0.1:1080"


def test_cluster_proxy_overrides_env_var(monkeypatch):
    from src.clients import create_search_client_manager

    created = []
    monkeypatch.delenv("ELASTICSEARCH_CLUSTERS_FILE", raising=False)
    monkeypatch.delenv("DEFAULT_CLUSTER", raising=False)
    monkeypatch.setenv("ELASTICSEARCH_PROXY", "socks5h://127.0.0.1:1080")
    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps(
            {
                "a": {"hosts": ["https://a:9200"], "proxy": "socks5h://127.0.0.1:2080"},
                "b": {"hosts": ["https://b:9200"]},
            }
        ),
    )
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr(
        "src.clients.SearchClient", lambda config, engine: created.append(config) or object()
    )

    create_search_client_manager("elasticsearch")

    assert [c["proxy"] for c in created] == [
        "socks5h://127.0.0.1:2080",
        "socks5h://127.0.0.1:1080",
    ]


# --- client wiring ---------------------------------------------------------


def test_elasticsearch_proxy_node_sets_session_proxies():
    from elastic_transport import NodeConfig, RequestsHttpNode

    node_class = elasticsearch_proxy_kwargs("socks5h://127.0.0.1:1080")["node_class"]
    node = node_class(NodeConfig("https", "es.internal", 9200))

    assert issubclass(node_class, RequestsHttpNode)
    assert node.session.proxies == {
        "http": "socks5h://127.0.0.1:1080",
        "https": "socks5h://127.0.0.1:1080",
    }


def test_opensearch_proxy_connection_sets_session_proxies():
    from opensearchpy import RequestsHttpConnection

    connection_class = opensearch_proxy_kwargs("http://proxy:3128")["connection_class"]
    connection = connection_class(host="os.internal", port=9200)

    assert issubclass(connection_class, RequestsHttpConnection)
    assert connection.session.proxies == {
        "http": "http://proxy:3128",
        "https": "http://proxy:3128",
    }


@pytest.fixture
def system_proxy_env(monkeypatch):
    """A system proxy that must never be used when a cluster proxy is configured."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)


def test_configured_proxy_takes_precedence_over_system_proxy_for_elasticsearch(
    system_proxy_env,
):
    from elastic_transport import NodeConfig

    node_class = elasticsearch_proxy_kwargs("socks5h://127.0.0.1:1080")["node_class"]
    session = node_class(NodeConfig("https", "es.internal", 9200)).session

    settings = session.merge_environment_settings(
        "https://es.internal:9200/", {}, None, None, None
    )

    assert settings["proxies"] == {
        "http": "socks5h://127.0.0.1:1080",
        "https": "socks5h://127.0.0.1:1080",
    }


def test_configured_proxy_takes_precedence_over_system_proxy_for_opensearch(
    system_proxy_env,
):
    connection_class = opensearch_proxy_kwargs("socks5h://127.0.0.1:1080")["connection_class"]
    session = connection_class(host="os.internal", port=9200).session

    settings = session.merge_environment_settings(
        "http://os.internal:9200/", {}, None, None, None
    )

    assert settings["proxies"] == {
        "http": "socks5h://127.0.0.1:1080",
        "https": "socks5h://127.0.0.1:1080",
    }


def test_search_client_without_proxy_keeps_default_transport(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.clients.base.Elasticsearch", lambda **kwargs: captured.update(kwargs)
    )

    SearchClient(_client_config(), "elasticsearch")

    assert "node_class" not in captured
    assert "connection_class" not in captured


def test_search_client_passes_proxy_to_elasticsearch_and_general_client(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.clients.base.Elasticsearch", lambda **kwargs: captured.update(kwargs)
    )

    client = SearchClient(
        _client_config(proxy="socks5h://127.0.0.1:1080"), "elasticsearch"
    )

    assert "node_class" in captured
    assert client.general_client.proxy == "socks5h://127.0.0.1:1080"


def test_search_client_passes_proxy_to_opensearch(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.clients.base.OpenSearch", lambda **kwargs: captured.update(kwargs)
    )

    SearchClient(_client_config(proxy="http://proxy:3128"), "opensearch")

    assert "connection_class" in captured


def test_general_rest_client_passes_proxy_to_httpx(monkeypatch):
    client_kwargs = []

    class FakeResponse:
        headers = {"content-type": "text/plain"}
        text = "ok"

        def raise_for_status(self):
            return None

    class FakeHttpClient:
        def __init__(self, **kwargs):
            client_kwargs.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def request(self, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("src.clients.base.httpx.Client", FakeHttpClient)

    GeneralRestClient(
        base_url="http://es.internal:9200",
        username=None,
        password=None,
        api_key=None,
        verify_certs=False,
        proxy="socks5h://127.0.0.1:1080",
    ).request("GET", "/")

    assert client_kwargs[0]["proxy"] == "socks5h://127.0.0.1:1080"


# --- end to end through a local SOCKS5 proxy -------------------------------


class _Socks5Handler(StreamRequestHandler):
    """Minimal SOCKS5 server (no auth, CONNECT only) that records destinations."""

    def handle(self):
        conn = self.connection
        _, nmethods = struct.unpack("!BB", self._recv(2))
        self._recv(nmethods)
        conn.sendall(b"\x05\x00")

        _, cmd, _, atyp = struct.unpack("!BBBB", self._recv(4))
        if atyp == 3:
            host = self._recv(self._recv(1)[0]).decode()
        elif atyp == 1:
            host = socket.inet_ntoa(self._recv(4))
        else:
            conn.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
            return
        port = struct.unpack("!H", self._recv(2))[0]
        self.server.destinations.append((host, port))

        # Every destination is served by the local test HTTP server.
        upstream = socket.create_connection(("127.0.0.1", self.server.target_port))
        conn.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
        self._pipe(conn, upstream)

    def _recv(self, size):
        data = b""
        while len(data) < size:
            chunk = self.connection.recv(size - len(data))
            if not chunk:
                raise ConnectionError("client closed connection")
            data += chunk
        return data

    @staticmethod
    def _pipe(a, b):
        def forward(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except OSError:
                pass
            finally:
                for s in (src, dst):
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

        t = threading.Thread(target=forward, args=(b, a), daemon=True)
        t.start()
        forward(a, b)
        t.join(timeout=5)


class _JsonHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Elastic-Product", "Elasticsearch")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def socks_proxy():
    http_server = HTTPServer(("127.0.0.1", 0), _JsonHandler)
    threading.Thread(target=http_server.serve_forever, daemon=True).start()

    ThreadingTCPServer.allow_reuse_address = True
    socks_server = ThreadingTCPServer(("127.0.0.1", 0), _Socks5Handler)
    socks_server.daemon_threads = True
    socks_server.destinations = []
    socks_server.target_port = http_server.server_address[1]
    threading.Thread(target=socks_server.serve_forever, daemon=True).start()

    yield socks_server

    socks_server.shutdown()
    http_server.shutdown()


def test_elasticsearch_requests_go_through_socks5h_proxy(socks_proxy, system_proxy_env):
    proxy = f"socks5h://127.0.0.1:{socks_proxy.server_address[1]}"
    # The host name only exists "behind" the proxy: socks5h must not resolve it locally.
    client = SearchClient(
        _client_config(hosts=["http://es.behind-proxy.invalid:9200/prefix"], proxy=proxy),
        "elasticsearch",
    )

    response = client.client.transport.perform_request("GET", "/_cluster/health")

    assert response.body == {"path": "/prefix/_cluster/health"}
    assert socks_proxy.destinations == [("es.behind-proxy.invalid", 9200)]


def test_general_rest_client_goes_through_socks5h_proxy(socks_proxy, system_proxy_env):
    proxy = f"socks5h://127.0.0.1:{socks_proxy.server_address[1]}"
    client = GeneralRestClient(
        base_url="http://es.behind-proxy.invalid:9200/prefix",
        username=None,
        password=None,
        api_key=None,
        verify_certs=False,
        proxy=proxy,
    )

    assert client.request("GET", "/_cat/indices", {"format": "json"}) == {
        "path": "/prefix/_cat/indices?format=json"
    }
    assert socks_proxy.destinations == [("es.behind-proxy.invalid", 9200)]


@pytest.mark.parametrize(
    "value",
    [
        "ftp://user:SECRETPW@proxy:21",
        "socks5h://user:SECRETPW@127.0.0.1:invalid",
        "http://user:SECRETPW@proxy:0",
        "socks5h://user:SECRETPW@",
    ],
)
def test_invalid_proxy_error_does_not_echo_the_url(value):
    with pytest.raises(ValueError) as excinfo:
        normalize_proxy_url(value)
    assert "SECRETPW" not in str(excinfo.value)
    assert "user" not in str(excinfo.value)
