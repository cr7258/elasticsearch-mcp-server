
# Elasticsearch/OpenSearch MCP Server

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/cr7258-elasticsearch-mcp-server-badge.png)](https://mseep.ai/app/cr7258-elasticsearch-mcp-server)

[![Trust Score](https://archestra.ai/mcp-catalog/api/badge/quality/cr7258/elasticsearch-mcp-server)](https://archestra.ai/mcp-catalog/cr7258__elasticsearch-mcp-server)

## Overview

A Model Context Protocol (MCP) server implementation that provides Elasticsearch and OpenSearch interaction. This server enables searching documents, analyzing indices, and managing cluster through a set of tools.

<a href="https://glama.ai/mcp/servers/b3po3delex"><img width="380" height="200" src="https://glama.ai/mcp/servers/b3po3delex/badge" alt="Elasticsearch MCP Server" /></a>

## Demo

https://github.com/user-attachments/assets/f7409e31-fac4-4321-9c94-b0ff2ea7ff15

## Features

### General Operations

- `general_api_request`: Perform a general HTTP API request. Use this tool for any Elasticsearch/OpenSearch API that does not have a dedicated tool.

### Index Operations

- `list_indices`: List all indices.
- `get_index`: Returns information (mappings, settings, aliases) about one or more indices.
- `create_index`: Create a new index.
- `delete_index`: Delete an index.

### Document Operations

- `search_documents`: Search for documents.
- `index_document`: Creates or updates a document in the index.
- `get_document`: Get a document by ID.
- `delete_document`: Delete a document by ID.
- `delete_by_query`: Deletes documents matching the provided query.

### Cluster Operations

- `get_cluster_health`: Returns basic information about the health of the cluster.
- `get_cluster_stats`: Returns high-level overview of cluster statistics.

### Alias Operations

- `list_aliases`: List all aliases.
- `get_alias`: Get alias information for a specific index.
- `put_alias`: Create or update an alias for a specific index.
- `delete_alias`: Delete an alias for a specific index.

## Configure Environment Variables

The MCP server supports the following environment variables for authentication:

### Basic Authentication (Username/Password)
- `ELASTICSEARCH_USERNAME`: Username for basic authentication
- `ELASTICSEARCH_PASSWORD`: Password for basic authentication
- `OPENSEARCH_USERNAME`: Username for OpenSearch basic authentication
- `OPENSEARCH_PASSWORD`: Password for OpenSearch basic authentication

### API Key Authentication (Elasticsearch only) - Recommended
- `ELASTICSEARCH_API_KEY`: API key for [Elasticsearch](https://www.elastic.co/docs/deploy-manage/api-keys/elasticsearch-api-keys) or [Elastic Cloud](https://www.elastic.co/docs/deploy-manage/api-keys/elastic-cloud-api-keys) Authentication.

### Other Configuration
- `ELASTICSEARCH_HOSTS` / `OPENSEARCH_HOSTS`: Comma-separated list of hosts (default: `https://localhost:9200`)
- `ELASTICSEARCH_VERIFY_CERTS` / `OPENSEARCH_VERIFY_CERTS`: Whether to verify SSL certificates (default: `false`)

## Start Elasticsearch/OpenSearch Cluster

Start the Elasticsearch/OpenSearch cluster using Docker Compose:

```bash
# For Elasticsearch
docker-compose -f docker-compose-elasticsearch.yml up -d

# For OpenSearch
docker-compose -f docker-compose-opensearch.yml up -d
```

The default Elasticsearch username is `elastic` and password is `test123`. The default OpenSearch username is `admin` and password is `admin`.

You can access Kibana/OpenSearch Dashboards from http://localhost:5601.

## Stdio

### Option 1: Using uvx

Using `uvx` will automatically install the package from PyPI, no need to clone the repository locally. Add the following configuration to 's config file `claude_desktop_config.json`.

```json
// For Elasticsearch with username/password
{
  "mcpServers": {
    "elasticsearch-mcp-server": {
      "command": "uvx",
      "args": [
        "elasticsearch-mcp-server"
      ],
      "env": {
        "ELASTICSEARCH_HOSTS": "https://localhost:9200",
        "ELASTICSEARCH_USERNAME": "elastic",
        "ELASTICSEARCH_PASSWORD": "test123"
      }
    }
  }
}

// For Elasticsearch with API key
{
  "mcpServers": {
    "elasticsearch-mcp-server": {
      "command": "uvx",
      "args": [
        "elasticsearch-mcp-server"
      ],
      "env": {
        "ELASTICSEARCH_HOSTS": "https://localhost:9200",
        "ELASTICSEARCH_API_KEY": "<YOUR_ELASTICSEARCH_API_KEY>"
      }
    }
  }
}

// For OpenSearch
{
  "mcpServers": {
    "opensearch-mcp-server": {
      "command": "uvx",
      "args": [
        "opensearch-mcp-server"
      ],
      "env": {
        "OPENSEARCH_HOSTS": "https://localhost:9200",
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": "admin"
      }
    }
  }
}
```

### Option 2: Using uv with local development

Using `uv` requires cloning the repository locally and specifying the path to the source code. Add the following configuration to Claude Desktop's config file `claude_desktop_config.json`.

```json
// For Elasticsearch with username/password
{
  "mcpServers": {
    "elasticsearch-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "path/to/src/elasticsearch_mcp_server",
        "run",
        "elasticsearch-mcp-server"
      ],
      "env": {
        "ELASTICSEARCH_HOSTS": "https://localhost:9200",
        "ELASTICSEARCH_USERNAME": "elastic",
        "ELASTICSEARCH_PASSWORD": "test123"
      }
    }
  }
}

// For Elasticsearch with API key
{
  "mcpServers": {
    "elasticsearch-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "path/to/src/elasticsearch_mcp_server",
        "run",
        "elasticsearch-mcp-server"
      ],
      "env": {
        "ELASTICSEARCH_HOSTS": "https://localhost:9200",
        "ELASTICSEARCH_API_KEY": "<YOUR_ELASTICSEARCH_API_KEY>"
      }
    }
  }
}

// For OpenSearch
{
  "mcpServers": {
    "opensearch-mcp-server": {
      "command": "uv",
      "args": [
        "--directory",
        "path/to/src/elasticsearch_mcp_server",
        "run",
        "opensearch-mcp-server"
      ],
      "env": {
        "OPENSEARCH_HOSTS": "https://localhost:9200",
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": "admin"
      }
    }
  }
}
```

## SSE

### Option 1: Using uvx

```bash
# export environment variables (with username/password)
export ELASTICSEARCH_HOSTS="https://localhost:9200"
export ELASTICSEARCH_USERNAME="elastic"
export ELASTICSEARCH_PASSWORD="test123"

# OR export environment variables (with API key)
export ELASTICSEARCH_HOSTS="https://localhost:9200"
export ELASTICSEARCH_API_KEY="<YOUR_ELASTICSEARCH_API_KEY>"

# By default, the SSE MCP server will serve on http://127.0.0.1:8000/sse
uvx elasticsearch-mcp-server --transport sse

# The host, port, and path can be specified using the --host, --port, and --path options
uvx elasticsearch-mcp-server --transport sse --host 0.0.0.0 --port 8000 --path /sse
```

### Option 2: Using uv

```bash
# By default, the SSE MCP server will serve on http://127.0.0.1:8000/sse
uv run src/server.py elasticsearch-mcp-server --transport sse

# The host, port, and path can be specified using the --host, --port, and --path options
uv run src/server.py elasticsearch-mcp-server --transport sse --host 0.0.0.0 --port 8000 --path /sse
```

## Streamable HTTP

### Option 1: Using uvx

```bash
# export environment variables (with username/password)
export ELASTICSEARCH_HOSTS="https://localhost:9200"
export ELASTICSEARCH_USERNAME="elastic"
export ELASTICSEARCH_PASSWORD="test123"

# OR export environment variables (with API key)
export ELASTICSEARCH_HOSTS="https://localhost:9200"
export ELASTICSEARCH_API_KEY="<YOUR_ELASTICSEARCH_API_KEY>"

# By default, the Streamable HTTP MCP server will serve on http://127.0.0.1:8000/mcp
uvx elasticsearch-mcp-server --transport streamable-http

# The host, port, and path can be specified using the --host, --port, and --path options
uvx elasticsearch-mcp-server --transport streamable-http --host 0.0.0.0 --port 8000 --path /mcp
```

### Option 2: Using uv

```bash
# By default, the Streamable HTTP MCP server will serve on http://127.0.0.1:8000/mcp
uv run src/server.py elasticsearch-mcp-server --transport streamable-http

# The host, port, and path can be specified using the --host, --port, and --path options
uv run src/server.py elasticsearch-mcp-server --transport streamable-http --host 0.0.0.0 --port 8000 --path /mcp
```

## Compatibility

The MCP server is compatible with Elasticsearch 7.x, 8.x, and 9.x. By default, it uses the Elasticsearch 8.x client (without a suffix). To use the Elasticsearch 7.x client, run the `elasticsearch-mcp-server-es7` variant. For Elasticsearch 9.x, use `elasticsearch-mcp-server-es9`. For example:

```bash
uvx elasticsearch-mcp-server-es7
```

| MCP Server | Elasticsearch |
| --- | --- |
| elasticsearch-mcp-server-es7 | Elasticsearch 7.x |
| elasticsearch-mcp-server | Elasticsearch 8.x |
| elasticsearch-mcp-server-es9 | Elasticsearch 9.x |
| opensearch-mcp-server | OpenSearch 1.x, 2.x, 3.x |

## License

This project is licensed under the Apache License Version 2.0 - see the [LICENSE](LICENSE) file for details.
