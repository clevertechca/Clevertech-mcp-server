"""Tests for zoning tools (zoning.py).

Covers zoning_lookup by GPS, by address, missing parameters,
and boundary data handling.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.zoning import register_zoning_tools

from tests.conftest import register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_zoning_tools, client, config, name, mock_rate_limiter
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
    async def test_zoning_lookup_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup", limiter)

        result = await tool(city="calgary", lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

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

    @pytest.mark.asyncio
    async def test_zoning_lookup_404(self, mock_client, mock_config):
        request = httpx.Request("GET", "https://clevertech.ca/api/calgary/zoning/by-gps")
        response = httpx.Response(404, request=request, json={"detail": "Not Found"})
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=request, response=response
            )
        )
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0447, lon=-114.0719)

        assert "No zoning district found" in result
        assert "calgary" in result
        assert "HTTPStatusError" not in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", address="123 Main St")

        assert "Error" in result
        assert "timed out" in result.lower()
        assert "ReadTimeout" not in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_http_500(self, mock_client, mock_config):
        request = httpx.Request("GET", "https://clevertech.ca/api/calgary/zoning/by-gps")
        response = httpx.Response(500, request=request, text="boom")
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=request, response=response
            )
        )
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0447, lon=-114.0719)

        assert "HTTP 500" in result
        assert "No zoning district found" not in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_http_403(self, mock_client, mock_config):
        request = httpx.Request("GET", "https://clevertech.ca/api/calgary/zoning/by-gps")
        response = httpx.Response(403, request=request, text="forbidden")
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Forbidden", request=request, response=response
            )
        )
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        result = await tool(city="calgary", lat=51.0447, lon=-114.0719)

        assert "HTTP 403" in result
        assert "No zoning district found" not in result

    @pytest.mark.asyncio
    async def test_zoning_lookup_propagates_value_error(
        self, mock_client, mock_config
    ):
        mock_client.get = AsyncMock(side_effect=ValueError("boom"))
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        with pytest.raises(ValueError, match="boom"):
            await tool(city="calgary", lat=51.0447, lon=-114.0719)

    @pytest.mark.asyncio
    async def test_zoning_lookup_propagates_runtime_error(
        self, mock_client, mock_config
    ):
        mock_client.get = AsyncMock(side_effect=RuntimeError("boom"))
        tool = await _get_tool(mock_client, mock_config, "zoning_lookup")

        with pytest.raises(RuntimeError, match="boom"):
            await tool(city="calgary", address="123 Main St")


class TestZoningCodes:
    @pytest.mark.asyncio
    async def test_codes_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={"codes": [{"code": "R-CG", "description": "Residential"}]}
        )
        tool = await _get_tool(mock_client, mock_config, "zoning_codes")

        result = await tool(city="calgary")

        mock_client.get.assert_called_once_with(
            "/api/calgary/zoning/codes", api_key=None
        )
        assert "Zoning codes (1)" in result
        assert "- R-CG: Residential" in result


class TestZoningByCode:
    @pytest.mark.asyncio
    async def test_by_code_query_param_keeps_slash(
        self, mock_client, mock_config, sample_zoning
    ):
        mock_client.get = AsyncMock(return_value={"zoning": sample_zoning})
        tool = await _get_tool(mock_client, mock_config, "zoning_by_code")

        result = await tool(city="calgary", code="CR20-C20/R20")

        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/calgary/zoning/by-code"
        assert call_args[1]["params"] == {"code": "CR20-C20/R20"}
        assert "by-code/CR20" not in call_args[0][0]
        assert "Zone: R-CG" in result

    @pytest.mark.asyncio
    async def test_by_code_requires_code(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = await _get_tool(mock_client, mock_config, "zoning_by_code", limiter)

        result = await tool(city="calgary")

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "provide code" in result
