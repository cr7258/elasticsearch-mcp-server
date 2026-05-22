import pytest

from tests.e2e.k8s.conftest import kubectl_json

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


def test_helm_deployment_sets_expected_runtime_environment(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    deployment = kubectl_json("get", "deployment", release)
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
    assert env_by_name["ENGINE_TYPE"]["value"] == engine_type

    if engine_type == "elasticsearch":
        assert env_by_name["ELASTICSEARCH_HOSTS"]["value"].startswith("http://")
    else:
        assert env_by_name["OPENSEARCH_HOSTS"]["value"].startswith("http://")

    assert env_by_name["VERIFY_CERTS"]["value"] == "false"
    assert env_by_name["DISABLE_HIGH_RISK_OPERATIONS"]["value"] == "false"


def test_secure_helm_deployment_renders_auth_and_risk_envs(secure_mcp_server_in_kind):
    engine_type, release = secure_mcp_server_in_kind
    deployment = kubectl_json("get", "deployment", release)
    secret = kubectl_json("get", "secret", release)
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env_by_name = {env["name"]: env for env in container["env"]}

    assert env_by_name["DISABLE_HIGH_RISK_OPERATIONS"]["value"] == "true"
    assert env_by_name["DISABLE_OPERATIONS"]["value"] == "delete_index,delete_document"
    assert env_by_name["MCP_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": release,
        "key": "mcp-api-key",
        "optional": True,
    }
    assert "mcp-api-key" in secret["data"]
