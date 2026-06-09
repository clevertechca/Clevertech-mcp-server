"""
CleverTech API client — async httpx wrapper.

Supports per-request API key override for multi-user SSE deployments.
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

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Perform an async GET request.

        When *api_key* is provided, it overrides the default client key
        *for this request only* — thread-safe, no shared header mutation.
        """
        client = self._get_client()
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = await client.get(path, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Perform an async POST request.

        When *api_key* is provided, it overrides the default client key
        *for this request only* — thread-safe, no shared header mutation.
        """
        client = self._get_client()
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = await client.post(path, json=json, headers=headers)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client, if initialised."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
