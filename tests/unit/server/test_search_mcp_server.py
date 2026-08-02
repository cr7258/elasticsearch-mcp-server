import pytest
from fastmcp.server.auth import StaticTokenVerifier

from src import server as server_module
from src.server import SearchMCPServer

pytestmark = pytest.mark.unit


class _FakeManager:
    def get_client(self, cluster=None):
        return self


@pytest.fixture
def stub_dependencies(monkeypatch):
    fake_manager = _FakeManager()
    monkeypatch.setattr(
        server_module,
        "create_search_client_manager",
        lambda engine_type: fake_manager,
    )

    captured = {}

    def fake_register_all_tools(self, tool_classes):
        captured["tool_classes"] = tool_classes

    monkeypatch.setattr(
        server_module.ToolsRegister,
        "register_all_tools",
        fake_register_all_tools,
    )
    return fake_manager, captured


def test_search_mcp_server_creates_static_token_verifier_when_api_key_is_provided(
    stub_dependencies,
):
    server = SearchMCPServer(engine_type="elasticsearch", api_key="secret-token")

    assert isinstance(server.mcp.auth, StaticTokenVerifier)
    assert server.mcp.auth.tokens == {
        "secret-token": {
            "client_id": "mcp_client",
            "scopes": [],
        }
    }


def test_search_mcp_server_warns_when_no_api_key(stub_dependencies, caplog):
    server = SearchMCPServer(engine_type="elasticsearch", api_key=None)

    assert server.mcp.auth is None
    assert caplog.messages == [
        "MCP_API_KEY not set - authentication is DISABLED. Anyone can access this "
        "MCP server without authentication. Set MCP_API_KEY environment variable "
        "to enable authentication."
    ]


def test_search_mcp_server_uses_search_client_manager_from_factory(stub_dependencies):
    fake_manager, _ = stub_dependencies

    server = SearchMCPServer(engine_type="opensearch", api_key=None)

    assert server.search_client is fake_manager
    assert server.engine_type == "opensearch"
    assert server.name == "opensearch-mcp-server"


def test_search_mcp_server_registers_all_tool_classes(stub_dependencies):
    _, captured = stub_dependencies

    SearchMCPServer(engine_type="elasticsearch", api_key=None)

    tool_class_names = [cls.__name__ for cls in captured["tool_classes"]]
    assert tool_class_names == [
        "IndexTools",
        "DocumentTools",
        "ClusterTools",
        "AliasTools",
        "DataStreamTools",
        "GeneralTools",
        "AnalyzerTools",
    ]


def test_search_mcp_server_registers_health_routes(stub_dependencies):
    server = SearchMCPServer(engine_type="elasticsearch", api_key=None)

    paths = {route.path for route in server.mcp._additional_http_routes}
    assert "/healthz" in paths
    assert "/readyz" in paths
