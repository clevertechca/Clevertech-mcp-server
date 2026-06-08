"""Geocoding MCP tools."""

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_geo_tools(mcp: FastMCP, client: CleverTechClient, config: dict):
    """Register geocoding tools."""

    @mcp.tool(
        name="reverse_geocode",
        description="Convert GPS coordinates to a human-readable address, city, neighborhood, province, and DLS grid reference. Works across all Canadian cities in the CleverTech database.",
    )
    async def reverse_geocode(lat: float, lon: float) -> str:
        """Reverse geocode GPS coordinates.

        Args:
            lat: Latitude
            lon: Longitude
        """
        data = await client.get(
            "/api/v1/geocode/reverse",
            params={"lat": lat, "lon": lon},
        )

        lines = [
            f"Address: {data.get('address', 'N/A')}",
            f"City: {data.get('city', 'N/A')}",
            f"Province: {data.get('province', 'N/A')}",
            f"Postal Code: {data.get('postal_code', data.get('postcode', 'N/A'))}",
            f"Neighborhood: {data.get('neighborhood', data.get('neighbourhood', 'N/A'))}",
        ]

        if data.get("dls"):
            lines.append(f"DLS: {data['dls']}")
        if data.get("lat") and data.get("lon"):
            lines.append(f"GPS: {data['lat']}, {data['lon']}")
        if data.get("confidence"):
            lines.append(f"Confidence: {data['confidence']}")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")

        return "\n".join(lines)
