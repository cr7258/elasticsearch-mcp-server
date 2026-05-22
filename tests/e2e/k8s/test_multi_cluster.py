import uuid

import pytest

from tests.e2e.k8s.conftest import (
    call_mcp_tool,
    port_forward,
    wait_for_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


_PORT_OFFSETS = {
    "elasticsearch": 18020,
    "opensearch": 18120,
}


def test_cluster_parameter_routes_through_mcp(multi_cluster_mcp_server_in_kind):
    engine_type, release = multi_cluster_mcp_server_in_kind
    with port_forward(release, _PORT_OFFSETS[engine_type] + 0) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = f"{base_url}/mcp"

        primary_index = f"mcp-k8s-{engine_type}-primary-{uuid.uuid4().hex[:8]}"
        secondary_index = f"mcp-k8s-{engine_type}-secondary-{uuid.uuid4().hex[:8]}"

        try:
            assert call_mcp_tool(
                mcp_url,
                "create_index",
                {"index": primary_index, "cluster": "primary"},
            )["acknowledged"] is True
            assert call_mcp_tool(
                mcp_url,
                "create_index",
                {"index": secondary_index, "cluster": "secondary"},
            )["acknowledged"] is True

            primary_indices = call_mcp_tool(
                mcp_url, "list_indices", {"cluster": "primary"}
            )
            secondary_indices = call_mcp_tool(
                mcp_url, "list_indices", {"cluster": "secondary"}
            )

            assert primary_index in primary_indices
            assert secondary_index not in primary_indices
            assert secondary_index in secondary_indices
            assert primary_index not in secondary_indices
        finally:
            call_mcp_tool(
                mcp_url,
                "delete_index",
                {"index": primary_index, "cluster": "primary"},
            )
            call_mcp_tool(
                mcp_url,
                "delete_index",
                {"index": secondary_index, "cluster": "secondary"},
            )


def test_omitted_cluster_uses_default_cluster_through_mcp(
    multi_cluster_mcp_server_in_kind,
):
    engine_type, release = multi_cluster_mcp_server_in_kind
    with port_forward(release, _PORT_OFFSETS[engine_type] + 1) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = f"{base_url}/mcp"

        index = f"mcp-k8s-{engine_type}-default-{uuid.uuid4().hex[:8]}"

        try:
            assert call_mcp_tool(mcp_url, "create_index", {"index": index})[
                "acknowledged"
            ] is True

            primary_indices = call_mcp_tool(
                mcp_url, "list_indices", {"cluster": "primary"}
            )
            secondary_indices = call_mcp_tool(
                mcp_url, "list_indices", {"cluster": "secondary"}
            )

            assert index in primary_indices
            assert index not in secondary_indices
        finally:
            call_mcp_tool(
                mcp_url, "delete_index", {"index": index, "cluster": "primary"}
            )
