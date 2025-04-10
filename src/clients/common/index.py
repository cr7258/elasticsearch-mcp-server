from typing import Dict, Optional

from src.clients.base import SearchClientBase



class IndexClient(SearchClientBase):
    def list_indices(self) -> Dict:
        """List all indices."""
        return self.client.cat.indices()
    
    def get_index(self, index: str) -> Dict:
        """Returns information (mappings, settings, aliases) about one or more indices."""
        return self.client.indices.get(index=index)
    
    def create_index(self, index: str, body: Optional[Dict] = None, settings: Dict | None = None, mappings: Dict | None = None) -> Dict:
        """Creates an index with optional settings and mappings."""
        if body is not None:
            return self.client.indices.create(index=index, body=body)
        return self.client.indices.create(index=index, settings=settings, mappings=mappings)
    
    def delete_index(self, index: str) -> Dict:
        """Delete an index."""
        return self.client.indices.delete(index=index)

    def get_mapping(self, index: str) -> Dict:
        return self.client.indices.get_mapping(index=index)[index]["mappings"]

    def get_settings(self, index: str) -> Dict:
        return self.client.indices.get_settings(index=index)[index]["settings"]

