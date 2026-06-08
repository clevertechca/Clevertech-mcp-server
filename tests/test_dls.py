"""Tests for DLS conversion tools (dls.py).

Covers GPS↔DLS single and batch conversions, parameter validation,
province passthrough, and result truncation.
"""

import pytest
from unittest.mock import AsyncMock

from clevertech_mcp.tools.dls import register_dls_tools

from tests.conftest import MockMCP, register_and_get_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_dls_convert(client, config):
    return register_and_get_tool(
        register_dls_tools, client, config, "dls_convert"
    )


async def _get_dls_batch(client, config):
    return register_and_get_tool(
        register_dls_tools, client, config, "dls_batch"
    )


# ===================================================================
# dls_convert tests
# ===================================================================

class TestDlsConvert:
    """Tests for the ``dls_convert`` tool."""

    @pytest.mark.asyncio
    async def test_dls_convert_gps_to_dls(self, mock_client, mock_config, sample_dls_result):
        """GPS→DLS: client.post returns DLS result — verify formatted output."""
        mock_client.post = AsyncMock(return_value=sample_dls_result)
        tool = await _get_dls_convert(mock_client, mock_config)

        result = await tool(direction="gps_to_dls", lat=51.0447, lon=-114.0719)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/v1/convert/gps-to-dls"
        assert call_args[1]["json"] == {"lat": 51.0447, "lon": -114.0719}

        assert "DLS: NW-16-24-1-W5" in result
        assert "Province: AB" in result
        assert "GPS: 51.0447, -114.0719" in result
        assert "Confidence: exact" in result
        assert "Distance to grid center: 0.35 km" in result

    @pytest.mark.asyncio
    async def test_dls_convert_dls_to_gps(self, mock_client, mock_config, sample_gps_result):
        """DLS→GPS: client.post returns GPS result — verify formatted output."""
        mock_client.post = AsyncMock(return_value=sample_gps_result)
        tool = await _get_dls_convert(mock_client, mock_config)

        result = await tool(direction="dls_to_gps", dls_string="NW-16-24-1-W5")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/v1/convert/dls-to-gps"
        assert call_args[1]["json"] == {"dls_string": "NW-16-24-1-W5"}

        assert "DLS: NW-16-24-1-W5" in result
        assert "GPS: 51.0447, -114.0719" in result
        assert "Province: AB" in result

    @pytest.mark.asyncio
    async def test_dls_convert_missing_params(self, mock_client, mock_config):
        """Missing lat/lon for gps_to_dls returns a clear error message."""
        tool = await _get_dls_convert(mock_client, mock_config)

        # gps_to_dls without lat/lon
        result = await tool(direction="gps_to_dls")
        assert "Error" in result
        assert "lat" in result.lower()
        assert "lon" in result.lower()
        mock_client.post.assert_not_called()

        # dls_to_gps without dls_string
        mock_client.post = AsyncMock()  # reset
        result = await tool(direction="dls_to_gps")
        assert "Error" in result
        assert "dls_string" in result.lower()
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_dls_convert_includes_province(self, mock_client, mock_config, sample_dls_result):
        """Province parameter is forwarded to the client payload."""
        mock_client.post = AsyncMock(return_value=sample_dls_result)
        tool = await _get_dls_convert(mock_client, mock_config)

        await tool(direction="gps_to_dls", lat=51.0, lon=-114.0, province="AB")

        call_json = mock_client.post.call_args[1]["json"]
        assert call_json["province"] == "AB"

    @pytest.mark.asyncio
    async def test_dls_convert_no_result(self, mock_client, mock_config):
        """Empty API response produces 'No result returned.' message."""
        mock_client.post = AsyncMock(return_value={})
        tool = await _get_dls_convert(mock_client, mock_config)

        result = await tool(direction="gps_to_dls", lat=51.0, lon=-114.0)
        assert result == "No result returned."


# ===================================================================
# dls_batch tests
# ===================================================================

class TestDlsBatch:
    """Tests for the ``dls_batch`` tool."""

    @pytest.mark.asyncio
    async def test_dls_batch_success(self, mock_client, mock_config):
        """Batch conversion returns formatted results list."""
        batch_response = {
            "count": 3,
            "results": [
                {"dls": "NW-16-24-1-W5", "lat": 51.04, "lon": -114.07},
                {"dls": "SE-10-25-2-W5", "lat": 51.05, "lon": -114.08},
                {"dls": "NE-22-23-3-W5", "lat": 51.03, "lon": -114.06},
            ],
        }
        mock_client.post = AsyncMock(return_value=batch_response)
        tool = await _get_dls_batch(mock_client, mock_config)

        items = [{"lat": 51.04, "lon": -114.07}] * 3
        result = await tool(direction="gps_to_dls", items=items)

        assert "Batch result: 3 conversions" in result
        assert "NW-16-24-1-W5" in result
        assert "SE-10-25-2-W5" in result
        assert "NE-22-23-3-W5" in result
        # Province not in payload by default
        assert "province" not in mock_client.post.call_args[1]["json"]

    @pytest.mark.asyncio
    async def test_dls_batch_empty(self, mock_client, mock_config):
        """Empty items list returns an error."""
        tool = await _get_dls_batch(mock_client, mock_config)

        result = await tool(direction="gps_to_dls", items=[])
        assert "Error" in result
        assert "empty" in result.lower()
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_dls_batch_over_limit(self, mock_client, mock_config):
        """Over 100 items returns an error."""
        tool = await _get_dls_batch(mock_client, mock_config)

        items = [{"lat": 51.0, "lon": -114.0}] * 101
        result = await tool(direction="gps_to_dls", items=items)
        assert "Error" in result
        assert "100" in result
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_dls_batch_truncates_results(self, mock_client, mock_config):
        """More than 20 results are truncated with a '... and N more' note."""
        results = [
            {"dls": f"NW-{i}-24-1-W5", "lat": 51.0, "lon": -114.0}
            for i in range(1, 26)  # 25 results
        ]
        batch_response = {"count": 25, "results": results}
        mock_client.post = AsyncMock(return_value=batch_response)
        tool = await _get_dls_batch(mock_client, mock_config)

        items = [{"lat": 51.0, "lon": -114.0}] * 25
        result = await tool(direction="gps_to_dls", items=items)

        # First 20 shown
        assert "NW-1-24-1-W5" in result
        assert "NW-20-24-1-W5" in result
        # 21st not shown
        assert "NW-21-24-1-W5" not in result
        # Truncation note
        assert "... and 5 more" in result

    @pytest.mark.asyncio
    async def test_dls_batch_with_province(self, mock_client, mock_config):
        """Province is forwarded in batch payload."""
        mock_client.post = AsyncMock(return_value={"count": 1, "results": [{"dls": "X"}]})
        tool = await _get_dls_batch(mock_client, mock_config)

        await tool(direction="gps_to_dls", items=[{"lat": 51.0, "lon": -114.0}], province="SK")

        call_json = mock_client.post.call_args[1]["json"]
        assert call_json["province"] == "SK"
