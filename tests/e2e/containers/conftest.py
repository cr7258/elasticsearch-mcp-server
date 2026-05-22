import os
import time

# Avoid pulling the Ryuk sidecar image in CI. Containers are stopped by fixtures.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

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


def search_client_from_container(container: DockerContainer, engine_type: str) -> SearchClient:
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


@pytest.fixture(scope="session", params=["elasticsearch", "opensearch"])
def search_engine(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    container = search_container(engine_type)
    container.start()

    try:
        search_client = search_client_from_container(container, engine_type)
        wait_for_search_client(search_client)
        yield engine_type, search_client
    finally:
        container.stop()
