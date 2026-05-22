import pytest

from tests.e2e.k8s.conftest import kubectl_json

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


def test_helm_deployment_sets_expected_runtime_environment(mcp_server_in_kind):
    deployment = kubectl_json("get", "deployment", "mcp-e2e")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env_by_name = {env["name"]: env for env in container["env"]}

    assert container["args"] == [
        "--transport",
        "streamable-http",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--path",
        "/mcp",
    ]
    assert env_by_name["ENGINE_TYPE"]["value"] == "elasticsearch"
    assert env_by_name["ELASTICSEARCH_HOSTS"]["value"] == "http://elasticsearch:9200"
    assert env_by_name["VERIFY_CERTS"]["value"] == "false"
    assert env_by_name["DISABLE_HIGH_RISK_OPERATIONS"]["value"] == "false"


def test_secure_helm_deployment_renders_auth_and_risk_envs(secure_mcp_server_in_kind):
    deployment = kubectl_json("get", "deployment", "mcp-e2e-secure")
    secret = kubectl_json("get", "secret", "mcp-e2e-secure")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env_by_name = {env["name"]: env for env in container["env"]}

    assert env_by_name["DISABLE_HIGH_RISK_OPERATIONS"]["value"] == "true"
    assert env_by_name["DISABLE_OPERATIONS"]["value"] == "delete_index,delete_document"
    assert env_by_name["MCP_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "mcp-e2e-secure",
        "key": "mcp-api-key",
        "optional": True,
    }
    assert "mcp-api-key" in secret["data"]
