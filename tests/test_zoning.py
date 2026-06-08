"""Tests for zoning tools (zoning.py).

Covers zoning_lookup by GPS, by address, missing parameters,
and boundary data handling.
"""

import pytest
from unittest.mock import AsyncMock

from clevertech_mcp.tools.zoning import register_zoning_tools

from tests.conftest import register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tool(client, config, name: str):
    return register_and_get_tool(
        register_zoning_tools, client, config, name
    )


# ===================================================================
# zoning_lookup
# ===================================================================

class TestZoningLookup:
    """Tests for the ``zoning_lookup`` tool."""

    @pytest.mark.asyncio
    async def test_zoning_lookup_by_gps(self, mock_client, mock_config, sample_zoning):
        """GPS lookup returns zone code, description, and boundaries."""
        mock_client.get = AsyncMock(return_value={"zoning": sample_zoning})
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0447, lon=-114.0719)

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "calgary" in call_args[0][0]
        assert call_args[1]["params"] == {"lat": 51.0447, "lon": -114.0719}

        assert "Zone: R-CG" in result
        assert "Description: Residential" in result
        assert "District: Beltline" in result
        assert "Land Use: Residential Multi-Family" in result
        assert "Boundaries: Available" in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_by_address(self, mock_client, mock_config, sample_zoning):
        """Address lookup also uses the by-gps endpoint."""
        mock_client.get = AsyncMock(return_value={"zoning": sample_zoning})
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", address="123 Main St")

        call_args = mock_client.get.call_args
        assert call_args[1]["params"] == {"address": "123 Main St"}

        assert "Zone: R-CG" in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_missing_params(self, mock_client, mock_config):
        """No lat/lon or address provided returns an error."""
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary")  # no lat, lon, or address
        assert "Error" in result
        assert "lat" in result.lower()
        assert "lon" in result.lower()
        assert "address" in result.lower()
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_zoning_lookup_gps_takes_priority(self, mock_client, mock_config, sample_zoning):
        """When both GPS and address are provided, GPS is used (checked first)."""
        mock_client.get = AsyncMock(return_value={"zoning": sample_zoning})
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        await tool(city="calgary", lat=51.0, lon=-114.0, address="123 Main St")

        # GPS params, not address
        assert mock_client.get.call_args[1]["params"] == {"lat": 51.0, "lon": -114.0}

    @pytest.mark.asyncio
    async def test_zoning_lookup_list_response(self, mock_client, mock_config, sample_zoning):
        """Zoning in a list response uses the first element."""
        mock_client.get = AsyncMock(return_value={"zoning": [sample_zoning]})
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0, lon=-114.0)

        assert "Zone: R-CG" in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_flat_response(self, mock_client, mock_config, sample_zoning):
        """Response without a 'zoning' key falls back to the top-level data."""
        flat = {
            "zone_code": "R-1",
            "description": "Single Family Residential",
        }
        mock_client.get = AsyncMock(return_value=flat)
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0, lon=-114.0)

        assert "Zone: R-1" in result
        assert "Description: Single Family Residential" in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_alternate_zone_key(self, mock_client, mock_config):
        """Response using 'zone' key instead of 'zone_code'."""
        mock_client.get = AsyncMock(return_value={"zoning": {"zone": "DC", "description": "Direct Control"}})
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", address="456 Example Ave")

        assert "Zone: DC" in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_with_message(self, mock_client, mock_config, sample_zoning):
        """API _message is appended to output."""
        mock_client.get = AsyncMock(return_value={
            "zoning": sample_zoning,
            "_message": "Zoning data last updated 2024-01-01.",
        })
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0, lon=-114.0)

        assert "Zoning data last updated 2024-01-01." in result
