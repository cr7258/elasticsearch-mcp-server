from typing import Dict, Optional
from src.clients.base import SearchClientBase

class DataStreamClient(SearchClientBase):  
    def create_data_stream(self, name: str) -> Dict:
        """Create a new data stream."""
        return self.client.indices.create_data_stream(name=name)
    
    def get_data_stream(self, name: Optional[str] = None) -> Dict:
        """Get information about one or more data streams."""
        if name:
            return self.client.indices.get_data_stream(name=name)
        else:
            return self.client.indices.get_data_stream()
    
    def delete_data_stream(self, name: str) -> Dict:
        """Delete one or more data streams."""
        return self.client.indices.delete_data_stream(name=name)
