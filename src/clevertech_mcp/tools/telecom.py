"""ISED telecom-tower MCP tools.

Wraps the documented ``/api/telecom`` routes: towers nearby, towers search,
and network stats. Nearby defaults to ``limit=1`` because the live nearby
call can be heavy.
"""

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
from clevertech_mcp.params import (
    canadian_gps_error,
    clamp_limit,
    clamp_radius_km,
    nonempty_term,
)


def _tower_rows(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("results", data.get("towers", data.get("items")))
        if isinstance(rows, list):
            return rows
    return []


def _format_tower(row: dict) -> list[str]:
    tower_id = row.get("tower_id", row.get("id", "N/A"))
    lat = row.get("latitude", row.get("lat"))
    lon = row.get("longitude", row.get("lon"))
    lines = [
        "",
        "---",
        f"Tower: {tower_id}",
        f"Carrier: {row.get('carrier', row.get('client_name', 'N/A'))}",
        f"City: {row.get('city', 'N/A')}, {row.get('province', 'N/A')}",
        f"Technology: {row.get('technology', 'N/A')}",
    ]
    if row.get("height_meters") is not None:
        lines.append(f"Height: {row['height_meters']} m")
    if lat is not None and lon is not None:
        lines.append(f"GPS: {lat}, {lon}")
    if row.get("address"):
        lines.append(f"Address: {row['address']}")
    return lines


def register_telecom_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register telecom tower nearby, search, and stats tools."""

    @mcp.tool(
        name="telecom_towers_nearby",
        description=(
            "Find ISED-licensed telecom towers near a GPS point in Canada. "
            "Default limit is 1 because nearby queries can be heavy. Optional "
            "`radius_km` (default 5, clamped 0.1–100 to match upstream). "
            "Lat/lon must be within Canadian bounds (lat 41–84, lon −142 to "
            "−52)."
        ),
    )
    async def telecom_towers_nearby(
        lat: float = None,
        lon: float = None,
        limit: int = 1,
        radius_km: float = 5.0,
        ctx: Context = None,
    ) -> str:
        """Get towers near a GPS point.

        Args:
            lat: Latitude (Canadian bounds).
            lon: Longitude (Canadian bounds).
            limit: Max results (1-200, default 1).
            radius_km: Search radius in km (0.1-100, default 5).
        """
        gps_error = canadian_gps_error(lat, lon)
        if gps_error:
            return gps_error

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        radius = clamp_radius_km(radius_km)

        try:
            data = await client.get(
                "/api/telecom/towers/nearby",
                params={
                    "lat": lat,
                    "lon": lon,
                    "limit": clamp_limit(limit, maximum=200),
                    "radius_km": radius,
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No telecom towers found near GPS {lat}, {lon}.",
            )

        rows = _tower_rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} towers"]
        for row in rows:
            if isinstance(row, dict):
                lines.extend(_format_tower(row))
        return "\n".join(lines)

    @mcp.tool(
        name="telecom_towers_search",
        description=(
            "Search ISED-licensed telecom towers. Pass a carrier or keyword as "
            "`q` (preferred) or `query` (alias). If both are given, `q` wins. "
            "Empty or whitespace-only `q` is treated as missing so `query` is "
            "used. The search term is sent as the API `carrier` filter."
        ),
    )
    async def telecom_towers_search(
        q: str | None = None,
        query: str | None = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Search towers by carrier keyword.

        Args:
            q: Carrier or keyword (preferred). Wins if both q and query are non-empty.
            query: Alias for q. Used when q is omitted, empty, or whitespace-only.
            limit: Max results (1-200, default 20).
        """
        search = nonempty_term(q) or nonempty_term(query)
        if search is None:
            return (
                "Error: provide q or query (carrier or keyword). "
                "If both are given, q wins."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                "/api/telecom/towers/search",
                params={
                    "carrier": search,
                    "limit": clamp_limit(limit, maximum=200),
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No telecom towers found for {search!r}.",
            )

        rows = _tower_rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} towers"]
        for row in rows:
            if isinstance(row, dict):
                lines.extend(_format_tower(row))
        return "\n".join(lines)

    @mcp.tool(
        name="telecom_stats",
        description=(
            "Get national ISED telecom-tower statistics: total towers, unique "
            "carriers and technologies, and height range."
        ),
    )
    async def telecom_stats(ctx: Context = None) -> str:
        """Get telecom network stats."""
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get("/api/telecom/stats", api_key=upstream_key)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found="No telecom stats are available.",
            )

        lines = [
            "# Telecom stats",
            f"Total towers: {data.get('total', 'N/A')}",
            f"Unique carriers: {data.get('unique_carriers', 'N/A')}",
            f"Unique technologies: {data.get('unique_technologies', 'N/A')}",
        ]
        if data.get("avg_height") is not None:
            lines.append(f"Average height: {data['avg_height']} m")
        if data.get("min_height") is not None and data.get("max_height") is not None:
            lines.append(f"Height range: {data['min_height']}–{data['max_height']} m")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
