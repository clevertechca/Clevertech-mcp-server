"""Tests for business registry tools (business.py).

Covers business_registry_search with filters, empty results,
and flexible field names from the API.
"""

import pytest
from unittest.mock import AsyncMock

from clevertech_mcp.tools.business import register_business_tools

from tests.conftest import register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tool(client, config, name: str):
    return register_and_get_tool(
        register_business_tools, client, config, name
    )


# ===================================================================
# business_registry_search
# ===================================================================

class TestBusinessRegistrySearch:
    """Tests for the ``business_registry_search`` tool."""

    @pytest.mark.asyncio
    async def test_business_registry_search_success(self, mock_client, mock_config, sample_business):
        """Search returns formatted corporation listings."""
        api_response = {
            "results": [sample_business],
            "total": 1,
        }
        mock_client.get = AsyncMock(return_value=api_response)
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="ACME")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/registry/search"
        assert call_args[1]["params"]["q"] == "ACME"
        assert call_args[1]["params"]["limit"] == 25

        assert "Found 1 of 1 corporations" in result
        assert "Name: ACME CANADA INC." in result
        assert "Number: 123456-7" in result
        assert "Status: Active" in result
        assert "Province: AB" in result
        assert "Address: 100 Business Park" in result

    @pytest.mark.asyncio
    async def test_business_registry_search_with_filters(self, mock_client, mock_config, sample_business):
        """All optional filters are forwarded as query params."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        await tool(
            q="CONSTRUCTION",
            province="BC",
            city="Vancouver",
            status="Active",
            limit=50,
        )

        params = mock_client.get.call_args[1]["params"]
        assert params["q"] == "CONSTRUCTION"
        assert params["province"] == "BC"
        assert params["city"] == "Vancouver"
        assert params["status"] == "Active"
        assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_business_registry_search_empty(self, mock_client, mock_config):
        """Empty results show zero count."""
        mock_client.get = AsyncMock(return_value={"results": [], "total": 0})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="XYZZY_NONEXISTENT")

        assert "Found 0 of 0 corporations" in result
        assert "---" not in result

    @pytest.mark.asyncio
    async def test_business_registry_search_limit_capped(self, mock_client, mock_config, sample_business):
        """Limit > 100 is capped to 100."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        await tool(q="INC", limit=500)

        assert mock_client.get.call_args[1]["params"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_business_registry_search_alternate_field_names(self, mock_client, mock_config):
        """Handles API responses using 'name'/'number' instead of 'corporation_name'/'corporation_number'."""
        alt_response = {
            "results": [
                {
                    "name": "Beta Corp",
                    "number": "98765-4",
                    "status": "Dissolved",
                    "province": "ON",
                    "registered_address": "1 Yonge St, Toronto ON",
                }
            ],
            "total": 1,
        }
        mock_client.get = AsyncMock(return_value=alt_response)
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="Beta")

        assert "Name: Beta Corp" in result
        assert "Number: 98765-4" in result
        assert "Status: Dissolved" in result
        assert "Province: ON" in result

    @pytest.mark.asyncio
    async def test_business_registry_search_missing_address(self, mock_client, mock_config):
        """Corporation without registered_address omits the address line."""
        no_addr = {
            "corporation_name": "NoAddr Ltd.",
            "corporation_number": "00000-0",
            "status": "Active",
            "province": "MB",
            # no registered_address
        }
        mock_client.get = AsyncMock(return_value={"results": [no_addr], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="NoAddr")

        assert "Name: NoAddr Ltd." in result
        assert "Address:" not in result

    @pytest.mark.asyncio
    async def test_business_registry_search_with_message(self, mock_client, mock_config, sample_business):
        """API _message appears in output."""
        mock_client.get = AsyncMock(return_value={
            "results": [sample_business],
            "total": 1,
            "_message": "Results limited to federally incorporated entities.",
        })
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="ACME")

        assert "Results limited to federally incorporated entities." in result

    @pytest.mark.asyncio
    async def test_business_registry_search_no_total_field(self, mock_client, mock_config, sample_business):
        """When 'total' is absent, falls back to len(results)."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business]})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="ACME")

        assert "Found 1 of 1 corporations" in result
