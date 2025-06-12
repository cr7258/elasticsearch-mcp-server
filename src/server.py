import logging
import sys
import argparse

from fastmcp import FastMCP

from src.clients import create_search_client
from src.tools.alias import AliasTools
from src.tools.cluster import ClusterTools
from src.tools.document import DocumentTools
from src.tools.general import GeneralTools
from src.tools.index import IndexTools
from src.tools.register import ToolsRegister
from src.version import __version__ as VERSION

class SearchMCPServer:
    def __init__(self, engine_type):
        # Set engine type
        self.engine_type = engine_type
        self.name = f"{self.engine_type}-mcp-server"
        self.mcp = FastMCP(self.name)
        self.logger = logging.getLogger()
        self.logger.info(f"Initializing {self.name}, Version: {VERSION}")
        
        # Create the corresponding search client
        self.search_client = create_search_client(self.engine_type)
        
        # Initialize tools
        self._register_tools()

    def _register_tools(self):
        """Register all MCP tools."""
        # Create a tools register
        register = ToolsRegister(self.logger, self.search_client, self.mcp)
        
        # Define all tool classes to register
        tool_classes = [
            IndexTools,
            DocumentTools,
            ClusterTools,
            AliasTools,
            GeneralTools,
        ]        
        # Register all tools
        register.register_all_tools(tool_classes)


def run_search_server(engine_type, transport, host, port, path):
    """Run search server with specified engine type and transport options.
    
    Args:
        engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        transport: Transport protocol to use ("stdio", "streamable-http", or "sse")
        host: Host to bind to when using HTTP transports
        port: Port to bind to when using HTTP transports
        path: URL path prefix for HTTP transports
    """
    
    server = SearchMCPServer(engine_type=engine_type)
    
    if transport in ["streamable-http", "sse"]:
        server.logger.info(f"Starting {server.name} with {transport} transport on {host}:{port}{path}")
        server.mcp.run(transport=transport, host=host, port=port, path=path)
    else:
        server.logger.info(f"Starting {server.name} with {transport} transport")
        server.mcp.run(transport=transport)

def parse_server_args():
    """Parse command line arguments for the MCP server.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport", "-t",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
        help="Transport protocol to use (default: stdio)"
    )
    parser.add_argument(
        "--host", "-H",
        default="127.0.0.1",
        help="Host to bind to when using HTTP transports (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind to when using HTTP transports (default: 8000)"
    )
    parser.add_argument(
        "--path", "-P",
        help="URL path prefix for HTTP transports (default: /mcp for streamable-http, /sse for sse)"
    )
    
    args = parser.parse_args()
    
    # Set default path based on transport type if not specified
    if args.path is None:
        if args.transport == "sse":
            args.path = "/sse"
        else:
            args.path = "/mcp"
            
    return args

def elasticsearch_mcp_server():
    """Entry point for Elasticsearch MCP server."""
    args = parse_server_args()
    
    # Run the server with the specified options
    run_search_server(
        engine_type="elasticsearch",
        transport=args.transport,
        host=args.host,
        port=args.port,
        path=args.path
    )

def opensearch_mcp_server():
    """Entry point for OpenSearch MCP server."""
    args = parse_server_args()
    
    # Run the server with the specified options
    run_search_server(
        engine_type="opensearch",
        transport=args.transport,
        host=args.host,
        port=args.port,
        path=args.path
    )

if __name__ == "__main__":
    # Require elasticsearch-mcp-server or opensearch-mcp-server as the first argument
    if len(sys.argv) <= 1 or sys.argv[1] not in ["elasticsearch-mcp-server", "opensearch-mcp-server"]:
        print("Error: First argument must be 'elasticsearch-mcp-server' or 'opensearch-mcp-server'")
        sys.exit(1)
        
    # Determine engine type based on the first argument
    engine_type = "elasticsearch"  # Default
    if sys.argv[1] == "opensearch-mcp-server":
        engine_type = "opensearch"
        
    # Remove the first argument so it doesn't interfere with argparse
    sys.argv.pop(1)
    
    # Parse command line arguments
    args = parse_server_args()
    
    # Run the server with the specified options
    run_search_server(
        engine_type=engine_type,
        transport=args.transport,
        host=args.host,
        port=args.port,
        path=args.path
    )
