import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from fastmcp import Client

from tests.e2e.containers.conftest import (
    docker_available,
    search_container,
)

pytestmark = pytest.mark.e2e

# Local proxies (Privoxy, Charles, etc.) frequently mangle 127.0.0.1 traffic and
# return 503 before the request reaches uvicorn. Bypass them for the test client.
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(url: str, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


@pytest.fixture(scope="module")
def secured_http_mcp_server():
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    container = search_container("elasticsearch")
    container.start()
    try:
        es_host = container.get_container_host_ip()
        es_port = container.get_exposed_port(9200)

        port = _free_port()
        env = os.environ.copy()
        env["ELASTICSEARCH_HOSTS"] = f"http://{es_host}:{es_port}"
        env["MCP_API_KEY"] = "secret-token"
        env["VERIFY_CERTS"] = "false"

        repo_root = Path(__file__).resolve().parents[3]
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "src.server",
                "elasticsearch-mcp-server",
                "--transport",
                "streamable-http",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--path",
                "/mcp",
            ],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            _wait_for_health(f"http://127.0.0.1:{port}/healthz")
            yield f"http://127.0.0.1:{port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        container.stop()


def _list_tools(url: str, auth=None):
    async def fetch():
        async with Client(url, auth=auth) as client:
            return await client.list_tools()

    return asyncio.run(fetch())


def test_mcp_endpoint_rejects_request_without_bearer_token(secured_http_mcp_server):
    mcp_url = f"{secured_http_mcp_server}/mcp"

    with pytest.raises(Exception):
        _list_tools(mcp_url)


def test_mcp_endpoint_rejects_request_with_invalid_bearer_token(secured_http_mcp_server):
    mcp_url = f"{secured_http_mcp_server}/mcp"

    with pytest.raises(Exception):
        _list_tools(mcp_url, auth="wrong-token")


def test_mcp_endpoint_accepts_request_with_valid_bearer_token(secured_http_mcp_server):
    mcp_url = f"{secured_http_mcp_server}/mcp"

    tools = _list_tools(mcp_url, auth="secret-token")
    names = {tool.name for tool in tools}
    assert "list_indices" in names
