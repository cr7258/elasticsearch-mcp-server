import json

import pytest

from tests.e2e.containers.conftest import (
    ENGINE_TYPES,
    docker_available,
    http_mcp_server_with_real_backend,
    wait_for_http,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module", params=ENGINE_TYPES)
def http_mcp_server(request):
    if not docker_available():
        pytest.skip("Docker is required for e2e tests")

    engine_type = request.param
    with http_mcp_server_with_real_backend(engine_type) as base_url:
        yield engine_type, base_url


def test_healthz_returns_ok(http_mcp_server):
    _, base_url = http_mcp_server

    status, body = wait_for_http(f"{base_url}/healthz")
    assert status == 200
    assert json.loads(body) == {"status": "ok"}


def test_readyz_reports_search_engine_ready(http_mcp_server):
    engine_type, base_url = http_mcp_server

    status, body = wait_for_http(f"{base_url}/readyz")
    payload = json.loads(body)
    assert status == 200
    assert payload == {"status": "ok", "search_engine": engine_type}
