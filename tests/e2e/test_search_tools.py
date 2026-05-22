import os
import time
import uuid

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

pytestmark = pytest.mark.e2e

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


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except DockerException:
        return False


def _search_container(engine_type: str) -> DockerContainer:
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


def _wait_for_search_client(search_client: SearchClient, timeout: int = 120) -> None:
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


def _register_tools(search_client: SearchClient) -> dict:
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
    if not _docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    container = _search_container(engine_type)
    container.start()

    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(9200)
        search_client = SearchClient(
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
        _wait_for_search_client(search_client)
        yield engine_type, search_client
    finally:
        container.stop()


def test_index_tools_create_list_get_and_delete_real_index(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)
    index = f"mcp-e2e-{engine_type}-{uuid.uuid4().hex[:8]}"

    try:
        create_response = tools["create_index"](index=index)
        assert create_response["acknowledged"] is True

        indices = tools["list_indices"]()
        assert index in indices

        index_info = tools["get_index"](index=index)
        assert index in index_info
    finally:
        delete_response = tools["delete_index"](index=index)
        assert delete_response["acknowledged"] is True


def test_document_tools_index_get_and_delete_real_document(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)
    index = f"mcp-e2e-docs-{engine_type}-{uuid.uuid4().hex[:8]}"

    try:
        tools["create_index"](index=index)

        document = {"title": "MCP e2e document", "engine": engine_type}
        index_response = tools["index_document"](
            index=index,
            id="doc-1",
            document=document,
        )
        assert index_response["result"] in {"created", "updated"}

        get_response = tools["get_document"](index=index, id="doc-1")
        assert get_response["_source"] == document

        delete_doc_response = tools["delete_document"](index=index, id="doc-1")
        assert delete_doc_response["result"] == "deleted"
    finally:
        delete_index_response = tools["delete_index"](index=index)
        assert delete_index_response["acknowledged"] is True


def test_cluster_general_and_analyzer_tools_query_real_cluster(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)

    health = tools["get_cluster_health"]()
    assert health["status"] in {"green", "yellow"}

    health_via_general_api = tools["general_api_request"]("GET", "/_cluster/health")
    assert health_via_general_api["status"] in {"green", "yellow"}

    analysis = tools["analyze_text"](text="Hello MCP", analyzer="standard")
    tokens = [token["token"] for token in analysis["tokens"]]
    assert tokens == ["hello", "mcp"]


def test_alias_tools_create_get_list_and_delete_real_alias(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)
    index = f"mcp-e2e-alias-{engine_type}-{uuid.uuid4().hex[:8]}"
    alias = f"{index}-alias"

    try:
        tools["create_index"](index=index)

        put_alias_response = tools["put_alias"](index=index, name=alias, body={})
        assert put_alias_response["acknowledged"] is True

        alias_info = tools["get_alias"](index=index)
        assert alias in alias_info[index]["aliases"]

        aliases = tools["list_aliases"]()
        assert alias in aliases

        delete_alias_response = tools["delete_alias"](index=index, name=alias)
        assert delete_alias_response["acknowledged"] is True
    finally:
        delete_index_response = tools["delete_index"](index=index)
        assert delete_index_response["acknowledged"] is True


def test_document_search_and_delete_by_query_real_documents(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)
    index = f"mcp-e2e-search-{engine_type}-{uuid.uuid4().hex[:8]}"

    try:
        tools["create_index"](index=index)
        tools["index_document"](
            index=index,
            id="doc-1",
            document={"message": "delete me", "category": "cleanup"},
        )
        tools["index_document"](
            index=index,
            id="doc-2",
            document={"message": "keep me", "category": "keep"},
        )
        tools["general_api_request"]("POST", f"/{index}/_refresh")

        search_response = tools["search_documents"](
            index=index,
            body={"query": {"term": {"category.keyword": "cleanup"}}},
        )
        assert search_response["hits"]["total"]["value"] == 1

        delete_response = tools["delete_by_query"](
            index=index,
            body={"query": {"term": {"category.keyword": "cleanup"}}},
        )
        assert delete_response["deleted"] == 1
    finally:
        delete_index_response = tools["delete_index"](index=index)
        assert delete_index_response["acknowledged"] is True


def test_data_stream_tools_create_get_and_delete_real_data_stream(search_engine):
    engine_type, search_client = search_engine
    tools = _register_tools(search_client)
    suffix = f"{engine_type}-{uuid.uuid4().hex[:8]}"
    template = f"mcp-e2e-template-{suffix}"
    stream = f"mcp-e2e-stream-{suffix}"
    template_created = False
    stream_created = False

    try:
        tools["general_api_request"](
            "PUT",
            f"/_index_template/{template}",
            body={
                "index_patterns": [f"{stream}*"],
                "data_stream": {},
                "template": {
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "message": {"type": "text"},
                        }
                    }
                },
            },
        )
        template_created = True

        create_response = tools["create_data_stream"](name=stream)
        assert create_response["acknowledged"] is True
        stream_created = True

        stream_response = tools["get_data_stream"](name=stream)
        data_stream_names = [
            item["name"] for item in stream_response.get("data_streams", [])
        ]
        assert stream in data_stream_names
    finally:
        if stream_created:
            delete_stream_response = tools["delete_data_stream"](name=stream)
            assert delete_stream_response["acknowledged"] is True
        if template_created:
            tools["general_api_request"]("DELETE", f"/_index_template/{template}")
