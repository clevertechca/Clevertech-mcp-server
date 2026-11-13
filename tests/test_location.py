"""Tests for location_resolve and location_context."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.location import register_location_tools

from tests.conftest import register_and_get_tool


def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_location_tools, client, config, name, mock_rate_limiter
    )


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request, json={"detail": "Not Found"})
    return httpx.HTTPStatusError("Not Found", request=request, response=response)


class TestLocationResolve:
    @pytest.mark.asyncio
    async def test_resolve_address(self, mock_client, mock_config):
        mock_client.post = AsyncMock(
            return_value={
                "location": {
                    "address": "308 4 Ave SW",
                    "city": "calgary",
                    "lat": 51.045,
                    "lon": -114.072,
                },
                "quality": {"status": "ok", "methods": ["address"]},
            }
        )
        tool = _get_tool(mock_client, mock_config, "location_resolve")

        result = await tool(address="308 4 Ave SW", city="calgary")

        mock_client.post.assert_called_once()
        assert mock_client.post.call_args[0][0] == "/api/v2/locations/resolve"
        body = mock_client.post.call_args[1]["json"]
        assert body == {"address": "308 4 Ave SW", "city": "calgary"}
        assert "q" not in body
        assert "308 4 Ave SW" in result
        assert "Quality: ok" in result

    @pytest.mark.asyncio
    async def test_resolve_coordinates(self, mock_client, mock_config):
        mock_client.post = AsyncMock(
            return_value={"location": {"lat": 51.045, "lon": -114.072}}
        )
        tool = _get_tool(mock_client, mock_config, "location_resolve")

        await tool(lat=51.045, lon=-114.072)

        body = mock_client.post.call_args[1]["json"]
        assert body == {"coordinates": {"lat": 51.045, "lon": -114.072}}
        assert "q" not in body

    @pytest.mark.asyncio
    async def test_resolve_never_sends_q(self, mock_client, mock_config):
        mock_client.post = AsyncMock(return_value={"location": {}})
        tool = _get_tool(mock_client, mock_config, "location_resolve")

        await tool(dls="NW-16-24-1-W5")

        body = mock_client.post.call_args[1]["json"]
        assert body == {"dls": "NW-16-24-1-W5"}
        assert set(body) <= {"address", "coordinates", "dls", "city"}

    @pytest.mark.asyncio
    async def test_resolve_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.post = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "location_resolve", limiter)

        result = await tool(lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.post.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_resolve_accepts_st_johns(self, mock_client, mock_config):
        mock_client.post = AsyncMock(
            return_value={"location": {"city": "st-johns"}}
        )
        limiter = MagicMock()
        tool = _get_tool(mock_client, mock_config, "location_resolve", limiter)

        result = await tool(lat=47.5615, lon=-52.7126, city="st-johns")

        limiter.check_or_raise.assert_called()
        body = mock_client.post.call_args[1]["json"]
        assert body["coordinates"] == {"lat": 47.5615, "lon": -52.7126}
        assert body["city"] == "st-johns"
        assert "st-johns" in result

    @pytest.mark.asyncio
    async def test_resolve_requires_input(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.post = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "location_resolve", limiter)

        result = await tool()

        limiter.check_or_raise.assert_not_called()
        mock_client.post.assert_not_called()
        assert "exactly one" in result
        assert "do not send q" in result

    @pytest.mark.asyncio
    async def test_resolve_rejects_combinations(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.post = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "location_resolve", limiter)

        result = await tool(address="308 4 Ave SW", lat=51.045, lon=-114.072)

        limiter.check_or_raise.assert_not_called()
        mock_client.post.assert_not_called()
        assert "exactly one" in result
        assert "not a combination" in result

    @pytest.mark.asyncio
    async def test_resolve_short_address_before_rate_limit(
        self, mock_client, mock_config
    ):
        limiter = MagicMock()
        mock_client.post = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "location_resolve", limiter)

        result = await tool(address="ab")

        limiter.check_or_raise.assert_not_called()
        mock_client.post.assert_not_called()
        assert "at least 3 characters" in result

    @pytest.mark.asyncio
    async def test_resolve_404(self, mock_client, mock_config):
        mock_client.post = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/v2/locations/resolve")
        )
        tool = _get_tool(mock_client, mock_config, "location_resolve")

        result = await tool(address="999 Nowhere St")

        assert "No location could be resolved" in result


class TestLocationContext:
    @pytest.mark.asyncio
    async def test_context_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={
                "datasets": [{"name": "zoning"}, {"name": "census"}],
                "radius_m": 1000,
            }
        )
        tool = _get_tool(mock_client, mock_config, "location_context")

        result = await tool(lat=51.045, lon=-114.072, city="calgary")

        params = mock_client.get.call_args[1]["params"]
        assert mock_client.get.call_args[0][0] == "/api/v2/locations/context"
        assert params["lat"] == 51.045
        assert params["lon"] == -114.072
        assert params["radius_m"] == 1000
        assert params["city"] == "calgary"
        assert "several upstream API calls" in result
        assert "datasets: 2 item(s)" in result

    @pytest.mark.asyncio
    async def test_context_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "location_context", limiter)

        result = await tool(lat=10.0, lon=10.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_context_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = _get_tool(mock_client, mock_config, "location_context")

        result = await tool(lat=51.045, lon=-114.072)

        assert "Error" in result
        assert "timed out" in result.lower()
        assert "ReadTimeout" not in result
