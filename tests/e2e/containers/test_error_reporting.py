"""End-to-end proof that error reasons reach callers and never reach logs.

The real MCP server runs as a subprocess with all output written to a file, so
the log assertions cover every logger (including non-propagating ones such as
fastmcp, mcp, opensearchpy.trace and elastic_transport.*).
"""

import asyncio
import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastmcp import Client

from tests.e2e.containers.conftest import free_port, wait_for_http

pytestmark = pytest.mark.e2e

CANARY_COL = "CANARY_COL_7f3"
CANARY_QUERY = "CANARY_Q_7f3"
CANARY_VALUE = "CANARY_VAL_7f3"
CANARY_USER = "canary_user_7f3"
CANARY_PASSWORD = "canary_pass_7f3"


@contextlib.contextmanager
def _server_with_log(engine_type: str, hosts: str, log_path: Path):
    """Run the real server; yield (base_url, log_offset_after_startup)."""
    port = free_port()
    env = os.environ.copy()
    env[f"{engine_type.upper()}_HOSTS"] = hosts
    env[f"{engine_type.upper()}_USERNAME"] = CANARY_USER
    env[f"{engine_type.upper()}_PASSWORD"] = CANARY_PASSWORD
    env["VERIFY_CERTS"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    repo_root = Path(__file__).resolve().parents[3]
    with open(log_path, "wb") as log:
        process = subprocess.Popen(
            [
                sys.executable, "-m", "src.server", f"{engine_type}-mcp-server",
                "--transport", "streamable-http", "--host", "127.0.0.1",
                "--port", str(port), "--path", "/mcp",
            ],
            cwd=repo_root, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_for_http(f"{base_url}/healthz")
            wait_for_http(f"{base_url}/readyz")
            yield base_url, log_path.stat().st_size
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="module")
def reporting_env(search_engine, tmp_path_factory):
    engine_type, search_client = search_engine
    hosts = search_client.config["hosts"][0]
    index = f"mcp-e2e-errrep-{uuid.uuid4().hex[:8]}"
    search_client.client.indices.create(
        index=index,
        body={"mappings": {"properties": {"@timestamp": {"type": "date"}}}},
    )
    search_client.client.index(
        index=index,
        id="1",
        body={"title": CANARY_VALUE, "@timestamp": "2024-01-01T00:00:00Z"},
        refresh=True,
    )
    log_path = tmp_path_factory.mktemp("errrep") / "server.log"
    try:
        with _server_with_log(engine_type, hosts, log_path) as (base_url, offset):
            yield {
                "engine": engine_type,
                "url": f"{base_url}/mcp",
                "index": index,
                "hosts": hosts,
                "log_path": log_path,
                "offset": offset,
            }
    finally:
        search_client.client.indices.delete(index=index, ignore_unavailable=True)


def _call(url: str, tool: str, args: dict):
    async def run():
        async with Client(url) as client:
            return await client.call_tool(tool, args, raise_on_error=False)

    return asyncio.run(run())


def _text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


def _bad_request(env: dict, canary_params: dict | None = None):
    """A request that the cluster rejects with a descriptive reason."""
    index = env["index"]
    if env["engine"] == "elasticsearch":
        body = {"query": f"FROM {index} | KEEP {CANARY_COL}"}
        return _call(
            env["url"],
            "general_api_request",
            {"method": "POST", "path": "/_query", "body": body, "params": canary_params},
        )
    body = {"query": {"no_such_clause": {CANARY_COL: CANARY_VALUE}}}
    return _call(
        env["url"],
        "general_api_request",
        {"method": "POST", "path": f"/{index}/_search", "body": body, "params": canary_params},
    )


def test_general_api_bad_request_returns_reason(reporting_env):
    result = _bad_request(reporting_env)
    text = _text(result)
    assert result.is_error is True
    if reporting_env["engine"] == "elasticsearch":
        assert "Unknown column" in text
        assert CANARY_COL in text
    else:
        assert "no_such_clause" in text
        assert "parsing_exception: unknown query [no_such_clause]" in text, text
    parts = urlsplit(reporting_env["hosts"])
    assert f"{parts.hostname}:{parts.port}" not in text
    assert CANARY_USER not in text


def test_dedicated_tool_error_has_no_wrapper(reporting_env):
    body = {"query": {"range": {"@timestamp": {"gte": "not-a-date"}}}}
    index = reporting_env["index"]
    result = _call(
        reporting_env["url"], "search_documents", {"index": index, "body": body}
    )
    text = _text(result)
    assert result.is_error is True
    assert "failed to parse date field" in text
    assert "structured_content must be a dict" not in text


def test_logs_carry_no_markers(reporting_env):
    env = reporting_env
    first = _bad_request(env)
    second = _call(
        env["url"],
        "general_api_request",
        {
            "method": "GET",
            "path": f"/{env['index']}/_search",
            "params": {"canary": CANARY_QUERY},
        },
    )
    third = _bad_request(env, canary_params={"canary": CANARY_QUERY})
    assert first.is_error and second.is_error and third.is_error

    with open(env["log_path"], "rb") as f:
        f.seek(env["offset"])
        logs = f.read().decode("utf-8", "replace")

    # Not vacuous: the server logged the failures, in the safe form.
    assert logs.count("general_api_request failed: 400") >= 2, logs
    assert "general_api_request failed: 400 POST" in logs, logs

    parts = urlsplit(env["hosts"])
    host_port = f"{parts.hostname}:{parts.port}"
    for marker in (CANARY_COL, CANARY_QUERY, CANARY_VALUE, CANARY_USER,
                   CANARY_PASSWORD, host_port):
        assert marker not in logs, f"{marker!r} leaked into server logs:\n{logs}"
