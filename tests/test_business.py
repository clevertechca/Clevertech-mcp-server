"""Tests for business registry tools (business.py).

Covers business_registry_search with filters, empty results,
and flexible field names from the API.
"""

import inspect

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

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
        assert "Jurisdiction: AB" in result
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
        assert "Jurisdiction: ON" in result

    @pytest.mark.asyncio
    async def test_business_registry_search_missing_address(self, mock_client, mock_config):
        """Corporation without registered_address omits the address line."""
        no_addr = {
            "corporation_name": "NoAddr Ltd.",
            "corporation_number": "00000-0",
            "status": "Active",
            "jurisdiction": "MB",
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

    @pytest.mark.asyncio
    async def test_business_registry_search_query_alias(self, mock_client, mock_config, sample_business):
        """Agents can pass query instead of q; it is forwarded as q to the API."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(query="ACME")

        mock_client.get.assert_called_once()
        assert mock_client.get.call_args[1]["params"]["q"] == "ACME"
        assert "Name: ACME CANADA INC." in result

    @pytest.mark.asyncio
    async def test_business_registry_search_q_wins_over_query(self, mock_client, mock_config, sample_business):
        """When both q and query are given, q wins."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        await tool(q="ACME", query="ignored")

        assert mock_client.get.call_args[1]["params"]["q"] == "ACME"

    @pytest.mark.asyncio
    async def test_business_registry_search_empty_q_falls_through_to_query(
        self, mock_client, mock_config, sample_business
    ):
        """Empty or whitespace-only q is treated as missing so query is used."""
        mock_client.get = AsyncMock(return_value={"results": [sample_business], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool(q="", query="ACME")

        assert mock_client.get.call_args[1]["params"]["q"] == "ACME"
        assert "Name: ACME CANADA INC." in result

        mock_client.get.reset_mock()
        await tool(q="   ", query="ACME")
        assert mock_client.get.call_args[1]["params"]["q"] == "ACME"

    @pytest.mark.asyncio
    async def test_business_registry_search_requires_q_or_query(self, mock_client, mock_config):
        """Missing both q and query returns an error and does not call the API."""
        mock_client.get = AsyncMock()
        tool = await _get_tool(mock_client, mock_config, "business_registry_search")

        result = await tool()

        mock_client.get.assert_not_called()
        assert "provide q or query" in result

    def test_business_registry_search_schema_documents_query_alias(self, mock_client, mock_config):
        """Tool schema and description advertise query as an alias for q."""
        tool = register_and_get_tool(
            register_business_tools, mock_client, mock_config, "business_registry_search"
        )
        params = inspect.signature(tool).parameters
        assert "q" in params
        assert "query" in params
        assert params["q"].default is None
        assert params["query"].default is None
        assert "query" in tool.__doc__
        assert "Alias" in tool.__doc__


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request, json={"detail": "Not Found"})
    return httpx.HTTPStatusError("Not Found", request=request, response=response)


class TestBusinessRegistryGet:
    @pytest.mark.asyncio
    async def test_get_success(self, mock_client, mock_config, sample_business):
        mock_client.get = AsyncMock(
            return_value={**sample_business, "corporation_id": 42}
        )
        tool = await _get_tool(mock_client, mock_config, "business_registry_get")

        result = await tool(corporation_id="42")

        mock_client.get.assert_called_once()
        assert mock_client.get.call_args[0][0] == "/api/registry/corporation/42"
        assert "Name: ACME CANADA INC." in result
        assert "Id: 42" in result

    @pytest.mark.asyncio
    async def test_get_query_alias(self, mock_client, mock_config, sample_business):
        mock_client.get = AsyncMock(return_value=sample_business)
        tool = await _get_tool(mock_client, mock_config, "business_registry_get")

        await tool(query="99")

        assert mock_client.get.call_args[0][0] == "/api/registry/corporation/99"

    @pytest.mark.asyncio
    async def test_get_requires_id(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = register_and_get_tool(
            register_business_tools,
            mock_client,
            mock_config,
            "business_registry_get",
            limiter,
        )

        result = await tool()

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "corporation_id" in result

    @pytest.mark.asyncio
    async def test_get_404(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/registry/corporation/1")
        )
        tool = await _get_tool(mock_client, mock_config, "business_registry_get")

        result = await tool(corporation_id="1")

        assert "No corporation found" in result
        assert "1" in result

    @pytest.mark.asyncio
    async def test_get_rejects_non_integer_id(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = register_and_get_tool(
            register_business_tools,
            mock_client,
            mock_config,
            "business_registry_get",
            limiter,
        )

        result = await tool(corporation_id="abc-12")

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "must be an integer" in result


class TestBusinessRegistryAdvanced:
    @pytest.mark.asyncio
    async def test_advanced_forwards_facets(
        self, mock_client, mock_config, sample_business
    ):
        mock_client.get = AsyncMock(
            return_value={
                "results": [sample_business],
                "total": 1,
                "facets": {"status": {"Active": 1}},
            }
        )
        tool = await _get_tool(mock_client, mock_config, "business_registry_advanced")

        result = await tool(
            q="ACME",
            province="AB",
            act="CBCA",
            corporation_type="federal",
            limit=80,
        )

        params = mock_client.get.call_args[1]["params"]
        assert mock_client.get.call_args[0][0] == "/api/registry/advanced"
        assert params["q"] == "ACME"
        assert params["province"] == "AB"
        assert params["act"] == "CBCA"
        assert params["corporation_type"] == "federal"
        assert params["limit"] == 80
        assert "Name: ACME CANADA INC." in result
        assert "- status:" in result

    @pytest.mark.asyncio
    async def test_advanced_empty_q_falls_through(
        self, mock_client, mock_config, sample_business
    ):
        mock_client.get = AsyncMock(return_value={"results": [sample_business]})
        tool = await _get_tool(mock_client, mock_config, "business_registry_advanced")

        await tool(q="  ", query="ACME")
        assert mock_client.get.call_args[1]["params"]["q"] == "ACME"

    @pytest.mark.asyncio
    async def test_advanced_limit_capped(
        self, mock_client, mock_config, sample_business
    ):
        mock_client.get = AsyncMock(return_value={"results": [sample_business]})
        tool = await _get_tool(mock_client, mock_config, "business_registry_advanced")

        await tool(q="INC", limit=999)
        assert mock_client.get.call_args[1]["params"]["limit"] == 500

    @pytest.mark.asyncio
    async def test_advanced_facet_only_does_not_require_q(
        self, mock_client, mock_config, sample_business
    ):
        mock_client.get = AsyncMock(return_value={"results": [sample_business]})
        tool = await _get_tool(mock_client, mock_config, "business_registry_advanced")

        await tool(province="AB", status="Active")

        params = mock_client.get.call_args[1]["params"]
        assert "q" not in params
        assert params["province"] == "AB"
        assert params["status"] == "Active"


class TestBusinessRegistryStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={
                "total_corporations": 1200000,
                "by_province": {"ON": 400000, "AB": 90000},
            }
        )
        tool = await _get_tool(mock_client, mock_config, "business_registry_stats")

        result = await tool()

        mock_client.get.assert_called_once_with("/api/registry/stats", api_key=None)
        assert "Total corporations: 1200000" in result
        assert "- ON: 400000" in result

    @pytest.mark.asyncio
    async def test_stats_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = await _get_tool(mock_client, mock_config, "business_registry_stats")

        result = await tool()

        assert "Error" in result
        assert "timed out" in result.lower()
        assert "ReadTimeout" not in result
