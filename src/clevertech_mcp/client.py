"""
CleverTech API client — async httpx wrapper.
"""

from typing import Any, Optional
import httpx


class CleverTechClient:
    """Async HTTP client for the CleverTech API."""

    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialise and return the underlying httpx.AsyncClient."""
        if self._client is None:
            headers: dict[str, str] = {
                "Accept": "application/json",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Perform an async GET request and return the parsed JSON body."""
        client = self._get_client()
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Perform an async POST request and return the parsed JSON body."""
        client = self._get_client()
        response = await client.post(path, json=json)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client, if initialised."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
