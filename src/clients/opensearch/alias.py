from typing import Dict
from .base import BaseOpenSearchClient
from ..interfaces.alias import AliasClientInterface

class OpenSearchAliasClient(BaseOpenSearchClient, AliasClientInterface):
    def list_aliases(self) -> Dict:
        """Get all aliases."""
        return self.client.cat.aliases()
    
    def get_alias(self, index: str) -> Dict:
        """Get aliases for the specified index."""
        return self.client.indices.get_alias(index=index)

    def put_alias(self, index: str, name: str, body: Dict) -> Dict:
        """Creates or updates an alias."""
        return self.client.indices.put_alias(index=index, name=name, body=body)
    
    def delete_alias(self, index: str, name: str) -> Dict:
        """Delete an alias for the specified index."""
        return self.client.indices.delete_alias(index=index, name=name)
