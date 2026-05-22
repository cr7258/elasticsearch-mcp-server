import pytest

from tests.e2e.k8s.conftest import port_forward, wait_for_http

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


def test_helm_deployment_serves_health_and_readiness(mcp_server_in_kind):
    with port_forward("mcp-e2e", 18000) as base_url:
        health = wait_for_http(f"{base_url}/healthz")
        assert health["status"] == 200
        assert '"status":"ok"' in health["body"]

        ready = wait_for_http(f"{base_url}/readyz")
        assert ready["status"] == 200
        assert '"status":"ok"' in ready["body"]
        assert '"search_engine":"elasticsearch"' in ready["body"]
