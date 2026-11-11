"""Exercise the installed distribution through its public CLI and MCP endpoint."""

import asyncio
import json
import socket
import subprocess
import time

import httpx
import pytest
from fastmcp import Client

pytestmark = pytest.mark.e2e


def test_server_import_and_cli(installed_package):
    package = installed_package
    subprocess.run(
        [str(package["python"]), "-I", "-c", "import src.server"],
        cwd=package["cwd"], env=package["env"], check=True, timeout=30,
    )
    result = subprocess.run(
        [str(package["cli"]), "--help"],
        cwd=package["cwd"], env=package["env"], check=True, timeout=30,
        capture_output=True, text=True,
    )
    assert "--transport" in result.stdout


def test_installed_error_reporting(installed_package):
    package = installed_package
    subprocess.run(
        [str(package["python"]), "-I", "-m", "pytest", "--import-mode=importlib",
         "-o", "markers=unit: unit tests", "test_error_report.py", "-q"],
        cwd=package["cwd"], env=package["env"], check=True, timeout=60,
    )


@pytest.fixture
def package_server(installed_package):
    package = installed_package
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = package["env"].copy()
    # No backend is needed for health, discovery, or unknown-cluster validation.
    # Explicit configuration keeps local credentials and .env files out of the test.
    env["ELASTICSEARCH_CLUSTERS"] = env["OPENSEARCH_CLUSTERS"] = json.dumps(
        {"default": {"hosts": ["http://127.0.0.1:1"]}}
    )
    for name in ("MCP_API_KEY", "ELASTICSEARCH_CLUSTERS_FILE", "OPENSEARCH_CLUSTERS_FILE",
                 "DEFAULT_CLUSTER", "RESPONSE_FORMAT"):
        env.pop(name, None)
    base_url = f"http://127.0.0.1:{port}"
    log_path = package["cwd"] / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [str(package["cli"]), "--transport", "streamable-http", "--host",
             "127.0.0.1", "--port", str(port), "--path", "/mcp"],
            cwd=package["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail(f"Installed server exited:\n{log_path.read_text()}")
                    try:
                        response = client.get(f"{base_url}/healthz")
                    except httpx.TransportError:
                        time.sleep(0.1)
                        continue
                    if response.status_code == 200:
                        assert response.json() == {"status": "ok"}
                        break
                    time.sleep(0.1)
                else:
                    pytest.fail(f"Installed server did not start:\n{log_path.read_text()}")
            yield base_url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_mcp_initialization_discovery_and_tool_error(package_server):
    async def run():
        async with Client(f"{package_server}/mcp", timeout=10) as client:
            tools = await client.list_tools()
            assert "get_cluster_health" in {tool.name for tool in tools}
            result = await client.call_tool(
                "get_cluster_health", {"cluster": "missing"}, raise_on_error=False,
            )
            assert result.is_error
            text = "\n".join(block.text for block in result.content if block.type == "text")
            assert "Unknown cluster 'missing'" in text

    asyncio.run(run())
