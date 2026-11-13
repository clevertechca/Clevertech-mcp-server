"""Tests for safety tools (safety.py).

Covers nearby, search, stats, by-id, and national summary — including
q/query aliases, URL-encoded ids, mocked 404s, and a mocked timeout on
the known-slow /api/v2/safety/summary route.
"""

import inspect

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.safety import register_safety_tools

from tests.conftest import register_and_get_tool


def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_safety_tools, client, config, name, mock_rate_limiter
    )


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request, json={"detail": "Not Found"})
    return httpx.HTTPStatusError("Not Found", request=request, response=response)


# ===================================================================
# safety_nearby
# ===================================================================

class TestSafetyNearby:
    """Tests for the ``safety_nearby`` tool."""

    @pytest.mark.asyncio
    async def test_safety_nearby_success(
        self, mock_client, mock_config, sample_safety_incident
    ):
        """Nearby lookup formats a list with a small default limit."""
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1, "count": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_nearby")

        result = await tool(city="toronto", lat=43.7141, lon=-79.3895)

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/toronto/safety/nearby"
        assert call_args[1]["params"]["lat"] == 43.7141
        assert call_args[1]["params"]["lon"] == -79.3895
        assert call_args[1]["params"]["limit"] == 20

        assert "Found 1 of 1 safety incidents" in result
        assert "Id: toronto_shootings:GO-2004195761" in result
        assert "Category: shooting" in result
        assert "Injury: none" in result

    @pytest.mark.asyncio
    async def test_safety_nearby_missing_lat_lon_skips_rate_limit(
        self, mock_client, mock_config
    ):
        """Missing lat/lon errors before rate limiting or HTTP."""
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "safety_nearby", limiter)

        result = await tool(city="toronto")

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Error" in result
        assert "lat" in result.lower()

    @pytest.mark.asyncio
    async def test_safety_nearby_limit_capped(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_nearby")

        await tool(city="toronto", lat=43.7, lon=-79.4, limit=999)

        assert mock_client.get.call_args[1]["params"]["limit"] == 200

    @pytest.mark.asyncio
    async def test_safety_nearby_clamps_zero_limit(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_nearby")

        await tool(city="toronto", lat=43.7, lon=-79.4, limit=0)

        assert mock_client.get.call_args[1]["params"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_safety_nearby_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "safety_nearby", limiter)

        result = await tool(city="toronto", lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_safety_nearby_404(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/toronto/safety/nearby")
        )
        tool = _get_tool(mock_client, mock_config, "safety_nearby")

        result = await tool(city="toronto", lat=43.7, lon=-79.4)

        assert "No safety incidents found" in result
        assert "toronto" in result

    @pytest.mark.asyncio
    async def test_safety_nearby_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = _get_tool(mock_client, mock_config, "safety_nearby")

        result = await tool(city="toronto", lat=43.7, lon=-79.4)

        assert "timed out" in result.lower()
        assert "Error" in result


# ===================================================================
# safety_search
# ===================================================================

class TestSafetySearch:
    """Tests for the ``safety_search`` tool."""

    @pytest.mark.asyncio
    async def test_safety_search_success(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_search")

        result = await tool(city="toronto", q="shooting")

        assert mock_client.get.call_args[0][0] == "/api/toronto/safety/search"
        assert mock_client.get.call_args[1]["params"]["q"] == "shooting"
        assert mock_client.get.call_args[1]["params"]["limit"] == 20
        assert "Id: toronto_shootings:GO-2004195761" in result

    @pytest.mark.asyncio
    async def test_safety_search_query_alias(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_search")

        await tool(city="toronto", query="Yonge")

        assert mock_client.get.call_args[1]["params"]["q"] == "Yonge"

    @pytest.mark.asyncio
    async def test_safety_search_q_wins_over_query(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_search")

        await tool(city="toronto", q="shooting", query="ignored")

        assert mock_client.get.call_args[1]["params"]["q"] == "shooting"

    @pytest.mark.asyncio
    async def test_safety_search_requires_q_or_query(self, mock_client, mock_config):
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "safety_search")

        result = await tool(city="toronto")

        mock_client.get.assert_not_called()
        assert "provide q or query" in result

    @pytest.mark.asyncio
    async def test_safety_search_empty_q_falls_through_to_query(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(
            return_value={"results": [sample_safety_incident], "total": 1}
        )
        tool = _get_tool(mock_client, mock_config, "safety_search")

        await tool(city="toronto", q="", query="Yonge")
        assert mock_client.get.call_args[1]["params"]["q"] == "Yonge"

        mock_client.get.reset_mock()
        await tool(city="toronto", q="   ", query="Yonge")
        assert mock_client.get.call_args[1]["params"]["q"] == "Yonge"

    def test_safety_search_schema_documents_query_alias(self, mock_client, mock_config):
        tool = _get_tool(mock_client, mock_config, "safety_search")
        params = inspect.signature(tool).parameters
        assert "q" in params
        assert "query" in params
        assert "Alias" in tool.__doc__


# ===================================================================
# safety_stats
# ===================================================================

class TestSafetyStats:
    """Tests for the ``safety_stats`` tool."""

    @pytest.mark.asyncio
    async def test_safety_stats_success(
        self, mock_client, mock_config, sample_safety_stats
    ):
        mock_client.get = AsyncMock(return_value=sample_safety_stats)
        tool = _get_tool(mock_client, mock_config, "safety_stats")

        result = await tool(city="toronto")

        mock_client.get.assert_called_once_with(
            "/api/toronto/safety/stats", api_key=None
        )
        assert "Total rows: 12840" in result
        assert "By injury:" in result
        assert "- none: 9000" in result
        assert "- fatal: 40" in result


# ===================================================================
# safety_by_id
# ===================================================================

class TestSafetyById:
    """Tests for the ``safety_by_id`` tool."""

    @pytest.mark.asyncio
    async def test_safety_by_id_url_encodes_colon(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(return_value=sample_safety_incident)
        tool = _get_tool(mock_client, mock_config, "safety_by_id")

        result = await tool(
            city="toronto", source_record_id="toronto_shootings:GO-2004195761"
        )

        path = mock_client.get.call_args[0][0]
        assert path == "/api/toronto/safety/toronto_shootings%3AGO-2004195761"
        assert ":" not in path.split("/safety/")[-1]
        assert "Id: toronto_shootings:GO-2004195761" in result
        assert "Category: shooting" in result

    @pytest.mark.asyncio
    async def test_safety_by_id_query_alias(
        self, mock_client, mock_config, sample_safety_incident
    ):
        mock_client.get = AsyncMock(return_value=sample_safety_incident)
        tool = _get_tool(mock_client, mock_config, "safety_by_id")

        await tool(city="toronto", query="toronto_shootings:GO-2004195761")

        assert "%3A" in mock_client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_safety_by_id_404(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/toronto/safety/missing")
        )
        tool = _get_tool(mock_client, mock_config, "safety_by_id")

        result = await tool(city="toronto", source_record_id="missing")

        assert "No safety record found" in result
        assert "missing" in result


# ===================================================================
# safety_summary
# ===================================================================

class TestSafetySummary:
    """Tests for the ``safety_summary`` tool."""

    @pytest.mark.asyncio
    async def test_safety_summary_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={"total_rows": 50000, "by_injury": {"fatal": 12}}
        )
        tool = _get_tool(mock_client, mock_config, "safety_summary")

        result = await tool()

        mock_client.get.assert_called_once_with(
            "/api/v2/safety/summary", params=None, api_key=None
        )
        assert "# Safety summary" in result
        assert "total_rows: 50000" in result
        assert "- fatal: 12" in result

    @pytest.mark.asyncio
    async def test_safety_summary_timeout_is_clean_error(self, mock_client, mock_config):
        """Known-slow national summary returns a tool error, not a traceback."""
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = _get_tool(mock_client, mock_config, "safety_summary")

        result = await tool()

        assert "timed out" in result.lower()
        assert "Error" in result
        assert "safety_nearby" in result or "safety_stats" in result
        assert "Traceback" not in result
        assert "ReadTimeout" not in result

    @pytest.mark.asyncio
    async def test_safety_summary_passes_category(self, mock_client, mock_config):
        mock_client.get = AsyncMock(return_value={"total_rows": 1})
        tool = _get_tool(mock_client, mock_config, "safety_summary")

        await tool(category="collision")

        assert mock_client.get.call_args[1]["params"] == {"category": "collision"}
