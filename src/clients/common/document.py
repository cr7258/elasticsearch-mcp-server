from typing import Dict, Optional

from src.clients.base import SearchClientBase

class DocumentClient(SearchClientBase):
    def search_documents(self, index: str, body: Dict) -> Dict:
        """Search for documents in the index."""
        return self.client.search(index=index, body=body)
    
    def index_document(self, index: str, document: Dict, id: Optional[str] = None) -> Dict:
        """Creates a new document in the index."""
        # Handle parameter name differences between Elasticsearch and OpenSearch
        if self.engine_type == "elasticsearch":
            # For Elasticsearch: index(index, document, id=None, ...)
            if id is not None:
                return self.client.index(index=index, document=document, id=id)
            else:
                return self.client.index(index=index, document=document)
        else:
            # For OpenSearch: index(index, body, id=None, ...)
            if id is not None:
                return self.client.index(index=index, body=document, id=id)
            else:
                return self.client.index(index=index, body=document)
    
    def get_document(self, index: str, id: str) -> Dict:
        """Get a document by ID."""
        return self.client.get(index=index, id=id)
    
    def delete_document(self, index: str, id: str) -> Dict:
        """Removes a document from the index."""
        return self.client.delete(index=index, id=id)

    def delete_by_query(self, index: str, body: Dict) -> Dict:
        """Deletes documents matching the provided query."""
        return self.client.delete_by_query(index=index, body=body)

