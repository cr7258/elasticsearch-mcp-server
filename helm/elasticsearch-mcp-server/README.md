# elasticsearch-mcp-server Helm Chart

Helm chart for deploying the [Elasticsearch/OpenSearch MCP Server](https://github.com/cr7258/elasticsearch-mcp-server) on Kubernetes.

## Prerequisites

- Kubernetes 1.23+
- Helm 3.10+
- A running Elasticsearch or OpenSearch cluster reachable from within the cluster

## Docker image

The Docker image is published to the GitHub Container Registry:

```
ghcr.io/cr7258/elasticsearch-mcp-server:<version>
```

The image runs as a non-root user with a read-only root filesystem and exposes the MCP server on port `8000` using `streamable-http` transport by default.

## Install the chart

The Helm chart is published as an OCI artifact to the GitHub Container Registry:

```
oci://ghcr.io/cr7258/charts/elasticsearch-mcp-server
```

**Elasticsearch — username/password:**

```bash
helm install elasticsearch-mcp oci://ghcr.io/cr7258/charts/elasticsearch-mcp-server \
  --set elasticsearch.hosts="https://your-elasticsearch:9200" \
  --set auth.credentials.elasticsearchUsername=elastic \
  --set auth.credentials.elasticsearchPassword=changeme \
  --set auth.credentials.mcpApiKey=your-secure-mcp-token
```

**Elasticsearch — API key (recommended):**

```bash
helm install elasticsearch-mcp oci://ghcr.io/cr7258/charts/elasticsearch-mcp-server \
  --set elasticsearch.hosts="https://your-elasticsearch:9200" \
  --set auth.credentials.elasticsearchApiKey=your-api-key \
  --set auth.credentials.mcpApiKey=your-secure-mcp-token
```

**OpenSearch:**

```bash
helm install opensearch-mcp oci://ghcr.io/cr7258/charts/elasticsearch-mcp-server \
  --set server.engineType=opensearch \
  --set opensearch.hosts="https://your-opensearch:9200" \
  --set auth.credentials.opensearchUsername=admin \
  --set auth.credentials.opensearchPassword=changeme \
  --set auth.credentials.mcpApiKey=your-secure-mcp-token
```

## Secret management

The chart supports two strategies for managing credentials.

**Option A — chart-managed Secret** (suitable for development):

Set values under `auth.credentials.*`. The chart creates a Kubernetes `Secret` and mounts the values as environment variables.

```yaml
auth:
  credentials:
    elasticsearchUsername: elastic
    elasticsearchPassword: changeme
    elasticsearchApiKey: ""       # takes precedence over password when set
    mcpApiKey: your-mcp-token
```

**Option B — existing Secret** (recommended for production, e.g. with External Secrets Operator):

```yaml
auth:
  existingSecret: my-secret-name
  existingSecretKeys:
    elasticsearchUsername: elasticsearch-username
    elasticsearchPassword: elasticsearch-password
    elasticsearchApiKey: elasticsearch-api-key
    opensearchUsername: opensearch-username
    opensearchPassword: opensearch-password
    mcpApiKey: mcp-api-key
```

When `auth.existingSecret` is set, no Secret is created by the chart.

## Key configuration values

| Parameter | Description | Default |
|---|---|---|
| `image.repository` | Docker image repository | `ghcr.io/cr7258/elasticsearch-mcp-server` |
| `image.tag` | Image tag (defaults to chart `appVersion`) | `""` |
| `server.engineType` | `elasticsearch` or `opensearch` | `elasticsearch` |
| `server.transport` | `streamable-http` or `sse` (`stdio` is not supported in Kubernetes) | `streamable-http` |
| `server.port` | Port the MCP server listens on | `8000` |
| `elasticsearch.hosts` | Elasticsearch host URL | `https://elasticsearch:9200` |
| `elasticsearch.verifyCerts` | Verify TLS certificates | `false` |
| `opensearch.hosts` | OpenSearch host URL | `https://opensearch:9200` |
| `opensearch.verifyCerts` | Verify TLS certificates | `false` |
| `auth.credentials.elasticsearchUsername` | ES basic auth username | `""` |
| `auth.credentials.elasticsearchPassword` | ES basic auth password | `""` |
| `auth.credentials.elasticsearchApiKey` | ES API key (takes precedence over password) | `""` |
| `auth.credentials.opensearchUsername` | OpenSearch basic auth username | `""` |
| `auth.credentials.opensearchPassword` | OpenSearch basic auth password | `""` |
| `auth.credentials.mcpApiKey` | Bearer token for MCP server authentication | `""` |
| `auth.existingSecret` | Use a pre-existing Secret instead of creating one | `""` |
| `risk.disableHighRiskOperations` | Disable all write/delete operations | `false` |
| `risk.disabledOperations` | Comma-separated list of specific operations to disable | `""` |
| `ingress.enabled` | Expose the MCP server via an Ingress | `false` |
| `autoscaling.enabled` | Enable Horizontal Pod Autoscaler | `false` |

For the full list of configurable values see [values.yaml](values.yaml).

## Health endpoints

The server exposes two HTTP endpoints used as Kubernetes probes:

| Endpoint | Probe | Success | Failure |
|---|---|---|---|
| `GET /healthz` | Liveness — is the process alive? | `200 {"status":"ok"}` | — |
| `GET /readyz` | Readiness — is the search cluster reachable? | `200 {"status":"ok","search_engine":"..."}` | `503` |

The chart configures these automatically via `livenessProbe` and `readinessProbe` in `values.yaml`.

## Verify the deployment

```bash
# Port-forward the service
kubectl port-forward svc/elasticsearch-mcp 8000:8000

# Liveness
curl http://localhost:8000/healthz
# {"status":"ok"}

# Readiness (returns 503 until the search cluster is reachable)
curl http://localhost:8000/readyz
# {"status":"ok","search_engine":"elasticsearch"}
```

## Running the unit tests

The chart ships with a [helm-unittest](https://github.com/helm-unittest/helm-unittest) test suite:

```bash
helm plugin install https://github.com/helm-unittest/helm-unittest
helm unittest helm/elasticsearch-mcp-server/
```
