import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from typing import Iterator

import pytest
from fastmcp import Client


CLUSTER_NAME = os.environ.get("KIND_CLUSTER_NAME", "elasticsearch-mcp-server-e2e")
IMAGE_REPOSITORY = os.environ.get(
    "KIND_E2E_IMAGE_REPOSITORY", "elasticsearch-mcp-server"
)
IMAGE_TAG = os.environ.get("KIND_E2E_IMAGE_TAG", "e2e")
IMAGE = f"{IMAGE_REPOSITORY}:{IMAGE_TAG}"
NAMESPACE = "default"

ELASTICSEARCH_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.17.2"
OPENSEARCH_IMAGE = "opensearchproject/opensearch:2.11.0"

ENGINE_TYPES = ["elasticsearch", "opensearch"]


def release_names(engine: str) -> dict:
    return {
        "default": f"mcp-e2e-{engine}",
        "secure": f"mcp-e2e-{engine}-secure",
        "multi": f"mcp-e2e-{engine}-multi",
    }


def _run(command, input_text=None, timeout=300):
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
        timeout=timeout,
    )


def _run_with_retries(command, attempts=3, delay=10, timeout=300):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return _run(command, timeout=timeout)
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(delay)
    raise last_error


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def _kind_cluster_exists(cluster_name: str) -> bool:
    result = subprocess.run(
        ["kind", "get", "clusters"],
        text=True,
        capture_output=True,
        check=False,
    )
    return cluster_name in result.stdout.splitlines()


def kubectl_json(*args):
    result = _run(["kubectl", *args, "-o", "json"])
    return json.loads(result.stdout)


def wait_for_http(url: str, timeout: int = 60, headers: dict | None = None) -> dict:
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            request = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(request, timeout=5) as response:
                return {
                    "status": response.status,
                    "body": response.read().decode("utf-8"),
                }
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def call_mcp_tool(url: str, tool_name: str, arguments: dict | None = None, *, auth=None):
    async def call_tool():
        async with Client(url, auth=auth) as client:
            return await client.call_tool(tool_name, arguments or {})

    result = asyncio.run(call_tool())
    if result.data is not None:
        return result.data
    if result.structured_content:
        if "result" in result.structured_content:
            return result.structured_content["result"]
        return result.structured_content
    if result.content and hasattr(result.content[0], "text"):
        text = result.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return result.content


def list_mcp_tools(url: str, *, auth=None) -> list:
    async def fetch():
        async with Client(url, auth=auth) as client:
            return await client.list_tools()

    return asyncio.run(fetch())


def _free_port() -> int:
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def port_forward(
    service: str, local_port: int | None = None, remote_port: int = 8000
) -> Iterator[str]:
    """Start a ``kubectl port-forward`` and yield the local base URL.

    If ``local_port`` is not given, a free port is allocated automatically so
    callers do not need to manage port number bookkeeping themselves.
    """

    if local_port is None:
        local_port = _free_port()

    process = subprocess.Popen(
        [
            "kubectl",
            "port-forward",
            f"service/{service}",
            f"{local_port}:{remote_port}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Give kubectl a moment to bind the local port before tests connect.
        time.sleep(1)
        yield f"http://127.0.0.1:{local_port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextlib.contextmanager
def mcp_endpoint(
    release: str,
    *,
    auth_header: dict | None = None,
) -> Iterator[str]:
    """Open a port-forward to the MCP server release and yield its ``/mcp`` URL.

    Waits for ``/healthz`` to respond before yielding so callers do not need to
    poll readiness themselves.
    """

    with port_forward(release) as base_url:
        wait_for_http(f"{base_url}/healthz", headers=auth_header)
        yield f"{base_url}/mcp"


def helm_install_args(
    release_name: str,
    fullname_override: str,
    engine: str,
    backend_hosts: str,
):
    args = [
        "helm",
        "upgrade",
        "--install",
        release_name,
        "helm/elasticsearch-mcp-server",
        "--namespace",
        NAMESPACE,
        "--set",
        f"fullnameOverride={fullname_override}",
        "--set",
        f"image.repository={IMAGE_REPOSITORY}",
        "--set",
        f"image.tag={IMAGE_TAG}",
        "--set",
        "image.pullPolicy=Never",
        "--set",
        f"server.engineType={engine}",
        "--set",
        "server.transport=streamable-http",
        "--set",
        "readinessProbe.initialDelaySeconds=2",
        "--set",
        "livenessProbe.initialDelaySeconds=2",
    ]
    if engine == "elasticsearch":
        args.extend(
            [
                "--set",
                f"elasticsearch.hosts={backend_hosts}",
                "--set",
                "elasticsearch.verifyCerts=false",
            ]
        )
    else:
        args.extend(
            [
                "--set",
                f"opensearch.hosts={backend_hosts}",
                "--set",
                "opensearch.verifyCerts=false",
            ]
        )
    return args


def install_release(args, deployment_name: str):
    _run(args, timeout=180)
    _run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{deployment_name}",
            "--timeout=240s",
        ],
        timeout=260,
    )


def uninstall_release(release_name: str):
    subprocess.run(
        ["helm", "uninstall", release_name, "--namespace", NAMESPACE],
        check=False,
        timeout=120,
    )


