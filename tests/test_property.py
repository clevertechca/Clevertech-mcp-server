"""Tests for property tools (property.py).

Covers property_search, property_report, and property_by_roll —
including pagination, empty results, and minimal/missing data handling.
"""

import json
import pytest
from unittest.mock import AsyncMock

from clevertech_mcp.tools.property import register_property_tools

from tests.conftest import register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tool(client, config, name: str):
    return register_and_get_tool(
        register_property_tools, client, config, name
    )


# ===================================================================
# property_search
# ===================================================================

class TestPropertySearch:
    """Tests for the ``property_search`` tool."""

    @pytest.mark.asyncio
    async def test_property_search_success(self, mock_client, mock_config, sample_property):
        """Search returns formatted property listings."""
        api_response = {
            "results": [sample_property],
            "total": 1,
        }
        mock_client.get = AsyncMock(return_value=api_response)
        tool = await _get_tool(mock_client, mock_config, "property_search")

        result = await tool(city="calgary", address="123 Main St")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "calgary" in call_args[0][0]
        assert call_args[1]["params"]["address"] == "123 Main St"
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["offset"] == 0

        assert "Found 1 of 1 properties" in result
        assert "Address: 123 Main St" in result
        assert "Roll: 1234567" in result
        assert "Assessed Value: $500,000" in result
        assert "Type: Residential" in result
        assert "DLS: NW-16-24-1-W5" in result

    @pytest.mark.asyncio
    async def test_property_search_empty(self, mock_client, mock_config):
        """Empty results show zero count."""
        mock_client.get = AsyncMock(return_value={"results": [], "total": 0})
        tool = await _get_tool(mock_client, mock_config, "property_search")

        result = await tool(city="calgary", address="Nonexistent St")

        assert "Found 0 of 0 properties" in result
        # No property detail lines
        assert "---" not in result

    @pytest.mark.asyncio
    async def test_property_search_with_pagination(self, mock_client, mock_config, sample_property):
        """Limit and offset are forwarded to the client."""
        mock_client.get = AsyncMock(return_value={"results": [sample_property], "total": 50})
        tool = await _get_tool(mock_client, mock_config, "property_search")

        await tool(city="toronto", address="King St", limit=50, offset=10)

        params = mock_client.get.call_args[1]["params"]
        assert params["limit"] == 50
        assert params["offset"] == 10

    @pytest.mark.asyncio
    async def test_property_search_limit_capped(self, mock_client, mock_config, sample_property):
        """Limit > 200 is capped to 200."""
        mock_client.get = AsyncMock(return_value={"results": [sample_property], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "property_search")

        await tool(city="vancouver", address="Main St", limit=999)

        assert mock_client.get.call_args[1]["params"]["limit"] == 200

    @pytest.mark.asyncio
    async def test_property_search_missing_value_shows_na(self, mock_client, mock_config):
        """Properties without assessed_value show N/A."""
        prop = {
            "roll_number": "9999999",
            "address": "456 Side St",
            "property_type": "Commercial",
            # no assessed_value
        }
        mock_client.get = AsyncMock(return_value={"results": [prop], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "property_search")

        result = await tool(city="edmonton", address="456 Side St")

        assert "Assessed Value: N/A" in result
        assert "Type: Commercial" in result

    @pytest.mark.asyncio
    async def test_property_search_with_message(self, mock_client, mock_config, sample_property):
        """API _message is included in output."""
        mock_client.get = AsyncMock(return_value={
            "results": [sample_property],
            "total": 1,
            "_message": "Showing approximate matches.",
        })
        tool = await _get_tool(mock_client, mock_config, "property_search")

        result = await tool(city="calgary", address="123 Main")

        assert "Showing approximate matches." in result


# ===================================================================
# property_report
# ===================================================================

class TestPropertyReport:
    """Tests for the ``property_report`` tool."""

    @pytest.mark.asyncio
    async def test_property_report_success(self, mock_client, mock_config, sample_property_report):
        """Full report includes assessment, permits, and zoning sections."""
        mock_client.get = AsyncMock(return_value=sample_property_report)
        tool = await _get_tool(mock_client, mock_config, "property_report")

        result = await tool(city="calgary", roll_number="1234567")

        mock_client.get.assert_called_once_with(
            "/api/calgary/property/report/1234567"
        )

        # Header
        assert "# Property Report" in result
        assert "**Address:** 123 Main St" in result
        assert "**Roll:** 1234567" in result
        # Assessment
        assert "## Assessment" in result
        assert "- Assessed Value: $500,000" in result
        assert "- Land: $200,000" in result
        assert "- Building: $300,000" in result
        assert "- Year Built: 1990" in result
        # Permits
        assert "## Building Permits (2)" in result
        assert "BP-2024-001" in result
        assert "BP-2023-045" in result
        # Zoning
        assert "## Zoning" in result
        assert "Zone: R-CG" in result
        # Message
        assert "Report generated from live data." in result

    @pytest.mark.asyncio
    async def test_property_report_minimal(self, mock_client, mock_config):
        """Report with missing property/permits/zoning handles gracefully."""
        minimal = {
            "address": "Minimal Ave",
            "roll_number": "0000001",
            "dls": "N/A",
            "generated_at": "2024-01-01T00:00:00Z",
            "property": {},          # empty
            # no permits key at all
            # no zoning key at all
        }
        mock_client.get = AsyncMock(return_value=minimal)
        tool = await _get_tool(mock_client, mock_config, "property_report")

        result = await tool(city="calgary", roll_number="0000001")

        assert "# Property Report" in result
        assert "**Address:** Minimal Ave" in result
        # Assessment section exists but values are N/A
        assert "- Assessed Value: N/A" in result
        assert "- Land: N/A" in result
        assert "- Year Built: N/A" in result
        # Permits and Zoning sections absent
        assert "Building Permits" not in result
        assert "## Zoning" not in result


# ===================================================================
# property_by_roll
# ===================================================================

class TestPropertyByRoll:
    """Tests for the ``property_by_roll`` tool."""

    @pytest.mark.asyncio
    async def test_property_by_roll_success(self, mock_client, mock_config, sample_property):
        """By-roll lookup returns JSON-dumped property data."""
        mock_client.get = AsyncMock(return_value=sample_property)
        tool = await _get_tool(mock_client, mock_config, "property_by_roll")

        result = await tool(city="calgary", roll_number="1234567")

        mock_client.get.assert_called_once_with(
            "/api/calgary/property/by-roll/1234567"
        )
        # Result is JSON string
        parsed = json.loads(result)
        assert parsed["roll_number"] == "1234567"
        assert parsed["address"] == "123 Main St"

    @pytest.mark.asyncio
    async def test_property_by_roll_missing(self, mock_client, mock_config):
        """Empty object returned — JSON dump still succeeds."""
        mock_client.get = AsyncMock(return_value={})
        tool = await _get_tool(mock_client, mock_config, "property_by_roll")

        result = await tool(city="calgary", roll_number="nonexistent")

        assert result == "{}"
