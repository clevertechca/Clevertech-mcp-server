"""Serialized POST-body contract tests against the v1 handlers.

These go through ``CleverTechClient.post`` (httpx JSON encoding) rather than
asserting only the ``json=`` kwarg on a MagicMock.
"""

import pytest

from clevertech_mcp.tools.building import register_building_tools
from clevertech_mcp.tools.dls import register_dls_tools
from clevertech_mcp.tools.location import register_location_tools
from clevertech_mcp.tools.property import register_property_tools

from tests.conftest import register_and_get_tool
from tests.post_capture import capturing_client, v1_batch_ids

_LOCATION_FIELDS = frozenset({"address", "coordinates", "dls", "city"})


class TestPropertyBatchSerializedBody:
    @pytest.mark.asyncio
    async def test_wire_json_uses_ids_key(self, mock_config, sample_property):
        async with capturing_client(
            {"found": [sample_property], "not_found": ["999"]}
        ) as (client, captured):
            tool = register_and_get_tool(
                register_property_tools, client, mock_config, "property_batch"
            )
            result = await tool(city="calgary", roll_numbers="1234567, 999")

        assert captured["method"] == "POST"
        assert captured["path"] == "/api/calgary/property/batch"
        body = captured["body"]
        assert set(body) == {"ids"}
        assert "roll_numbers" not in body
        assert v1_batch_ids(body) == ["1234567", "999"]
        assert "Address: 123 Main St" in result


class TestPermitBatchSerializedBody:
    @pytest.mark.asyncio
    async def test_wire_json_uses_ids_key(self, mock_config, sample_permit):
        async with capturing_client({"found": [sample_permit]}) as (client, captured):
            tool = register_and_get_tool(
                register_building_tools, client, mock_config, "building_permit_batch"
            )
            result = await tool(city="calgary", permit_numbers=["BP-2024-001"])

        assert captured["method"] == "POST"
        assert captured["path"] == "/api/calgary/permits/batch"
        body = captured["body"]
        assert set(body) == {"ids"}
        assert "permit_numbers" not in body
        assert v1_batch_ids(body) == ["BP-2024-001"]
        assert "Permit: BP-2024-001" in result


class TestLocationResolveSerializedBody:
    @pytest.mark.asyncio
    async def test_wire_json_is_location_request(self, mock_config):
        async with capturing_client({"location": {"city": "calgary"}}) as (
            client,
            captured,
        ):
            tool = register_and_get_tool(
                register_location_tools, client, mock_config, "location_resolve"
            )
            await tool(address="308 4 Ave SW", city="calgary")

        body = captured["body"]
        assert captured["path"] == "/api/v2/locations/resolve"
        assert set(body) <= _LOCATION_FIELDS
        assert "q" not in body
        assert body == {"address": "308 4 Ave SW", "city": "calgary"}
        locator_fields = [k for k in ("address", "coordinates", "dls") if k in body]
        assert len(locator_fields) == 1


class TestDlsSerializedBodies:
    @pytest.mark.asyncio
    async def test_gps_to_dls_body(self, mock_config, sample_dls_result):
        async with capturing_client(sample_dls_result) as (client, captured):
            tool = register_and_get_tool(
                register_dls_tools, client, mock_config, "dls_convert"
            )
            await tool(direction="gps_to_dls", lat=51.0447, lon=-114.0719)

        assert captured["path"] == "/api/v1/convert/gps-to-dls"
        assert captured["body"] == {"lat": 51.0447, "lon": -114.0719}

    @pytest.mark.asyncio
    async def test_dls_to_gps_body(self, mock_config, sample_gps_result):
        async with capturing_client(sample_gps_result) as (client, captured):
            tool = register_and_get_tool(
                register_dls_tools, client, mock_config, "dls_convert"
            )
            await tool(direction="dls_to_gps", dls_string="NW-16-24-1-W5")

        assert captured["path"] == "/api/v1/convert/dls-to-gps"
        assert captured["body"] == {"dls_string": "NW-16-24-1-W5"}

    @pytest.mark.asyncio
    async def test_batch_body(self, mock_config):
        async with capturing_client({"results": [], "count": 0}) as (client, captured):
            tool = register_and_get_tool(
                register_dls_tools, client, mock_config, "dls_batch"
            )
            await tool(
                direction="gps_to_dls",
                items=[{"lat": 51.0, "lon": -114.0}],
                province="AB",
            )

        assert captured["path"] == "/api/v1/convert/batch"
        assert captured["body"] == {
            "direction": "gps_to_dls",
            "items": [{"lat": 51.0, "lon": -114.0}],
            "province": "AB",
        }
