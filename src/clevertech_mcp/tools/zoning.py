"""Zoning MCP tools."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip
from clevertech_mcp.schema_hints import CITY_SLUG

_ZONING_LOOKUP_DESCRIPTION = (
    "Return municipal zoning for a location in a supported Canadian city: zone code, "
    "description, district name, land use, and whether boundary geometry is present. "
    "Supply either (lat AND lon) in WGS84 decimal degrees OR a street address string; "
    "when both are provided, GPS takes precedence. "
    "Use property_report when you need assessment + permits + zoning together for a "
    "known roll number; use this tool for zoning-only questions at a point or address. "
    "Requires CLEVERTECH_API_KEY. Call list_cities to confirm zoning coverage for a slug."
)


def register_zoning_tools(mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter):
    """Register zoning lookup tools."""

    @mcp.tool(
        name="zoning_lookup",
        description=_ZONING_LOOKUP_DESCRIPTION,
    )
    async def zoning_lookup(
        city: Annotated[str, Field(description=CITY_SLUG)],
        lat: Annotated[
            Optional[float],
            Field(
                description=(
                    "Latitude (WGS84). Required together with lon when not using address."
                )
            ),
        ] = None,
        lon: Annotated[
            Optional[float],
            Field(
                description=(
                    "Longitude (WGS84). Required together with lat when not using address."
                )
            ),
        ] = None,
        address: Annotated[
            Optional[str],
            Field(
                description=(
                    "Street address to geocode within the city. Use when you do not have "
                    "GPS coordinates. Ignored when both lat and lon are supplied."
                )
            ),
        ] = None,
        ctx: Context = None,
    ) -> str:
        """Get zoning information."""
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
