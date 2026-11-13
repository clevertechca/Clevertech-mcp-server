"""Tests for building permit tools (building.py).

Covers building_permit_search (with type filter, pagination, empty results)
and building_permit_recent (success and empty).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from clevertech_mcp.tools.building import register_building_tools

from tests.conftest import register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tool(client, config, name: str, mock_rate_limiter=None):
    return register_and_get_tool(
        register_building_tools, client, config, name, mock_rate_limiter
    )


# ===================================================================
# building_permit_search
# ===================================================================

class TestBuildingPermitSearch:
    """Tests for the ``building_permit_search`` tool."""

    @pytest.mark.asyncio
    async def test_building_permit_search_success(self, mock_client, mock_config, sample_permit):
        """Search returns formatted permit listings."""
        api_response = {
            "results": [sample_permit],
            "total": 1,
        }
        mock_client.get = AsyncMock(return_value=api_response)
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        result = await tool(city="calgary", q="456 Oak Ave")

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/calgary/permits/search"
        assert call_args[1]["params"]["q"] == "456 Oak Ave"
        assert call_args[1]["params"]["limit"] == 20

        assert "Found 1 of 1 building permits" in result
        assert "Permit: BP-2024-001" in result
        assert "Type: Building" in result
        assert "Status: Issued" in result
        assert "Address: 456 Oak Ave" in result
        assert "Applicant: John Smith" in result
        assert "Value: $250,000" in result
        assert "Issued: 2024-01-15" in result

    @pytest.mark.asyncio
    async def test_building_permit_search_with_type_filter(self, mock_client, mock_config, sample_permit):
        """Permit type filter is passed as a query parameter."""
        mock_client.get = AsyncMock(return_value={"results": [sample_permit], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        await tool(city="vancouver", q="renovation", permit_type="Demolition")

        params = mock_client.get.call_args[1]["params"]
        assert params["q"] == "renovation"
        assert params["permit_type"] == "Demolition"

    @pytest.mark.asyncio
    async def test_building_permit_search_limit_capped(self, mock_client, mock_config, sample_permit):
        """Limit > 200 is capped to 200."""
        mock_client.get = AsyncMock(return_value={"results": [sample_permit], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        await tool(city="toronto", q="condo", limit=500)

        assert mock_client.get.call_args[1]["params"]["limit"] == 200

    @pytest.mark.asyncio
    async def test_building_permit_search_empty(self, mock_client, mock_config):
        """Empty results show zero count."""
        mock_client.get = AsyncMock(return_value={"results": [], "total": 0})
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        result = await tool(city="montreal", q="nonexistent")

        assert "Found 0 of 0 building permits" in result
        assert "---" not in result

    @pytest.mark.asyncio
    async def test_building_permit_search_with_message(self, mock_client, mock_config, sample_permit):
        """API _message appears in output."""
        mock_client.get = AsyncMock(return_value={
            "results": [sample_permit],
            "total": 1,
            "_message": "Search limited to current year.",
        })
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        result = await tool(city="edmonton", q="warehouse")

        assert "Search limited to current year." in result

    @pytest.mark.asyncio
    async def test_building_permit_search_missing_value(self, mock_client, mock_config):
        """Permit without job_value shows 'Value: N/A'."""
        permit_no_value = {
            "permit_number": "BP-2024-099",
            "permit_type": "Plumbing",
            "status": "Pending",
            "address": "789 Pipe Rd",
            "applicant": "Jane Doe",
            # no job_value
            "issued_date": "2024-02-01",
        }
        mock_client.get = AsyncMock(return_value={"results": [permit_no_value], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "building_permit_search")

        result = await tool(city="calgary", q="789 Pipe")

        assert "Value: N/A" in result


# ===================================================================
# building_permit_recent
# ===================================================================

class TestBuildingPermitRecent:
    """Tests for the ``building_permit_recent`` tool."""

    @pytest.mark.asyncio
    async def test_building_permit_recent_success(self, mock_client, mock_config, sample_permit):
        """Recent permits return formatted list."""
        permits = [
            sample_permit,
            {
                "permit_number": "BP-2024-002",
                "permit_type": "Demolition",
                "status": "Issued",
                "address": "999 Tear Down Ln",
                "job_value": 50000,
                "issued_date": "2024-01-16",
            },
        ]
        mock_client.get = AsyncMock(return_value={"results": permits})
        tool = await _get_tool(mock_client, mock_config, "building_permit_recent")

        result = await tool(city="calgary", limit=10)

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "calgary" in call_args[0][0]
        assert call_args[1]["params"]["limit"] == 10

        assert "Recent building permits (2)" in result
        assert "BP-2024-001" in result
        assert "BP-2024-002" in result
        assert "Demolition" in result
        assert "Applicant" not in result
        assert "John Smith" not in result

    @pytest.mark.asyncio
    async def test_building_permit_recent_empty(self, mock_client, mock_config):
        """Empty recent permits results."""
        mock_client.get = AsyncMock(return_value={"results": []})
        tool = await _get_tool(mock_client, mock_config, "building_permit_recent")

        result = await tool(city="winnipeg")

        assert "Recent building permits (0)" in result
        assert "---" not in result

    @pytest.mark.asyncio
    async def test_building_permit_recent_limit_capped(self, mock_client, mock_config, sample_permit):
        """Limit > 100 is capped to 100."""
        mock_client.get = AsyncMock(return_value={"results": [sample_permit]})
        tool = await _get_tool(mock_client, mock_config, "building_permit_recent")

        await tool(city="ottawa", limit=500)

        assert mock_client.get.call_args[1]["params"]["limit"] == 100
        assert mock_client.get.call_args[0][0] == "/api/ottawa/permits/recent"


class TestBuildingPermitNearby:
    @pytest.mark.asyncio
    async def test_nearby_success(self, mock_client, mock_config, sample_permit):
        mock_client.get = AsyncMock(return_value={"results": [sample_permit], "total": 1})
        tool = await _get_tool(mock_client, mock_config, "building_permit_nearby")

        result = await tool(city="calgary", lat=51.045, lon=-114.072)

        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/api/calgary/permits/nearby"
        assert call_args[1]["params"]["lat"] == 51.045
        assert "Permit: BP-2024-001" in result

    @pytest.mark.asyncio
    async def test_nearby_rejects_out_of_bounds(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = await _get_tool(mock_client, mock_config, "building_permit_nearby", limiter)

        result = await tool(city="calgary", lat=0.0, lon=0.0)

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "Canadian bounds" in result


class TestBuildingPermitGet:
    @pytest.mark.asyncio
    async def test_get_success(self, mock_client, mock_config, sample_permit):
        mock_client.get = AsyncMock(return_value=sample_permit)
        tool = await _get_tool(mock_client, mock_config, "building_permit_get")

        result = await tool(city="calgary", permit_id="BP2006-19957")

        assert mock_client.get.call_args[0][0] == "/api/calgary/permits/BP2006-19957"
        assert "Permit: BP-2024-001" in result

    @pytest.mark.asyncio
    async def test_get_requires_id(self, mock_client, mock_config):
        limiter = MagicMock()
        mock_client.get = AsyncMock()
        tool = await _get_tool(mock_client, mock_config, "building_permit_get", limiter)

        result = await tool(city="calgary")

        limiter.check_or_raise.assert_not_called()
        mock_client.get.assert_not_called()
        assert "permit_id" in result


class TestBuildingPermitStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, mock_client, mock_config):
        mock_client.get = AsyncMock(
            return_value={"total_permits": 12000, "by_status": {"Issued": 8000}}
        )
        tool = await _get_tool(mock_client, mock_config, "building_permit_stats")

        result = await tool(city="calgary")

        mock_client.get.assert_called_once_with(
            "/api/calgary/permits/stats", api_key=None
        )
        assert "total_permits: 12000" in result
        assert "- Issued: 8000" in result


class TestBuildingPermitBatch:
    @pytest.mark.asyncio
    async def test_batch_success(self, mock_client, mock_config, sample_permit):
        mock_client.post = AsyncMock(return_value={"found": [sample_permit]})
        tool = await _get_tool(mock_client, mock_config, "building_permit_batch")

        result = await tool(city="calgary", permit_numbers=["BP-2024-001"])

        assert mock_client.post.call_args[0][0] == "/api/calgary/permits/batch"
        assert mock_client.post.call_args[1]["json"] == {
            "ids": ["BP-2024-001"]
        }
        assert "Permit: BP-2024-001" in result
