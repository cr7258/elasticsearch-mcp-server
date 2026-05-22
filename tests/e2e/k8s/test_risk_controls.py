import pytest

from tests.e2e.k8s.conftest import (
    list_mcp_tools,
    port_forward,
    wait_for_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


def test_disabled_operations_are_not_listed_through_mcp(secure_mcp_server_in_kind):
    with port_forward("mcp-e2e-secure", 18030) as base_url:
        wait_for_http(
            f"{base_url}/healthz",
            headers={"Authorization": "Bearer secret-token"},
        )
        mcp_url = f"{base_url}/mcp"

        tools = list_mcp_tools(mcp_url, auth="secret-token")
        names = {tool.name for tool in tools}

        assert "delete_index" not in names
        assert "delete_document" not in names
        assert "list_indices" in names
        assert "create_index" in names
        assert "index_document" in names
