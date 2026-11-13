"""Tests for telecom tools (telecom.py)."""

import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.telecom import register_telecom_tools

from tests.conftest import register_and_get_tool


def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_telecom_tools, client, config, name, mock_rate_limiter
    )


class TestTelecomTowersNearby:
    @pytest.mark.asyncio
    async def test_nearby_success(self, mock_client, mock_config, sample_tower):
        mock_client.get = AsyncMock(return_value=[sample_tower])
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby")

        result = await tool(lat=51.045, lon=-114.072)

        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/telecom/towers/nearby"
        assert call_args[1]["params"]["lat"] == 51.045
        assert call_args[1]["params"]["lon"] == -114.072
        assert call_args[1]["params"]["limit"] == 1
        assert call_args[1]["params"]["radius_km"] == 5.0
        assert "Tower: T-1001" in result
        assert "Carrier: Rogers" in result

    @pytest.mark.asyncio
    async def test_nearby_forwards_and_caps_radius_km(
        self, mock_client, mock_config, sample_tower
    ):
        mock_client.get = AsyncMock(return_value=[sample_tower])
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby")

        await tool(lat=51.045, lon=-114.072, radius_km=200)

        assert mock_client.get.call_args[1]["params"]["radius_km"] == 100.0

    @pytest.mark.asyncio
    async def test_nearby_forwards_fractional_radius(
        self, mock_client, mock_config, sample_tower
    ):
        mock_client.get = AsyncMock(return_value=[sample_tower])
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby")

        await tool(lat=51.045, lon=-114.072, radius_km=0.1)

        assert mock_client.get.call_args[1]["params"]["radius_km"] == 0.1

    @pytest.mark.asyncio
    async def test_nearby_accepts_st_johns(
        self, mock_client, mock_config, sample_tower
    ):
        """Official st-johns centre is inside the shared east GPS bound."""
        mock_client.get = AsyncMock(return_value=[sample_tower])
        limiter = MagicMock()
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby", limiter)

        result = await tool(lat=47.5615, lon=-52.7126)

        limiter.check_or_raise.assert_called()
        params = mock_client.get.call_args[1]["params"]
        assert params["lat"] == 47.5615
        assert params["lon"] == -52.7126
        assert "Tower: T-1001" in result

    @pytest.mark.asyncio
    async def test_nearby_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby", limiter)

        result = await tool(lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_nearby_clamps_zero_limit(
        self, mock_client, mock_config, sample_tower
    ):
        mock_client.get = AsyncMock(return_value=[sample_tower])
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby")

        await tool(lat=51.045, lon=-114.072, limit=0)

        assert mock_client.get.call_args[1]["params"]["limit"] == 1

    def test_nearby_schema_documents_radius_km(self, mock_client, mock_config):
        tool = _get_tool(mock_client, mock_config, "telecom_towers_nearby")
        params = inspect.signature(tool).parameters
        assert "radius_km" in params
        assert params["radius_km"].default == 5.0
        assert "radius_km" in tool.__doc__
        assert "0.1" in tool.__doc__


class TestTelecomTowersSearch:
    @pytest.mark.asyncio
    async def test_search_sends_carrier(
        self, mock_client, mock_config, sample_tower
    ):
        mock_client.get = AsyncMock(return_value={"results": [sample_tower], "total": 1})
        tool = _get_tool(mock_client, mock_config, "telecom_towers_search")

        result = await tool(q="Rogers")

        assert mock_client.get.call_args[0][0] == "/api/telecom/towers/search"
        assert mock_client.get.call_args[1]["params"]["carrier"] == "Rogers"
        assert mock_client.get.call_args[1]["params"]["limit"] == 20
        assert "Tower: T-1001" in result

    @pytest.mark.asyncio
    async def test_search_empty_q_falls_through_to_query(
        self, mock_client, mock_config, sample_tower
    ):
        mock_client.get = AsyncMock(return_value=[sample_tower])
        tool = _get_tool(mock_client, mock_config, "telecom_towers_search")

        await tool(q="", query="Bell")
        assert mock_client.get.call_args[1]["params"]["carrier"] == "Bell"

        mock_client.get.reset_mock()
        await tool(q="   ", query="Bell")
        assert mock_client.get.call_args[1]["params"]["carrier"] == "Bell"

    def test_search_schema_documents_query_alias(self, mock_client, mock_config):
        tool = _get_tool(mock_client, mock_config, "telecom_towers_search")
        params = inspect.signature(tool).parameters
        assert "q" in params
        assert "query" in params
        assert "Alias" in tool.__doc__


class TestTelecomStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={
                "total": 90000,
                "unique_carriers": 40,
                "unique_technologies": 6,
                "avg_height": 32.1,
                "min_height": 3.0,
                "max_height": 210.0,
            }
        )
        tool = _get_tool(mock_client, mock_config, "telecom_stats")

        result = await tool()

        mock_client.get.assert_called_once_with("/api/telecom/stats", api_key=None)
        assert "Total towers: 90000" in result
        assert "Unique carriers: 40" in result
        assert "Average height: 32.1 m" in result
