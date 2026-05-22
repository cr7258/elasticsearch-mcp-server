import os
import shutil
import subprocess
import time
import urllib.request

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]

CLUSTER_NAME = os.environ.get("KIND_CLUSTER_NAME", "elasticsearch-mcp-server-e2e")
IMAGE_REPOSITORY = os.environ.get(
    "KIND_E2E_IMAGE_REPOSITORY", "elasticsearch-mcp-server"
)
IMAGE_TAG = os.environ.get("KIND_E2E_IMAGE_TAG", "e2e")
IMAGE = f"{IMAGE_REPOSITORY}:{IMAGE_TAG}"
RELEASE_NAME = "mcp-e2e"
NAMESPACE = "default"


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


@pytest.fixture(scope="session")
def kind_cluster():
    missing_tools = [
        tool for tool in ("docker", "kind", "kubectl", "helm") if not _tool_available(tool)
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


@pytest.fixture(scope="session")
def elasticsearch_in_kind(kind_cluster):
    manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: elasticsearch
spec:
  replicas: 1
  selector:
    matchLabels:
      app: elasticsearch
  template:
    metadata:
      labels:
        app: elasticsearch
    spec:
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:8.17.2
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
  name: elasticsearch
spec:
  selector:
    app: elasticsearch
  ports:
    - name: http
      port: 9200
      targetPort: 9200
"""
    _run(["kubectl", "apply", "-f", "-"], input_text=manifest, timeout=120)
    _run(
        [
            "kubectl",
            "rollout",
            "status",
            "deployment/elasticsearch",
            "--timeout=240s",
        ],
        timeout=260,
    )
    return "http://elasticsearch:9200"


def _wait_for_http(url: str, timeout: int = 60) -> dict:
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return {
                    "status": response.status,
                    "body": response.read().decode("utf-8"),
                }
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


@pytest.fixture(scope="session")
def mcp_server_in_kind(kind_cluster, loaded_mcp_image, elasticsearch_in_kind):
    _run(
        [
            "helm",
            "upgrade",
            "--install",
            RELEASE_NAME,
            "helm/elasticsearch-mcp-server",
            "--namespace",
            NAMESPACE,
            "--set",
            "fullnameOverride=mcp-e2e",
            "--set",
            f"image.repository={IMAGE_REPOSITORY}",
            "--set",
            f"image.tag={IMAGE_TAG}",
            "--set",
            "image.pullPolicy=Never",
            "--set",
            "server.engineType=elasticsearch",
            "--set",
            "server.transport=streamable-http",
            "--set",
            f"elasticsearch.hosts={elasticsearch_in_kind}",
            "--set",
            "elasticsearch.verifyCerts=false",
            "--set",
            "readinessProbe.initialDelaySeconds=2",
            "--set",
            "livenessProbe.initialDelaySeconds=2",
        ],
        timeout=180,
    )
    _run(
        ["kubectl", "rollout", "status", "deployment/mcp-e2e", "--timeout=240s"],
        timeout=260,
    )
    yield
    _run(
        ["helm", "uninstall", RELEASE_NAME, "--namespace", NAMESPACE],
        timeout=120,
    )


def test_helm_deployment_serves_health_and_readiness(mcp_server_in_kind):
    port_forward = subprocess.Popen(
        ["kubectl", "port-forward", "service/mcp-e2e", "18000:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        health = _wait_for_http("http://127.0.0.1:18000/healthz")
        assert health["status"] == 200
        assert '"status":"ok"' in health["body"]

        ready = _wait_for_http("http://127.0.0.1:18000/readyz")
        assert ready["status"] == 200
        assert '"status":"ok"' in ready["body"]
        assert '"search_engine":"elasticsearch"' in ready["body"]
    finally:
        port_forward.terminate()
        port_forward.wait(timeout=10)
