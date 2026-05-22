import asyncio

import pytest
from fastmcp import Client

from tests.e2e.k8s.conftest import (
    list_mcp_tools,
    port_forward,
    wait_for_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


_PORT_OFFSETS = {
    "elasticsearch": 18040,
    "opensearch": 18140,
}


def _list_tools_unauthenticated(url: str):
    async def fetch():
        async with Client(url) as client:
            return await client.list_tools()

    return asyncio.run(fetch())


def test_mcp_endpoint_requires_bearer_token(secure_mcp_server_in_kind):
    engine_type, release = secure_mcp_server_in_kind
    with port_forward(release, _PORT_OFFSETS[engine_type] + 0) as base_url:
        wait_for_http(
            f"{base_url}/healthz",
            headers={"Authorization": "Bearer secret-token"},
        )
        mcp_url = f"{base_url}/mcp"

        with pytest.raises(Exception):
            _list_tools_unauthenticated(mcp_url)


def test_mcp_endpoint_rejects_invalid_bearer_token(secure_mcp_server_in_kind):
    engine_type, release = secure_mcp_server_in_kind
    with port_forward(release, _PORT_OFFSETS[engine_type] + 1) as base_url:
        wait_for_http(
            f"{base_url}/healthz",
            headers={"Authorization": "Bearer secret-token"},
        )
        mcp_url = f"{base_url}/mcp"

        with pytest.raises(Exception):
            list_mcp_tools(mcp_url, auth="wrong-token")


def test_mcp_endpoint_accepts_valid_bearer_token(secure_mcp_server_in_kind):
    engine_type, release = secure_mcp_server_in_kind
    with port_forward(release, _PORT_OFFSETS[engine_type] + 2) as base_url:
        wait_for_http(
            f"{base_url}/healthz",
            headers={"Authorization": "Bearer secret-token"},
        )
        mcp_url = f"{base_url}/mcp"

        tools = list_mcp_tools(mcp_url, auth="secret-token")
        names = {tool.name for tool in tools}
        assert "list_indices" in names
