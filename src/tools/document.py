from typing import Dict, Optional

from fastmcp import FastMCP

class DocumentTools:
    def __init__(self, search_client):
        self.search_client = search_client
    
    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def search_documents(index: str, body: Dict) -> Dict:
            """
            Search for documents.
            
            Args:
                index: Name of the index
                body: Search query
            """
            return self.search_client.search_documents(index=index, body=body)
        
        @mcp.tool()
        def index_document(index: str, document: Dict, id: Optional[str] = None) -> Dict:
            """
            Creates or updates a document in the index.
            
            Args:
                index: Name of the index
                document: Document data
                id: Optional document ID
            """
            return self.search_client.index_document(index=index, id=id, document=document)
        
        @mcp.tool()
        def get_document(index: str, id: str) -> Dict:
            """
            Get a document by ID.
            
            Args:
                index: Name of the index
                id: Document ID
            """
            return self.search_client.get_document(index=index, id=id)
        
        @mcp.tool()
        def delete_document(index: str, id: str) -> Dict:
            """
            Delete a document by ID.
            
            Args:
                index: Name of the index
                id: Document ID
            """
            return self.search_client.delete_document(index=index, id=id)
        
        @mcp.tool()
        def delete_by_query(index: str, body: Dict) -> Dict:
            """
            Deletes documents matching the provided query.
            
            Args:
                index: Name of the index
                body: Query to match documents for deletion
            """
            return self.search_client.delete_by_query(index=index, body=body)
