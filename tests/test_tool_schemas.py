"""Ensure MCP tool input schemas expose parameter descriptions for TDQS."""

import pytest

from mcp.server.fastmcp import FastMCP

from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.tools.building import register_building_tools
from clevertech_mcp.tools.dls import register_dls_tools
from clevertech_mcp.tools.property import register_property_tools
from clevertech_mcp.tools.zoning import register_zoning_tools


def _build_mcp() -> FastMCP:
    mcp = FastMCP("schema-test")
    client = CleverTechClient("https://test.example.com", api_key="test-key")
    config = {"api_url": "https://test.example.com", "api_key": "test-key"}
    limiter = LocalRateLimiter()
    register_dls_tools(mcp, client, config, limiter)
    register_property_tools(mcp, client, config, limiter)
    register_zoning_tools(mcp, client, config, limiter)
    register_building_tools(mcp, client, config, limiter)
    return mcp


@pytest.mark.asyncio
async def test_weak_tools_have_rich_descriptions_and_param_docs():
    mcp = _build_mcp()
    tools = {t.name: t for t in await mcp.list_tools()}

    expectations = {
        "dls_convert": {
            "min_desc_len": 400,
            "params": ["direction", "lat", "lon", "dls_string", "province"],
        },
        "dls_batch": {
            "min_desc_len": 350,
            "params": ["direction", "items", "province"],
        },
        "property_report": {
            "min_desc_len": 300,
            "params": ["city", "roll_number"],
        },
        "property_by_roll": {
            "min_desc_len": 250,
            "params": ["city", "roll_number"],
        },
        "zoning_lookup": {
            "min_desc_len": 250,
            "params": ["city", "lat", "lon", "address"],
        },
        "building_permit_search": {
            "min_desc_len": 200,
            "params": ["city", "q", "permit_type", "limit"],
        },
        "building_permit_recent": {
            "min_desc_len": 150,
            "params": ["city", "limit"],
        },
    }

    for name, spec in expectations.items():
        tool = tools[name]
        assert tool.description and len(tool.description) >= spec["min_desc_len"], name
        props = tool.inputSchema.get("properties", {})
        for param in spec["params"]:
            assert param in props, f"{name} missing param {param}"
            desc = props[param].get("description")
            assert desc and len(desc) >= 20, f"{name}.{param} description too short: {desc!r}"
