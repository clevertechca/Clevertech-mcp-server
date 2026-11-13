"""Capture the serialized HTTP body from a real CleverTechClient POST."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from clevertech_mcp.client import CleverTechClient


def v1_batch_ids(body: dict) -> list:
    """Mirror Clevertech_v1 ``body.get("ids", [])`` on property/permit batch."""
    return body.get("ids", [])


@asynccontextmanager
async def capturing_client(
    response_json: dict[str, Any],
) -> AsyncIterator[tuple[CleverTechClient, dict[str, Any]]]:
    """Yield a live client whose POSTs are recorded as JSON bytes on the wire."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["raw"] = bytes(request.content)
        captured["body"] = json.loads(request.content.decode()) if request.content else {}
        return httpx.Response(200, json=response_json)

    client = CleverTechClient("https://clevertech.ca")
    client._client = httpx.AsyncClient(
        base_url="https://clevertech.ca",
        transport=httpx.MockTransport(handler),
        timeout=30.0,
        headers={"Accept": "application/json"},
    )
    try:
        yield client, captured
    finally:
        await client.close()
