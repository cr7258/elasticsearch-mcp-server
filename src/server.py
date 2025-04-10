import logging
import sys

from fastmcp import FastMCP

from src.clients import create_search_client
from src.exceptions import UnsupportedEngineException
from src.tools.alias import AliasTools
from src.tools.cluster import ClusterTools
from src.tools.document import DocumentTools
from src.tools.index import IndexTools
from src.tools.register import ToolsRegister

ENGINE_TYPE_DEFAULT = "elasticsearch"
SUPPORTED_ENGINES = ("elasticsearch", "opensearch")


class SearchMCPServer:
    def __init__(self, engine_type):
        # Set engine type
        self.engine_type = engine_type
        self.name = f"{self.engine_type}_mcp_server"
        self.mcp = FastMCP(self.name)
        self.logger = logging.getLogger()
        self.logger.info(f"Initializing {self.name}...")

        # Create the corresponding search client
        self.search_client = create_search_client(self.engine_type)

        # Initialize tools
        self._register_tools()

    def _register_tools(self):
        """Register all MCP tools."""
        # Create a tools register
        register = ToolsRegister(self.logger, self.search_client, self.mcp)

        # Define all tool classes to register
        tool_classes = [IndexTools, DocumentTools, ClusterTools, AliasTools]
        # Register all tools
        register.register_all_tools(tool_classes)

    def run(self):
        """Run the MCP server."""
        self.mcp.run()


def run_search_server(engine_type: str):
    """Run search server with specified engine type."""
    if engine_type not in SUPPORTED_ENGINES:
        raise UnsupportedEngineException(f"{engine_type=} provided only {', '.join(SUPPORTED_ENGINES)} supported.")
    server = SearchMCPServer(engine_type=engine_type)
    server.run()


def main():
    # If command line arguments are provided, use the first argument as the engine type
    if len(sys.argv) > 1:
        engine_type = sys.argv[1].lower()
    else:
        engine_type = ENGINE_TYPE_DEFAULT
    run_search_server(engine_type)


if __name__ == "__main__":
    main()
