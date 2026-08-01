import sys
from unittest.mock import Mock

import pytest

from src import server

pytestmark = pytest.mark.unit


def test_parse_server_args_defaults_to_stdio_and_mcp_path(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["server"])

    args = server.parse_server_args()

    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path == "/mcp"


def test_parse_server_args_defaults_sse_path(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["server", "--transport", "sse"])

    args = server.parse_server_args()

    assert args.transport == "sse"
    assert args.path == "/sse"


def test_parse_server_args_preserves_explicit_path(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server",
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--path",
            "/custom",
        ],
    )

    args = server.parse_server_args()

    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/custom"


def test_run_search_server_passes_mcp_api_key_for_http_transport(monkeypatch):
    created = []

    class FakeMCP:
        def run(self, **kwargs):
            created[-1]["run_kwargs"] = kwargs

    class FakeSearchMCPServer:
        def __init__(self, engine_type, api_key=None):
            self.name = "fake-server"
            self.logger = type("Logger", (), {"info": lambda *args: None})()
            self.mcp = FakeMCP()
            created.append({"engine_type": engine_type, "api_key": api_key})

    monkeypatch.setenv("MCP_API_KEY", "secret")
    monkeypatch.setattr(server, "SearchMCPServer", FakeSearchMCPServer)

    server.run_search_server("elasticsearch", "streamable-http", "0.0.0.0", 9000, "/mcp")

    assert created == [
        {
            "engine_type": "elasticsearch",
            "api_key": "secret",
            "run_kwargs": {
                "transport": "streamable-http",
                "host": "0.0.0.0",
                "port": 9000,
                "path": "/mcp",
            },
        }
    ]


@pytest.mark.parametrize("host", ["0.0.0.0", "127.0.0.1"])
def test_run_search_server_warns_for_unauthenticated_http_transport(
    monkeypatch, caplog, host
):
    fake_server = Mock()
    fake_server.name = "fake-server"
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.setattr(server, "SearchMCPServer", Mock(return_value=fake_server))

    server.run_search_server("elasticsearch", "streamable-http", host, 8000, "/mcp")

    assert caplog.messages == [
        f"Server is listening on {host}:8000 without authentication. "
        "We recommend setting the MCP_API_KEY "
        "environment variable to enable Bearer token authentication."
    ]


def test_run_search_server_does_not_require_api_key_for_stdio(monkeypatch):
    created = []

    class FakeMCP:
        def run(self, **kwargs):
            created[-1]["run_kwargs"] = kwargs

    class FakeSearchMCPServer:
        def __init__(self, engine_type, api_key=None):
            self.name = "fake-server"
            self.logger = type("Logger", (), {"info": lambda *args: None})()
            self.mcp = FakeMCP()
            created.append({"engine_type": engine_type, "api_key": api_key})

    monkeypatch.setenv("MCP_API_KEY", "secret")
    monkeypatch.setattr(server, "SearchMCPServer", FakeSearchMCPServer)

    server.run_search_server("opensearch", "stdio", "127.0.0.1", 8000, "/mcp")

    assert created == [
        {
            "engine_type": "opensearch",
            "api_key": None,
            "run_kwargs": {"transport": "stdio"},
        }
    ]
