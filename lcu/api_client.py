"""HTTP API client for League Client."""
import requests
import logging
from typing import Optional, Dict, Any
from requests.auth import HTTPBasicAuth
import urllib3

# Disable SSL warnings since LCU uses self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class LCUApiClient:
    """HTTP client for League Client API."""
    
    def __init__(self, port: int, password: str):
        self.port = port
        self.password = password
        self.base_url = f"https://127.0.0.1:{port}"
        self.auth = HTTPBasicAuth('riot', password)
        self.session = requests.Session()
        self.session.verify = False  # Skip SSL verification for self-signed cert
    
    def get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make GET request to LCU API.
        
        Args:
            endpoint: API endpoint (e.g., '/lol-summoner/v1/current-summoner')
            
        Returns:
            JSON response or None on error
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, auth=self.auth, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"GET {endpoint} failed: {e}")
            return None
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Make POST request to LCU API.
        
        Args:
            endpoint: API endpoint
            data: Optional JSON data
            
        Returns:
            JSON response or None on error
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, auth=self.auth, json=data, timeout=5)
            response.raise_for_status()
            # Some endpoints return empty response
            if response.content:
                return response.json()
            return {}
        except Exception as e:
            logger.debug(f"POST {endpoint} failed: {e}")
            return None
    
    def accept_ready_check(self) -> bool:
        """
        Accept the matchmaking ready check.
        
        Returns:
            True if successful, False otherwise
        """
        result = self.post('/lol-matchmaking/v1/ready-check/accept')
        if result is not None:
            logger.info("Successfully accepted ready check")
            return True
        return False
    
    def get_ready_check_state(self) -> Optional[Dict[str, Any]]:
        """
        Get current ready check state.
        
        Returns:
            Ready check state or None
        """
        return self.get('/lol-matchmaking/v1/ready-check')
