import logging
from typing import Dict, Any
from ..es_client import ElasticsearchClient
from mcp.types import TextContent

class IndexTools(ElasticsearchClient):
    def register_tools(self, mcp: Any):
        """Register index-related tools."""
        
        @mcp.tool(description="List all indices in the Elasticsearch cluster")
        async def list_indices() -> list[TextContent]:
            """List all indices in the Elasticsearch cluster."""
            self.logger.info("Listing indices...")
            try:
                indices = self.es_client.cat.indices(format="json")
                return [TextContent(type="text", text=str(indices))]
            except Exception as e:
                self.logger.error(f"Error listing indices: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @mcp.tool(description="Get index mapping")
        async def get_mapping(index: str) -> list[TextContent]:
            """
            Get the mapping for an index.
            
            Args:
                index: Name of the index
            """
            self.logger.info(f"Getting mapping for index: {index}")
            try:
                response = self.es_client.indices.get_mapping(index=index)
                return [TextContent(type="text", text=str(response))]
            except Exception as e:
                self.logger.error(f"Error getting mapping: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @mcp.tool(description="Get index settings")
        async def get_settings(index: str) -> list[TextContent]:
            """
            Get the settings for an index.
            
            Args:
                index: Name of the index
            """
            self.logger.info(f"Getting settings for index: {index}")
            try:
                response = self.es_client.indices.get_settings(index=index)
                return [TextContent(type="text", text=str(response))]
            except Exception as e:
                self.logger.error(f"Error getting settings: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @mcp.tool(description="Create new index with the same mapping as existing_index")
        async def create_index(index: str, existing_index: str) -> list[TextContent]:
            """
            Create index with mapping of existing_index
            """
            self.logger.info(f"Creating index: {index} with mapping of {existing_index} existing index")
            try:
                mapping = self.es_client.indices.get_mapping(index=existing_index)[existing_index]["mappings"]
                _settings = self.es_client.indices.get_settings(index=existing_index)[existing_index]["settings"]
                settings = {
                    "number_of_shards": _settings["index"]["number_of_shards"],
                    "number_of_replicas": _settings["index"]["number_of_replicas"],
                }
                response = self.es_client.indices.create(index=index, mappings=mapping, settings=settings)
                return [TextContent(type="text", text=str(response))]
            except Exception as e:
                self.logger.error(f"Error creating index: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
