#!/bin/sh
set -e

# Select the MCP server entry point based on ENGINE_TYPE env var.
# Defaults to elasticsearch if not set.
ENGINE_TYPE="${ENGINE_TYPE:-elasticsearch}"

if [ "$ENGINE_TYPE" = "opensearch" ]; then
    exec opensearch-mcp-server "$@"
else
    exec elasticsearch-mcp-server "$@"
fi
