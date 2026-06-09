"""Zoning MCP tools."""

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip


def register_zoning_tools(mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter):
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
        ctx: Context = None,
    ) -> str:
        """Get zoning information.

        Args:
            city: City slug
            lat: Latitude (alternative to address)
            lon: Longitude (alternative to address)
            address: Street address (alternative to lat/lon)
        """
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        if lat is not None and lon is not None:
            params = {"lat": lat, "lon": lon}
            data = await client.get(f"/api/{city}/zoning/by-gps", params=params, api_key=upstream_key)
        elif address:
            data = await client.get(f"/api/{city}/zoning/by-gps", params={"address": address}, api_key=upstream_key)
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
