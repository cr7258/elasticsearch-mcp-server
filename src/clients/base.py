from abc import ABC
import logging
import warnings
from typing import Dict, Optional

from elasticsearch import Elasticsearch
import httpx
from opensearchpy import OpenSearch

class SearchClientBase(ABC):
    def __init__(self, config: Dict, engine_type: str):
        """
        Initialize the search client.
        
        Args:
            config: Configuration dictionary with connection parameters
            engine_type: Type of search engine to use ("elasticsearch" or "opensearch")
        """
        self.logger = logging.getLogger()
        self.config = config
        self.engine_type = engine_type
        
        # Extract common configuration
        hosts = config.get("hosts")
        username = config.get("username")
        password = config.get("password")
        api_key = config.get("api_key")
        verify_certs = config.get("verify_certs", False)
        
        # Disable insecure request warnings if verify_certs is False
        if not verify_certs:
            warnings.filterwarnings("ignore", message=".*verify_certs=False is insecure.*")
            warnings.filterwarnings("ignore", message=".*Unverified HTTPS request is being made to host.*")
            
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass
        
        # Initialize client based on engine type
        if engine_type == "elasticsearch":
            # Get auth parameters based on elasticsearch package version and authentication method
            auth_params = self._get_elasticsearch_auth_params(username, password, api_key)
            
            self.client = Elasticsearch(
                hosts=hosts,
                verify_certs=verify_certs,
                **auth_params
            )
            self.logger.info(f"Elasticsearch client initialized with hosts: {hosts}")
        elif engine_type == "opensearch":
            self.client = OpenSearch(
                hosts=hosts,
                http_auth=(username, password) if username and password else None,
                verify_certs=verify_certs
            )
            self.logger.info(f"OpenSearch client initialized with hosts: {hosts}")
        else:
            raise ValueError(f"Unsupported engine type: {engine_type}")

        # General REST client
        base_url = hosts[0] if isinstance(hosts, list) else hosts
        self.general_client = GeneralRestClient(
            base_url=base_url,
            username=username,
            password=password,
            api_key=api_key,
            verify_certs=verify_certs,
        )

    def _get_elasticsearch_auth_params(self, username: Optional[str], password: Optional[str], api_key: Optional[str]) -> Dict:
        """
        Get authentication parameters for Elasticsearch client based on package version.
        
        Args:
            username: Username for authentication
            password: Password for authentication
            api_key: API key for authentication
            
        Returns:
            Dictionary with appropriate auth parameters for the ES version
        """
        # API key takes precedence over username/password
        if api_key:
            return {"api_key": api_key}
            
        if not username or not password:
            return {}
            
        # Check Elasticsearch package version to determine auth parameter name
        try:
            from elasticsearch import __version__ as es_version
            major_version = es_version[0]    
            if major_version >= 8:
                # ES 8+ uses basic_auth
                return {"basic_auth": (username, password)}
            else:
                # ES 7 and below use http_auth
                return {"http_auth": (username, password)}
        except Exception as e:
            self.logger.error(f"Failed to detect Elasticsearch version: {e}")
            # If we can't detect version, try basic_auth first (ES 8+ default)
            return {"basic_auth": (username, password)}

class GeneralRestClient:
    def __init__(self, base_url: Optional[str], username: Optional[str], password: Optional[str], api_key: Optional[str], verify_certs: bool):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.auth = (username, password) if username and password else None
        self.api_key = api_key
        self.verify_certs = verify_certs

    def request(self, method, path, params=None, body=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {}
        
        # Add API key to Authorization header if provided
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        
        with httpx.Client(verify=self.verify_certs) as client:
            resp = client.request(
                method=method.upper(),
                url=url,
                params=params,
                json=body,
                auth=self.auth if not self.api_key else None,  # Use basic auth only if no API key
                headers=headers
            )
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if ct.startswith("application/json"):
                return resp.json()
            return resp.text