@pytest.fixture(scope="session")
def kind_cluster():
    missing_tools = [
        tool
        for tool in ("docker", "kind", "kubectl", "helm")
        if not _tool_available(tool)
    ]
    if missing_tools:
        pytest.skip(f"Missing tools for kind e2e: {', '.join(missing_tools)}")

    created_cluster = False
    if not _kind_cluster_exists(CLUSTER_NAME):
        _run(["kind", "create", "cluster", "--name", CLUSTER_NAME], timeout=180)
        created_cluster = True

    try:
        _run(["kubectl", "cluster-info", "--context", f"kind-{CLUSTER_NAME}"])
        yield CLUSTER_NAME
    finally:
        if created_cluster and os.environ.get("KEEP_KIND_CLUSTER") != "true":
            _run(["kind", "delete", "cluster", "--name", CLUSTER_NAME], timeout=120)


@pytest.fixture(scope="session")
def loaded_mcp_image(kind_cluster):
    _run_with_retries(["docker", "build", "-t", IMAGE, "."], timeout=600)
    _run_with_retries(
        ["kind", "load", "docker-image", IMAGE, "--name", kind_cluster], timeout=300
    )
    return IMAGE


def _backend_manifest(engine: str, name: str) -> str:
    if engine == "elasticsearch":
        return f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: elasticsearch
          image: {ELASTICSEARCH_IMAGE}
          ports:
            - containerPort: 9200
          env:
            - name: discovery.type
              value: single-node
            - name: xpack.security.enabled
              value: "false"
            - name: ES_JAVA_OPTS
              value: "-Xms512m -Xmx512m"
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
    - name: http
      port: 9200
      targetPort: 9200
"""

    return f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: opensearch
          image: {OPENSEARCH_IMAGE}
          ports:
            - containerPort: 9200
          env:
            - name: discovery.type
              value: single-node
            - name: DISABLE_SECURITY_PLUGIN
              value: "true"
            - name: OPENSEARCH_JAVA_OPTS
              value: "-Xms512m -Xmx512m"
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
    - name: http
      port: 9200
      targetPort: 9200
"""


def deploy_search_backend(engine: str, name: str) -> str:
    _run(
        ["kubectl", "apply", "-f", "-"],
        input_text=_backend_manifest(engine, name),
        timeout=120,
    )
    _run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{name}",
            "--timeout=240s",
        ],
        timeout=260,
    )
    return f"http://{name}:9200"


@pytest.fixture(scope="session", params=ENGINE_TYPES)
def engine(request):
    return request.param


@pytest.fixture(scope="session")
def search_backend_in_kind(kind_cluster, engine):
    name = f"{engine}-default"
    return engine, deploy_search_backend(engine, name)


@pytest.fixture(scope="session")
def mcp_server_in_kind(kind_cluster, loaded_mcp_image, search_backend_in_kind):
    engine_type, hosts = search_backend_in_kind
    release = release_names(engine_type)["default"]
    install_release(
        helm_install_args(release, release, engine_type, hosts),
        release,
    )
    yield engine_type, release
    uninstall_release(release)


@pytest.fixture(scope="session")
def secure_mcp_server_in_kind(kind_cluster, loaded_mcp_image, search_backend_in_kind):
    engine_type, hosts = search_backend_in_kind
    release = release_names(engine_type)["secure"]
    args = helm_install_args(release, release, engine_type, hosts)
    args.extend(
        [
            "--set",
            "risk.disableHighRiskOperations=true",
            "--set",
            "risk.disabledOperations=delete_index\\,delete_document",
            "--set",
            "auth.credentials.mcpApiKey=secret-token",
        ]
    )

    install_release(args, release)
    yield engine_type, release
    uninstall_release(release)


@pytest.fixture(scope="session")
def multi_cluster_mcp_server_in_kind(kind_cluster, loaded_mcp_image, engine, tmp_path_factory):
    primary_hosts = deploy_search_backend(engine, f"{engine}-primary")
    secondary_hosts = deploy_search_backend(engine, f"{engine}-secondary")

    clusters_config = json.dumps(
        {
            "primary": {"hosts": [primary_hosts]},
            "secondary": {"hosts": [secondary_hosts]},
        }
    )
    cluster_env_var = (
        "ELASTICSEARCH_CLUSTERS" if engine == "elasticsearch" else "OPENSEARCH_CLUSTERS"
    )

    # Helm's --set / --set-string parsers treat commas as list separators,
    # which mangles JSON values like ELASTICSEARCH_CLUSTERS. Drop the cluster
    # config into a values file (JSON is valid YAML) so commas survive.
    values_payload = {
        "extraEnv": [
            {"name": cluster_env_var, "value": clusters_config},
            {"name": "DEFAULT_CLUSTER", "value": "primary"},
        ]
    }
    values_dir = tmp_path_factory.mktemp(f"helm-values-{engine}")
    values_path = values_dir / "extra-env.json"
    values_path.write_text(json.dumps(values_payload))

    release = release_names(engine)["multi"]
    args = helm_install_args(release, release, engine, primary_hosts)
    args.extend(["--values", str(values_path)])

    install_release(args, release)
    yield engine, release
    uninstall_release(release)
