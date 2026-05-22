import pytest

from src.tools.alias import AliasTools
from src.tools.analyzer import AnalyzerTools
from src.tools.cluster import ClusterTools
from src.tools.data_stream import DataStreamTools
from src.tools.document import DocumentTools
from src.tools.general import GeneralTools
from src.tools.index import IndexTools

pytestmark = pytest.mark.unit


class FakeToolClient:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def __getattr__(self, method_name):
        def recorder(*args, **kwargs):
            self.calls.append((method_name, args, kwargs))
            return {"cluster": self.name, "method": method_name, "kwargs": kwargs}

        return recorder


class FakeClientManager:
    def __init__(self):
        self.clients = {
            "prod": FakeToolClient("prod"),
            "staging": FakeToolClient("staging"),
        }
        self.requested_clusters = []

    def get_client(self, cluster=None):
        cluster_name = cluster or "prod"
        self.requested_clusters.append(cluster_name)
        return self.clients[cluster_name]


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *args, **kwargs):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def test_tool_uses_requested_cluster_client():
    manager = FakeClientManager()
    mcp = FakeMCP()
    IndexTools(manager).register_tools(mcp)

    result = mcp.tools["list_indices"](cluster="staging")

    assert result == {"cluster": "staging", "method": "list_indices", "kwargs": {}}
    assert manager.requested_clusters == ["staging"]


def test_tool_uses_default_cluster_when_cluster_is_omitted():
    manager = FakeClientManager()
    mcp = FakeMCP()
    IndexTools(manager).register_tools(mcp)

    result = mcp.tools["list_indices"]()

    assert result == {"cluster": "prod", "method": "list_indices", "kwargs": {}}
    assert manager.requested_clusters == ["prod"]


@pytest.mark.parametrize(
    (
        "tool_class",
        "tool_name",
        "args",
        "kwargs",
        "expected_method",
        "expected_args",
        "expected_kwargs",
    ),
    [
        (IndexTools, "list_indices", (), {}, "list_indices", (), {}),
        (IndexTools, "get_index", (), {"index": "logs"}, "get_index", (), {"index": "logs"}),
        (
            IndexTools,
            "create_index",
            (),
            {"index": "logs", "body": {"settings": {}}},
            "create_index",
            (),
            {"index": "logs", "body": {"settings": {}}},
        ),
        (
            IndexTools,
            "delete_index",
            (),
            {"index": "logs"},
            "delete_index",
            (),
            {"index": "logs"},
        ),
        (
            DocumentTools,
            "search_documents",
            (),
            {"index": "logs", "body": {"query": {"match_all": {}}}},
            "search_documents",
            (),
            {"index": "logs", "body": {"query": {"match_all": {}}}},
        ),
        (
            DocumentTools,
            "index_document",
            (),
            {"index": "logs", "id": "1", "document": {"message": "hello"}},
            "index_document",
            (),
            {"index": "logs", "id": "1", "document": {"message": "hello"}},
        ),
        (
            DocumentTools,
            "get_document",
            (),
            {"index": "logs", "id": "1"},
            "get_document",
            (),
            {"index": "logs", "id": "1"},
        ),
        (
            DocumentTools,
            "delete_document",
            (),
            {"index": "logs", "id": "1"},
            "delete_document",
            (),
            {"index": "logs", "id": "1"},
        ),
        (
            DocumentTools,
            "delete_by_query",
            (),
            {"index": "logs", "body": {"query": {"match_all": {}}}},
            "delete_by_query",
            (),
            {"index": "logs", "body": {"query": {"match_all": {}}}},
        ),
        (ClusterTools, "get_cluster_health", (), {}, "get_cluster_health", (), {}),
        (ClusterTools, "get_cluster_stats", (), {}, "get_cluster_stats", (), {}),
        (AliasTools, "list_aliases", (), {}, "list_aliases", (), {}),
        (AliasTools, "get_alias", (), {"index": "logs"}, "get_alias", (), {"index": "logs"}),
        (
            AliasTools,
            "put_alias",
            (),
            {"index": "logs", "name": "logs-alias", "body": {}},
            "put_alias",
            (),
            {"index": "logs", "name": "logs-alias", "body": {}},
        ),
        (
            AliasTools,
            "delete_alias",
            (),
            {"index": "logs", "name": "logs-alias"},
            "delete_alias",
            (),
            {"index": "logs", "name": "logs-alias"},
        ),
        (
            AnalyzerTools,
            "analyze_text",
            (),
            {
                "text": "Hello World",
                "analyzer": "standard",
                "explain": True,
                "attributes": ["type"],
            },
            "analyze_text",
            (),
            {
                "text": "Hello World",
                "index": None,
                "analyzer": "standard",
                "tokenizer": None,
                "filter": None,
                "char_filter": None,
                "explain": True,
                "attributes": ["type"],
            },
        ),
        (
            DataStreamTools,
            "create_data_stream",
            (),
            {"name": "logs-stream"},
            "create_data_stream",
            (),
            {"name": "logs-stream"},
        ),
        (
            DataStreamTools,
            "get_data_stream",
            (),
            {"name": "logs-stream"},
            "get_data_stream",
            (),
            {"name": "logs-stream"},
        ),
        (
            DataStreamTools,
            "delete_data_stream",
            (),
            {"name": "logs-stream"},
            "delete_data_stream",
            (),
            {"name": "logs-stream"},
        ),
        (
            GeneralTools,
            "general_api_request",
            (),
            {
                "method": "GET",
                "path": "/_cluster/health",
                "params": {"pretty": "true"},
                "body": None,
            },
            "general_api_request",
            ("GET", "/_cluster/health", {"pretty": "true"}, None),
            {},
        ),
    ],
)
def test_tool_forwards_arguments_to_selected_cluster_client(
    tool_class,
    tool_name,
    args,
    kwargs,
    expected_method,
    expected_args,
    expected_kwargs,
):
    manager = FakeClientManager()
    mcp = FakeMCP()
    tool_class(manager).register_tools(mcp)

    result = mcp.tools[tool_name](*args, **kwargs, cluster="staging")

    assert result == {
        "cluster": "staging",
        "method": expected_method,
        "kwargs": expected_kwargs,
    }
    assert manager.clients["staging"].calls == [
        (expected_method, expected_args, expected_kwargs)
    ]
