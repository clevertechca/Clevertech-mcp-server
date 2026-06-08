"""
Aggregate all tool registrations onto a single FastMCP instance.
"""

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_all_tools(mcp: FastMCP, client: CleverTechClient, config: dict) -> None:
    """Wire up every tool category to the FastMCP server."""
    # Lazy imports so that individual tool modules can be worked on in
    # parallel without one missing module breaking the whole scaffold.
    try:
        from clevertech_mcp.tools.property import register_property_tools
        register_property_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.dls import register_dls_tools
        register_dls_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.building import register_building_tools
        register_building_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.zoning import register_zoning_tools
        register_zoning_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.business import register_business_tools
        register_business_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.geo import register_geo_tools
        register_geo_tools(mcp, client, config)
    except ImportError:
        pass

    try:
        from clevertech_mcp.tools.meta import register_meta_tools
        register_meta_tools(mcp, client, config)
    except ImportError:
        pass
