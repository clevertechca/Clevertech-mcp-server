"""Zoning MCP tools."""

from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import (
    _get_user_api_key,
    get_upstream_key,
    is_authenticated,
    _extract_client_ip,
)
from clevertech_mcp.http_errors import tool_http_error
from clevertech_mcp.params import canadian_gps_error, nonempty_term


def _format_zoning(zoning: dict) -> list[str]:
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
    return lines


def _as_zoning(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    zoning = data.get("zoning", data)
    if isinstance(zoning, list):
        return zoning[0] if zoning and isinstance(zoning[0], dict) else {}
    return zoning if isinstance(zoning, dict) else {}


def register_zoning_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
):
    """Register zoning lookup, codes, and by-code tools."""

    @mcp.tool(
        name="zoning_lookup",
        description=(
            "Look up zoning district information for a GPS point or address in "
            "a Canadian city. Returns zone code, description, and district "
            "boundaries."
        ),
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
        if lat is not None and lon is not None:
            gps_error = canadian_gps_error(lat, lon)
            if gps_error:
                return gps_error
        elif not address:
            return "Error: Provide either lat+lon or address."

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        if lat is not None and lon is not None:
            params = {"lat": lat, "lon": lon}
        else:
            params = {"address": address}

        try:
            data = await client.get(
                f"/api/{city}/zoning/by-gps", params=params, api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No zoning district found for the given location in {city}.",
            )

        message = data.get("_message", "") if isinstance(data, dict) else ""
        lines = _format_zoning(_as_zoning(data))
        if message:
            lines.append(f"\n{message}")
        return "\n".join(lines)

    @mcp.tool(
        name="zoning_codes",
        description="List zoning district codes available for a Canadian city.",
    )
    async def zoning_codes(city: str, ctx: Context = None) -> str:
        """List zoning codes for a city.

        Args:
            city: City slug.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/zoning/codes", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No zoning codes are available for {city}.",
            )

        if isinstance(data, list):
            codes = data
        elif isinstance(data, dict):
            codes = data.get("codes", data.get("results", data.get("items", [])))
        else:
            codes = []
        lines = [f"Zoning codes ({len(codes)})"]
        for item in codes:
            if isinstance(item, dict):
                code = item.get("code", item.get("zone_code", item.get("zone", "N/A")))
                desc = item.get("description", "")
                lines.append(f"- {code}" + (f": {desc}" if desc else ""))
            else:
                lines.append(f"- {item}")
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="zoning_by_code",
        description=(
            "Look up zoning districts by code. Calls GET "
            "`/api/{city}/zoning/by-code?code=` (case- and accent-insensitive; "
            "slashes work, e.g. CR20-C20/R20). Pass `code` (preferred), `q`, "
            "or `query`."
        ),
    )
    async def zoning_by_code(
        city: str,
        code: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get districts matching a zoning code.

        Args:
            city: City slug.
            code: Zoning code (preferred). Slashes are sent as the `code` query param.
            q: Alias for code.
            query: Alias for code / q.
        """
        zone_code = nonempty_term(code) or nonempty_term(q) or nonempty_term(query)
        if zone_code is None:
            return (
                "Error: provide code (preferred), q, or query. "
                "If more than one is given, code wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/zoning/by-code",
                params={"code": zone_code},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No zoning district found for code {zone_code} in {city}.",
            )

        rows: list = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("results", "districts", "zoning", "items"):
                maybe = data.get(key)
                if isinstance(maybe, list):
                    rows = maybe
                    break
            if not rows:
                zoning = _as_zoning(data)
                if zoning:
                    rows = [zoning]
        lines = [f"Found {len(rows)} zoning district(s) for {zone_code}"]
        for row in rows:
            if isinstance(row, dict):
                lines.append("")
                lines.extend(_format_zoning(row))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
