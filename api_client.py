"""
PasarGuard Panel API Client

Handles authentication and data fetching from the panel API.
"""

import httpx
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PanelAPIClient:
    """Client for interacting with PasarGuard Panel API"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize the API client.
        
        Args:
            base_url: Panel API base URL (e.g., https://panel.example.com)
            username: Admin username for authentication
            password: Admin password for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        
    async def _ensure_token(self) -> bool:
        """Ensure we have a valid access token"""
        # Check if token is still valid (with 5 min buffer)
        if self.access_token and self.token_expires:
            if datetime.now() < self.token_expires - timedelta(minutes=5):
                return True
        
        # Get new token
        return await self._authenticate()
    
    async def _authenticate(self) -> bool:
        """Authenticate with the panel API and get access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/admin/token",
                    data={
                        "username": self.username,
                        "password": self.password,
                        "grant_type": "password"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    # Token typically expires in 1440 minutes (24 hours) based on API
                    self.token_expires = datetime.now() + timedelta(hours=24)
                    logger.info("Successfully authenticated with panel API")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make authenticated request to API"""
        if not await self._ensure_token():
            logger.error("Failed to authenticate")
            return None
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    **kwargs
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    # Token expired, try to re-authenticate
                    self.access_token = None
                    if await self._authenticate():
                        return await self._request(method, endpoint, **kwargs)
                    return None
                else:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"API request error: {str(e)}")
            return None
    
    async def get_admins(self, offset: int = 0, limit: int = 100) -> Optional[Dict]:
        """
        Fetch list of admins from the panel.
        
        Returns:
            Dict with 'admins' list and pagination info, or None on error
        """
        params = {"offset": offset, "limit": limit}
        return await self._request("GET", "/api/admins", params=params)
    
    async def get_all_admins(self) -> List[Dict]:
        """
        Fetch all admins (handles pagination automatically).
        
        Returns:
            List of all admin dictionaries
        """
        all_admins = []
        offset = 0
        limit = 100
        
        while True:
            result = await self.get_admins(offset=offset, limit=limit)
            if not result or "admins" not in result:
                break
            
            admins = result["admins"]
            all_admins.extend(admins)
            
            # Check if we've fetched all
            total = result.get("total", 0)
            if offset + limit >= total or len(admins) < limit:
                break
            
            offset += limit
        
        logger.info(f"Fetched {len(all_admins)} admins from panel")
        return all_admins
    
    async def get_users(self, offset: int = 0, limit: int = 100, 
                       admin: Optional[str] = None, 
                       status: Optional[str] = None) -> Optional[Dict]:
        """
        Fetch list of users from the panel.
        
        Args:
            offset: Pagination offset
            limit: Number of users to fetch
            admin: Filter by admin username
            status: Filter by user status (active, disabled, limited, expired, on_hold)
            
        Returns:
            Dict with 'users' list and pagination info, or None on error
        """
        params = {"offset": offset, "limit": limit}
        if admin:
            params["admin"] = admin
        if status:
            params["status"] = status
            
        return await self._request("GET", "/api/users", params=params)
    
    async def get_all_users(self, admin: Optional[str] = None) -> List[Dict]:
        """
        Fetch all users (handles pagination automatically).
        
        Args:
            admin: Optional filter by admin username
            
        Returns:
            List of all user dictionaries
        """
        all_users = []
        offset = 0
        limit = 100
        
        while True:
            result = await self.get_users(offset=offset, limit=limit, admin=admin)
            if not result or "users" not in result:
                break
            
            users = result["users"]
            all_users.extend(users)
            
            # Check if we've fetched all
            total = result.get("total", 0)
            if offset + limit >= total or len(users) < limit:
                break
            
            offset += limit
        
        logger.info(f"Fetched {len(all_users)} users from panel")
        return all_users
    
    async def get_current_admin(self) -> Optional[Dict]:
        """Get details of currently authenticated admin"""
        return await self._request("GET", "/api/admin")
    
    async def test_connection(self) -> bool:
        """Test if we can connect and authenticate with the API"""
        try:
            if await self._authenticate():
                admin = await self.get_current_admin()
                if admin:
                    logger.info(f"Connected to panel as: {admin.get('username', 'unknown')}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
