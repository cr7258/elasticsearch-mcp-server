import asyncio
import logging
import time

import httpx
import pytest
from fastmcp import FastMCP

from src.server import SearchMCPServer

pytestmark = pytest.mark.unit


class _FakeRawClient:
    def __init__(self, *, ping_return=True, ping_exc=None, ping_delay=0.0):
        self.ping_return = ping_return
        self.ping_exc = ping_exc
        self.ping_delay = ping_delay

    def ping(self):
        if self.ping_delay:
            time.sleep(self.ping_delay)
        if self.ping_exc is not None:
            raise self.ping_exc
        return self.ping_return


class _FakeSearchClientManager:
    def __init__(self, raw_client):
        self._client = type("Wrapper", (), {"client": raw_client})()

    def get_client(self, cluster=None):
        return self._client


def _make_server_with_health_routes(raw_client) -> SearchMCPServer:
    server = SearchMCPServer.__new__(SearchMCPServer)
    server.engine_type = "elasticsearch"
    server.logger = logging.getLogger("test_health_routes")
    server.mcp = FastMCP("test-server")
    server.search_client = _FakeSearchClientManager(raw_client)
    server._register_health_routes()
    return server


async def _request(server: SearchMCPServer, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_healthz_returns_ok():
    server = _make_server_with_health_routes(_FakeRawClient())

    response = asyncio.run(_request(server, "/healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ok_when_search_client_is_reachable():
    server = _make_server_with_health_routes(_FakeRawClient(ping_return=True))

    response = asyncio.run(_request(server, "/readyz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "search_engine": "elasticsearch"}


def test_readyz_returns_503_when_ping_returns_false():
    server = _make_server_with_health_routes(_FakeRawClient(ping_return=False))

    response = asyncio.run(_request(server, "/readyz"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "search_engine": "elasticsearch",
    }


def test_readyz_returns_503_when_ping_raises():
    server = _make_server_with_health_routes(
        _FakeRawClient(ping_exc=RuntimeError("connection refused"))
    )

    response = asyncio.run(_request(server, "/readyz"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "search_engine": "elasticsearch",
    }


def test_readyz_returns_503_on_timeout(monkeypatch):
    server = _make_server_with_health_routes(_FakeRawClient(ping_return=True))

    async def _wait_for(coro, timeout):
        # Ensure the inner coroutine is closed so we do not get
        # "coroutine was never awaited" runtime warnings.
        coro.close()
        raise asyncio.TimeoutError()

    monkeypatch.setattr("src.server.asyncio.wait_for", _wait_for)

    response = asyncio.run(_request(server, "/readyz"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "timeout",
        "search_engine": "elasticsearch",
    }
