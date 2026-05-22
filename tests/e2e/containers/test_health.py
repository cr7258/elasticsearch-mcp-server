import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.e2e.containers.conftest import (
    docker_available,
    search_client_from_container,
    search_container,
    wait_for_search_client,
)

pytestmark = pytest.mark.e2e

# Bypass any local proxy so 127.0.0.1 traffic reaches the MCP subprocess.
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for(url: str, timeout: int = 120, expected_status: int = 200):
    """Poll ``url`` until it responds with ``expected_status``. The per-request
    timeout is generous so handlers like ``/readyz`` (which may ping the
    search backend during cluster start-up) have enough time to complete."""

    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                if response.status == expected_status:
                    return response.status, response.read().decode("utf-8")
                last_error = f"unexpected status {response.status}"
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


@pytest.fixture(scope="module", params=["elasticsearch", "opensearch"])
def http_mcp_server(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    container = search_container(engine_type)
    container.start()
    try:
        # Make sure the search engine itself is up before launching the
        # MCP server so /readyz does not block on a half-started backend.
        search_client = search_client_from_container(container, engine_type)
        wait_for_search_client(search_client)

        es_host = container.get_container_host_ip()
        es_port = container.get_exposed_port(9200)
        local_port = _free_port()

        env = os.environ.copy()
        env[f"{engine_type.upper()}_HOSTS"] = f"http://{es_host}:{es_port}"
        env["VERIFY_CERTS"] = "false"

        repo_root = Path(__file__).resolve().parents[3]
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "src.server",
                f"{engine_type}-mcp-server",
                "--transport",
                "streamable-http",
                "--host",
                "127.0.0.1",
                "--port",
                str(local_port),
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
            base_url = f"http://127.0.0.1:{local_port}"
            # Wait for liveness first, then readiness so the search backend
            # is fully up before the test methods run.
            _wait_for(f"{base_url}/healthz")
            _wait_for(f"{base_url}/readyz")
            yield engine_type, base_url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        container.stop()


def test_healthz_returns_ok(http_mcp_server):
    _, base_url = http_mcp_server

    status, body = _wait_for(f"{base_url}/healthz")
    assert status == 200
    assert json.loads(body) == {"status": "ok"}


def test_readyz_reports_search_engine_ready(http_mcp_server):
    engine_type, base_url = http_mcp_server

    status, body = _wait_for(f"{base_url}/readyz")
    payload = json.loads(body)
    assert status == 200
    assert payload == {"status": "ok", "search_engine": engine_type}
