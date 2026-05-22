import asyncio

import pytest
from fastmcp import Client

from tests.e2e.containers.conftest import (
    ENGINE_TYPES,
    docker_available,
    http_mcp_server_with_real_backend,
)

pytestmark = pytest.mark.e2e

API_KEY = "secret-token"


@pytest.fixture(scope="module", params=ENGINE_TYPES)
def secured_http_mcp_server(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    with http_mcp_server_with_real_backend(
        engine_type, extra_env={"MCP_API_KEY": API_KEY}
    ) as base_url:
        yield engine_type, base_url


def _list_tools(url: str, auth=None):
    async def fetch():
        async with Client(url, auth=auth) as client:
            return await client.list_tools()

    return asyncio.run(fetch())


def test_mcp_endpoint_rejects_request_without_bearer_token(secured_http_mcp_server):
    _, base_url = secured_http_mcp_server

    with pytest.raises(Exception):
        _list_tools(f"{base_url}/mcp")


def test_mcp_endpoint_rejects_request_with_invalid_bearer_token(secured_http_mcp_server):
    _, base_url = secured_http_mcp_server

    with pytest.raises(Exception):
        _list_tools(f"{base_url}/mcp", auth="wrong-token")


def test_mcp_endpoint_accepts_request_with_valid_bearer_token(secured_http_mcp_server):
    _, base_url = secured_http_mcp_server

    tools = _list_tools(f"{base_url}/mcp", auth=API_KEY)
    names = {tool.name for tool in tools}
    assert "list_indices" in names
