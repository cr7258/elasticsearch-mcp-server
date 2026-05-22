import uuid

import pytest

from src.clients import SearchClientManager
from tests.e2e.containers.conftest import (
    docker_available,
    register_tools,
    search_client_from_container,
    search_container,
    wait_for_search_client,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module", params=["elasticsearch", "opensearch"])
def two_search_clusters(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    containers = [search_container(engine_type), search_container(engine_type)]
    for container in containers:
        container.start()

    try:
        clients = []
        for container in containers:
            client = search_client_from_container(container, engine_type)
            wait_for_search_client(client)
            clients.append(client)
        yield engine_type, clients
    finally:
        for container in containers:
            container.stop()


def test_cluster_parameter_routes_tool_calls_to_named_search_cluster(
    two_search_clusters,
):
    engine_type, (primary_client, secondary_client) = two_search_clusters
    manager = SearchClientManager(
        {"primary": primary_client, "secondary": secondary_client},
        default_cluster="primary",
    )
    tools = register_tools(manager)

    primary_index = f"mcp-e2e-{engine_type}-primary-{uuid.uuid4().hex[:8]}"
    secondary_index = f"mcp-e2e-{engine_type}-secondary-{uuid.uuid4().hex[:8]}"

    try:
        assert tools["create_index"](index=primary_index, cluster="primary")[
            "acknowledged"
        ] is True
        assert tools["create_index"](index=secondary_index, cluster="secondary")[
            "acknowledged"
        ] is True

        primary_indices = tools["list_indices"](cluster="primary")
        secondary_indices = tools["list_indices"](cluster="secondary")

        assert primary_index in primary_indices
        assert secondary_index not in primary_indices
        assert secondary_index in secondary_indices
        assert primary_index not in secondary_indices
    finally:
        if primary_index in tools["list_indices"](cluster="primary"):
            tools["delete_index"](index=primary_index, cluster="primary")
        if secondary_index in tools["list_indices"](cluster="secondary"):
            tools["delete_index"](index=secondary_index, cluster="secondary")


def test_omitted_cluster_uses_default_search_cluster(two_search_clusters):
    engine_type, (primary_client, secondary_client) = two_search_clusters
    manager = SearchClientManager(
        {"primary": primary_client, "secondary": secondary_client},
        default_cluster="primary",
    )
    tools = register_tools(manager)
    index = f"mcp-e2e-{engine_type}-default-{uuid.uuid4().hex[:8]}"

    try:
        assert tools["create_index"](index=index)["acknowledged"] is True

        assert index in tools["list_indices"](cluster="primary")
        assert index not in tools["list_indices"](cluster="secondary")
    finally:
        if index in tools["list_indices"](cluster="primary"):
            tools["delete_index"](index=index, cluster="primary")
