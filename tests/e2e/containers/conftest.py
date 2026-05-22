import contextlib
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

# Avoid pulling the Ryuk sidecar image in CI. Containers are stopped by fixtures.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Local proxies (Privoxy, Charles, etc.) frequently mangle 127.0.0.1 traffic and
# return 503 before the request reaches uvicorn. Bypass them for any test client.
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

import docker
import pytest
from docker.errors import DockerException
from testcontainers.core.container import DockerContainer

from src.clients.common.client import SearchClient
from src.tools.alias import AliasTools
from src.tools.analyzer import AnalyzerTools
from src.tools.cluster import ClusterTools
from src.tools.data_stream import DataStreamTools
from src.tools.document import DocumentTools
from src.tools.general import GeneralTools
from src.tools.index import IndexTools

ELASTICSEARCH_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.17.2"
OPENSEARCH_IMAGE = "opensearchproject/opensearch:2.11.0"
ENGINE_TYPES = ["elasticsearch", "opensearch"]


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *args, **kwargs):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except DockerException:
        return False


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_http(
    url: str,
    timeout: int = 120,
    expected_status: int = 200,
    request_timeout: int = 8,
):
    """Poll ``url`` until it responds with ``expected_status`` or ``timeout``."""

    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=request_timeout) as response:
                if response.status == expected_status:
                    return response.status, response.read().decode("utf-8")
                last_error = f"unexpected status {response.status}"
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def search_container(engine_type: str) -> DockerContainer:
    if engine_type == "elasticsearch":
        return (
            DockerContainer(ELASTICSEARCH_IMAGE)
            .with_exposed_ports(9200)
            .with_env("discovery.type", "single-node")
            .with_env("xpack.security.enabled", "false")
            .with_env("ES_JAVA_OPTS", "-Xms512m -Xmx512m")
        )

    return (
        DockerContainer(OPENSEARCH_IMAGE)
        .with_exposed_ports(9200)
        .with_env("discovery.type", "single-node")
        .with_env("DISABLE_SECURITY_PLUGIN", "true")
        .with_env("OPENSEARCH_JAVA_OPTS", "-Xms512m -Xmx512m")
    )


def search_client_from_container(
    container: DockerContainer, engine_type: str
) -> SearchClient:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(9200)
    return SearchClient(
        {
            "hosts": [f"http://{host}:{port}"],
            "username": None,
            "password": None,
            "api_key": None,
            "verify_certs": False,
            "timeout": 30,
        },
        engine_type,
    )


def wait_for_search_client(search_client: SearchClient, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            if search_client.client.ping():
                return
        except Exception as exc:
            last_error = exc
        time.sleep(2)

    raise TimeoutError(f"Search engine did not become ready: {last_error}")


def register_tools(search_client) -> dict:
    mcp = FakeMCP()
    AliasTools(search_client).register_tools(mcp)
    AnalyzerTools(search_client).register_tools(mcp)
    ClusterTools(search_client).register_tools(mcp)
    DataStreamTools(search_client).register_tools(mcp)
    IndexTools(search_client).register_tools(mcp)
    DocumentTools(search_client).register_tools(mcp)
    GeneralTools(search_client).register_tools(mcp)
    return mcp.tools


@contextlib.contextmanager
def http_mcp_server_subprocess(
    engine_type: str,
    backend_hosts: str,
    *,
    extra_env: Optional[dict] = None,
) -> Iterator[str]:
    """Start the MCP server as a subprocess on a free local port and yield its
    base URL. Waits for ``/healthz`` and ``/readyz`` to be 200 before yielding.
    """

    local_port = free_port()
    env = os.environ.copy()
    env[f"{engine_type.upper()}_HOSTS"] = backend_hosts
    env["VERIFY_CERTS"] = "false"
    if extra_env:
        env.update(extra_env)

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

    base_url = f"http://127.0.0.1:{local_port}"
    try:
        wait_for_http(f"{base_url}/healthz")
        wait_for_http(f"{base_url}/readyz")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="session", params=ENGINE_TYPES)
def search_engine(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    container = search_container(engine_type)
    container.start()

    try:
        client = search_client_from_container(container, engine_type)
        wait_for_search_client(client)
        yield engine_type, client
    finally:
        container.stop()


@contextlib.contextmanager
def http_mcp_server_with_real_backend(
    engine_type: str,
    *,
    extra_env: Optional[dict] = None,
) -> Iterator[str]:
    """Start a real search backend container and an MCP server pointing to it.

    Yields the MCP server base URL and tears down both processes on exit.
    """

    container = search_container(engine_type)
    container.start()
    try:
        # Make sure the search engine itself is up before launching the MCP
        # server so /readyz does not block on a half-started backend.
        client = search_client_from_container(container, engine_type)
        wait_for_search_client(client)

        backend_hosts = (
            f"http://{container.get_container_host_ip()}:"
            f"{container.get_exposed_port(9200)}"
        )
        with http_mcp_server_subprocess(
            engine_type, backend_hosts, extra_env=extra_env
        ) as base_url:
            yield base_url
    finally:
        container.stop()
