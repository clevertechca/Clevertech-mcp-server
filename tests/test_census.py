"""Tests for census tools (census.py).

Covers census_lookup_by_gps, census_profile, census_stats, and
census_lookup_by_dls — including missing params, q/query aliases, and
a mocked 404 on the thin DLS map.
"""

import inspect

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.census import register_census_tools

from tests.conftest import register_and_get_tool


def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_census_tools, client, config, name, mock_rate_limiter
    )


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request, json={"detail": "Not Found"})
    return httpx.HTTPStatusError("Not Found", request=request, response=response)


# ===================================================================
# census_lookup_by_gps
# ===================================================================

class TestCensusLookupByGps:
    """Tests for the ``census_lookup_by_gps`` tool."""

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_success(
        self, mock_client, mock_config, sample_census_by_gps
    ):
        """GPS lookup formats year, population, median age, and income."""
        mock_client.get = AsyncMock(return_value=sample_census_by_gps)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps")

        result = await tool(city="calgary", lat=51.045, lon=-114.072)

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/calgary/census/by-gps"
        assert call_args[1]["params"] == {"lat": 51.045, "lon": -114.072}

        assert "DA: 48060645" in result
        assert "Year: 2021" in result
        assert "Population: 1,027" in result
        assert "Median age: 30.4" in result
        assert "Median income: $44,400" in result
        assert "GPS: 51.045, -114.072" in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_missing_lat_lon(self, mock_client, mock_config):
        """Missing lat/lon returns an error before rate limiting or HTTP."""
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps", limiter)

        result = await tool(city="calgary")

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Error" in result
        assert "lat" in result.lower()
        assert "lon" in result.lower()

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_rejects_out_of_bounds(
        self, mock_client, mock_config
    ):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps", limiter)

        result = await tool(city="calgary", lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_404(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/calgary/census/by-gps")
        )
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps")

        result = await tool(city="calgary", lat=51.045, lon=-114.072)

        assert "No census profile found" in result
        assert "51.045" in result
        assert "calgary" in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps")

        result = await tool(city="calgary", lat=51.045, lon=-114.072)

        assert "Error" in result
        assert "timed out" in result.lower()
        assert "ReadTimeout" not in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_hyphen_city_slug(
        self, mock_client, mock_config, sample_census_by_gps
    ):
        """Hyphenated city slugs are passed through in the path."""
        mock_client.get = AsyncMock(return_value=sample_census_by_gps)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps")

        await tool(city="quebec-city", lat=46.81, lon=-71.21)

        assert mock_client.get.call_args[0][0] == "/api/quebec-city/census/by-gps"

    @pytest.mark.asyncio
    async def test_census_lookup_by_gps_flat_profile(
        self, mock_client, mock_config, sample_census_profile
    ):
        """Response without a nested profile uses top-level fields."""
        mock_client.get = AsyncMock(return_value=sample_census_profile)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_gps")

        result = await tool(city="calgary", lat=51.0, lon=-114.0)

        assert "DA: 48060645" in result
        assert "Population: 1,027" in result


# ===================================================================
# census_profile
# ===================================================================

class TestCensusProfile:
    """Tests for the ``census_profile`` tool."""

    @pytest.mark.asyncio
    async def test_census_profile_success(
        self, mock_client, mock_config, sample_census_profile
    ):
        """Profile by DA id formats demographics."""
        mock_client.get = AsyncMock(return_value=sample_census_profile)
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary", da_id="48060645")

        mock_client.get.assert_called_once_with(
            "/api/calgary/census/profile",
            params={"da_id": "48060645"},
            api_key=None,
        )
        assert "DA: 48060645" in result
        assert "Year: 2021" in result
        assert "Population: 1,027" in result
        assert "Median age: 30.4" in result
        assert "Median income: $44,400" in result
        assert "Average income: $52,000" in result
        assert "Dwellings: 510" in result

    @pytest.mark.asyncio
    async def test_census_profile_csd_id(
        self, mock_client, mock_config, sample_census_profile
    ):
        """CSD-style ids are forwarded as da_id."""
        profile = {**sample_census_profile, "da_id": "CSD_4806016", "geography_type": "CSD"}
        mock_client.get = AsyncMock(return_value=profile)
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary", da_id="CSD_4806016")

        assert mock_client.get.call_args[1]["params"]["da_id"] == "CSD_4806016"
        assert "DA: CSD_4806016" in result
        assert "CSD" in result

    @pytest.mark.asyncio
    async def test_census_profile_query_alias(
        self, mock_client, mock_config, sample_census_profile
    ):
        """Agents can pass query instead of da_id."""
        mock_client.get = AsyncMock(return_value=sample_census_profile)
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary", query="48060645")

        assert mock_client.get.call_args[1]["params"]["da_id"] == "48060645"
        assert "DA: 48060645" in result

    @pytest.mark.asyncio
    async def test_census_profile_q_wins_over_query(
        self, mock_client, mock_config, sample_census_profile
    ):
        """When q and query are given (no da_id), q wins."""
        mock_client.get = AsyncMock(return_value=sample_census_profile)
        tool = _get_tool(mock_client, mock_config, "census_profile")

        await tool(city="calgary", q="48060645", query="ignored")

        assert mock_client.get.call_args[1]["params"]["da_id"] == "48060645"

    @pytest.mark.asyncio
    async def test_census_profile_da_id_wins(
        self, mock_client, mock_config, sample_census_profile
    ):
        """da_id wins over q and query."""
        mock_client.get = AsyncMock(return_value=sample_census_profile)
        tool = _get_tool(mock_client, mock_config, "census_profile")

        await tool(city="calgary", da_id="48060645", q="ignored", query="also-ignored")

        assert mock_client.get.call_args[1]["params"]["da_id"] == "48060645"

    @pytest.mark.asyncio
    async def test_census_profile_requires_id(self, mock_client, mock_config):
        """Missing da_id/q/query returns an error and does not call the API."""
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary")

        mock_client.get.assert_not_called()
        assert "da_id" in result
        assert "query" in result

    @pytest.mark.asyncio
    async def test_census_profile_404(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/calgary/census/profile")
        )
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary", da_id="48060645")

        assert "No census profile found" in result
        assert "48060645" in result

    @pytest.mark.asyncio
    async def test_census_profile_timeout(self, mock_client, mock_config):
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        tool = _get_tool(mock_client, mock_config, "census_profile")

        result = await tool(city="calgary", da_id="48060645")

        assert "Error" in result
        assert "timed out" in result.lower()
        assert "ReadTimeout" not in result

    def test_census_profile_schema_documents_query_alias(self, mock_client, mock_config):
        """Tool schema advertises q and query as aliases for da_id."""
        tool = _get_tool(mock_client, mock_config, "census_profile")
        params = inspect.signature(tool).parameters
        assert "da_id" in params
        assert "q" in params
        assert "query" in params
        assert params["da_id"].default is None
        assert params["q"].default is None
        assert params["query"].default is None
        assert "Alias" in tool.__doc__


# ===================================================================
# census_stats
# ===================================================================

class TestCensusStats:
    """Tests for the ``census_stats`` tool."""

    @pytest.mark.asyncio
    async def test_census_stats_success(
        self, mock_client, mock_config, sample_census_stats
    ):
        """Stats include total_profiles and census_years."""
        mock_client.get = AsyncMock(return_value=sample_census_stats)
        tool = _get_tool(mock_client, mock_config, "census_stats")

        result = await tool(city="calgary")

        mock_client.get.assert_called_once_with(
            "/api/calgary/census/stats", api_key=None
        )
        assert "Total profiles: 3,919" in result
        assert "Census years: 2016, 2021" in result
        assert "- DA: 3,800" in result
        assert "- CT: 119" in result


# ===================================================================
# census_lookup_by_dls
# ===================================================================

class TestCensusLookupByDls:
    """Tests for the ``census_lookup_by_dls`` tool."""

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_success(
        self, mock_client, mock_config, sample_census_by_dls
    ):
        """DLS lookup formats the nested profile."""
        mock_client.get = AsyncMock(return_value=sample_census_by_dls)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        result = await tool(city="calgary", dls="NW-16-24-1-W5")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/calgary/census/by-dls"
        assert call_args[1]["params"] == {"dls": "NW-16-24-1-W5"}

        assert "DLS: NW-16-24-1-W5" in result
        assert "DA: 48060645" in result
        assert "Population: 1,027" in result
        assert "Matched by: exact_dls" in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_404(self, mock_client, mock_config):
        """404 returns a clear not-found message about the small DLS map."""
        mock_client.get = AsyncMock(
            side_effect=_http_404("https://clevertech.ca/api/calgary/census/by-dls")
        )
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        result = await tool(city="calgary", dls="NW-16-24-1-W5")

        assert "No census profile found" in result
        assert "NW-16-24-1-W5" in result
        assert "1,000" in result or "small" in result.lower()
        assert "census_lookup_by_gps" in result

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_query_alias(
        self, mock_client, mock_config, sample_census_by_dls
    ):
        """Agents can pass query instead of dls; it is forwarded as dls."""
        mock_client.get = AsyncMock(return_value=sample_census_by_dls)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        await tool(city="calgary", query="NW-16-24-1-W5")

        assert mock_client.get.call_args[1]["params"]["dls"] == "NW-16-24-1-W5"

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_q_wins_over_query(
        self, mock_client, mock_config, sample_census_by_dls
    ):
        """When q and query are given (no dls), q wins."""
        mock_client.get = AsyncMock(return_value=sample_census_by_dls)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        await tool(city="calgary", q="NW-16-24-1-W5", query="ignored")

        assert mock_client.get.call_args[1]["params"]["dls"] == "NW-16-24-1-W5"

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_empty_dls_falls_through_to_query(
        self, mock_client, mock_config, sample_census_by_dls
    ):
        """Empty or whitespace-only dls is treated as missing so query is used."""
        mock_client.get = AsyncMock(return_value=sample_census_by_dls)
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        await tool(city="calgary", dls="", query="NW-16-24-1-W5")
        assert mock_client.get.call_args[1]["params"]["dls"] == "NW-16-24-1-W5"

        mock_client.get.reset_mock()
        await tool(city="calgary", dls="   ", query="NW-16-24-1-W5")
        assert mock_client.get.call_args[1]["params"]["dls"] == "NW-16-24-1-W5"

    @pytest.mark.asyncio
    async def test_census_lookup_by_dls_requires_dls(self, mock_client, mock_config):
        """Missing dls/q/query returns an error and does not call the API."""
        mock_client.get = AsyncMock()
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")

        result = await tool(city="calgary")

        mock_client.get.assert_not_called()
        assert "provide dls" in result
        assert "query" in result

    def test_census_lookup_by_dls_schema_documents_query_alias(
        self, mock_client, mock_config
    ):
        """Tool schema advertises q and query as aliases for dls."""
        tool = _get_tool(mock_client, mock_config, "census_lookup_by_dls")
        params = inspect.signature(tool).parameters
        assert "dls" in params
        assert "q" in params
        assert "query" in params
        assert "Alias" in tool.__doc__
