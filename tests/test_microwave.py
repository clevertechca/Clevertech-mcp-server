"""Tests for microwave tools (microwave.py)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.microwave import register_microwave_tools

from tests.conftest import register_and_get_tool


def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_microwave_tools, client, config, name, mock_rate_limiter
    )


class TestMicrowaveNearby:
    @pytest.mark.asyncio
    async def test_nearby_default_radius(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_microwave_link], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "microwave_nearby")

        result = await tool(lat=51.045, lon=-114.072)

        params = mock_client.get.call_args[1]["params"]
        assert mock_client.get.call_args[0][0] == "/api/microwave/radius"
        assert params["radius_km"] == 2.0
        assert params["limit"] == 50
        assert "Authorization: 0002315559" in result
        assert "Licensee: TELUS" in result

    @pytest.mark.asyncio
    async def test_nearby_caps_radius(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(return_value=[sample_microwave_link])
        tool = _get_tool(mock_client, mock_config, "microwave_nearby")

        await tool(lat=51.045, lon=-114.072, radius_km=100)

        assert mock_client.get.call_args[1]["params"]["radius_km"] == 25.0

    @pytest.mark.asyncio
    async def test_nearby_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "microwave_nearby", limiter)

        result = await tool(lat=10.0, lon=10.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_nearby_clamps_negative_limit(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(return_value=[sample_microwave_link])
        tool = _get_tool(mock_client, mock_config, "microwave_nearby")

        await tool(lat=51.045, lon=-114.072, limit=-5)

        assert mock_client.get.call_args[1]["params"]["limit"] == 1


class TestMicrowaveSearch:
    @pytest.mark.asyncio
    async def test_search_sends_licensee(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_microwave_link], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "microwave_search")

        result = await tool(q="TELUS")

        assert mock_client.get.call_args[0][0] == "/api/microwave/search"
        assert mock_client.get.call_args[1]["params"]["licensee"] == "TELUS"
        assert "Authorization: 0002315559" in result

    @pytest.mark.asyncio
    async def test_search_empty_q_falls_through(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(return_value=[sample_microwave_link])
        tool = _get_tool(mock_client, mock_config, "microwave_search")

        await tool(q="", query="Bell")
        assert mock_client.get.call_args[1]["params"]["licensee"] == "Bell"


class TestMicrowaveStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(return_value={"total_links": 12000, "by_band": {"11 GHz": 400}})
        tool = _get_tool(mock_client, mock_config, "microwave_stats")

        result = await tool()

        mock_client.get.assert_called_once_with("/api/microwave/stats", api_key=None)
        assert "total_links: 12000" in result
        assert "- 11 GHz: 400" in result


class TestMicrowaveByAuthorization:
    @pytest.mark.asyncio
    async def test_by_authorization_success(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(return_value=sample_microwave_link)
        tool = _get_tool(mock_client, mock_config, "microwave_by_authorization")

        result = await tool(authorization_number="0002315559")

        assert mock_client.get.call_args[0][0] == "/api/microwave/authorization/0002315559"
        assert "Authorization: 0002315559" in result

    @pytest.mark.asyncio
    async def test_query_alias(self, mock_client, mock_config, sample_microwave_link):
        mock_client.get = AsyncMock(return_value=sample_microwave_link)
        tool = _get_tool(mock_client, mock_config, "microwave_by_authorization")

        await tool(query="0002315559")

        assert mock_client.get.call_args[0][0] == "/api/microwave/authorization/0002315559"

    @pytest.mark.asyncio
    async def test_by_authorization_formats_list(
        self, mock_client, mock_config, sample_microwave_link
    ):
        """A list of links is formatted, not dumped via str(data)."""
        second = {
            **sample_microwave_link,
            "authorization_number": "0002315560",
            "licensee": "Bell",
        }
        mock_client.get = AsyncMock(return_value=[sample_microwave_link, second])
        tool = _get_tool(mock_client, mock_config, "microwave_by_authorization")

        result = await tool(authorization_number="0002315559")

        assert "2 links" in result
        assert "Authorization: 0002315559" in result
        assert "Licensee: TELUS" in result
        assert "Authorization: 0002315560" in result
        assert "Licensee: Bell" in result
        assert "[{'" not in result
        assert "str(" not in result

    @pytest.mark.asyncio
    async def test_by_authorization_formats_links_key(
        self, mock_client, mock_config, sample_microwave_link
    ):
        mock_client.get = AsyncMock(return_value={"links": [sample_microwave_link]})
        tool = _get_tool(mock_client, mock_config, "microwave_by_authorization")

        result = await tool(q="0002315559")

        assert "1 link" in result
        assert "Authorization: 0002315559" in result
        assert "Licensee: TELUS" in result
