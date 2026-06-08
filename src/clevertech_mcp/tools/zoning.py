"""Zoning MCP tools."""

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_zoning_tools(mcp: FastMCP, client: CleverTechClient, config: dict):
    """Register zoning lookup tools."""

    @mcp.tool(
        name="zoning_lookup",
        description="Look up zoning district information for a GPS point or address in a Canadian city. Returns zone code, description, and district boundaries.",
    )
    async def zoning_lookup(
        city: str,
        lat: float = None,
        lon: float = None,
        address: str = None,
    ) -> str:
        """Get zoning information.

        Args:
            city: City slug
            lat: Latitude (alternative to address)
            lon: Longitude (alternative to address)
            address: Street address (alternative to lat/lon)
        """
        if lat is not None and lon is not None:
            params = {"lat": lat, "lon": lon}
            data = await client.get(f"/api/{city}/zoning/by-gps", params=params)
        elif address:
            data = await client.get(f"/api/{city}/zoning/by-gps", params={"address": address})
        else:
            return "Error: Provide either lat+lon or address."

        message = data.get("_message", "")
        zoning = data.get("zoning", data)
        if isinstance(zoning, list):
            zoning = zoning[0] if zoning else {}

        lines = [
            f"Zone: {zoning.get('zone_code', zoning.get('zone', 'N/A'))}",
            f"Description: {zoning.get('description', 'N/A')}",
        ]

        if zoning.get("district_name"):
            lines.append(f"District: {zoning['district_name']}")
        if zoning.get("land_use"):
            lines.append(f"Land Use: {zoning['land_use']}")

        bounds = zoning.get("boundaries", zoning.get("geometry"))
        if bounds:
            lines.append(f"Boundaries: Available ({type(bounds).__name__})")

        if message:
            lines.append(f"\n{message}")

        return "\n".join(lines)
