import uuid

import pytest

from tests.e2e.k8s.conftest import call_mcp_tool, mcp_endpoint

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


def test_cluster_parameter_routes_through_mcp(multi_cluster_mcp_server_in_kind):
    engine_type, release = multi_cluster_mcp_server_in_kind
    primary_index = f"mcp-k8s-{engine_type}-primary-{uuid.uuid4().hex[:8]}"
    secondary_index = f"mcp-k8s-{engine_type}-secondary-{uuid.uuid4().hex[:8]}"

    with mcp_endpoint(release) as mcp_url:
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
    index = f"mcp-k8s-{engine_type}-default-{uuid.uuid4().hex[:8]}"

    with mcp_endpoint(release) as mcp_url:
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
