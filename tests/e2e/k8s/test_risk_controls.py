import pytest

from tests.e2e.k8s.conftest import list_mcp_tools, mcp_endpoint

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]

API_KEY = "secret-token"
BEARER_HEADER = {"Authorization": f"Bearer {API_KEY}"}


def test_disabled_operations_are_not_listed_through_mcp(secure_mcp_server_in_kind):
    _, release = secure_mcp_server_in_kind

    with mcp_endpoint(release, auth_header=BEARER_HEADER) as mcp_url:
        tools = list_mcp_tools(mcp_url, auth=API_KEY)
        names = {tool.name for tool in tools}

        assert "delete_index" not in names
        assert "delete_document" not in names
        assert "list_indices" in names
        assert "create_index" in names
        assert "index_document" in names
