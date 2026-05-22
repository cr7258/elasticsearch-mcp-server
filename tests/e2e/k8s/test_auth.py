import pytest

from tests.e2e.k8s.conftest import list_mcp_tools, mcp_endpoint

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]

API_KEY = "secret-token"
BEARER_HEADER = {"Authorization": f"Bearer {API_KEY}"}


def test_mcp_endpoint_requires_bearer_token(secure_mcp_server_in_kind):
    _, release = secure_mcp_server_in_kind

    with mcp_endpoint(release, auth_header=BEARER_HEADER) as mcp_url:
        with pytest.raises(Exception):
            list_mcp_tools(mcp_url)


def test_mcp_endpoint_rejects_invalid_bearer_token(secure_mcp_server_in_kind):
    _, release = secure_mcp_server_in_kind

    with mcp_endpoint(release, auth_header=BEARER_HEADER) as mcp_url:
        with pytest.raises(Exception):
            list_mcp_tools(mcp_url, auth="wrong-token")


def test_mcp_endpoint_accepts_valid_bearer_token(secure_mcp_server_in_kind):
    _, release = secure_mcp_server_in_kind

    with mcp_endpoint(release, auth_header=BEARER_HEADER) as mcp_url:
        tools = list_mcp_tools(mcp_url, auth=API_KEY)
        names = {tool.name for tool in tools}
        assert "list_indices" in names
