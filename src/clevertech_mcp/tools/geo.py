"""Geocoding MCP tools."""

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import (
    _get_user_api_key,
    get_upstream_key,
    is_authenticated,
    _extract_client_ip,
)


def register_geo_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register geocoding tools."""

    @mcp.tool(
        name="reverse_geocode",
        description=(
            "Convert GPS coordinates to a human-readable address, city, "
            "neighborhood, province, DLS grid reference, and — when available — "
            "the nearest property's roll number and assessed value. Works across "
            "all Canadian cities in the CleverTech database."
        ),
    )
    async def reverse_geocode(lat: float, lon: float, ctx: Context = None) -> str:
        """Reverse geocode GPS coordinates with optional property lookup.

        If the geocoded address falls within a known property parcel,
        the roll number and assessed value are included automatically.

        Args:
            lat: Latitude
            lon: Longitude
        """
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            "/api/v1/geocode/reverse",
            params={"lat": lat, "lon": lon},
            api_key=upstream_key,
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

        # If we have a city and address, try to look up the property
        city_name = data.get("city", "").strip()
        geocoded_address = data.get("address", "").strip()
        city_slug = data.get("city_slug", city_name.lower().replace(" ", "-"))

        if city_slug and geocoded_address:
            try:
                prop_data = await client.get(
                    f"/api/{city_slug}/property/search",
                    params={"address": geocoded_address, "limit": 1},
                    api_key=upstream_key,
                )
                props = prop_data.get("results", [])
                if props:
                    prop = props[0]
                    lines.append("")
                    lines.append("**Nearest Property:**")
                    lines.append(f"- Roll: {prop.get('roll_number', 'N/A')}")
                    if prop.get("assessed_value") is not None:
                        lines.append(
                            f"- Assessed Value: ${prop['assessed_value']:,.0f}"
                        )
                    if prop.get("property_type"):
                        lines.append(f"- Type: {prop['property_type']}")
            except Exception:
                pass  # Property lookup is best-effort

        if data.get("_message"):
            lines.append(f"\n{data['_message']}")

        return "\n".join(lines)
