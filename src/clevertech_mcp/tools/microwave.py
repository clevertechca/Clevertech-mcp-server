"""ISED microwave-link MCP tools.

Wraps the documented ``/api/microwave`` routes: radius, search, stats, and
authorization detail. Nearby radius defaults to 2 km because a 5 km live
call returned hundreds of links.
"""

from typing import Any
from urllib.parse import quote

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
from clevertech_mcp.params import canadian_gps_error, clamp_limit, nonempty_term

_MAX_RADIUS_KM = 25.0
_DEFAULT_RADIUS_KM = 2.0


def _rows(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "links", "items"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def _clamp_radius(radius_km: float) -> float:
    try:
        n = float(radius_km)
    except (TypeError, ValueError):
        return _DEFAULT_RADIUS_KM
    return max(1.0, min(n, _MAX_RADIUS_KM))


def _format_link(row: dict) -> list[str]:
    auth = row.get(
        "authorization_number",
        row.get("authorization", row.get("id", "N/A")),
    )
    lines = [
        "",
        "---",
        f"Authorization: {auth}",
        f"Licensee: {row.get('licensee', row.get('licensee_name', 'N/A'))}",
        f"Band: {row.get('frequency_band', row.get('band', 'N/A'))}",
        f"Province: {row.get('province', 'N/A')}",
    ]
    if row.get("distance_km") is not None:
        lines.append(f"Distance: {row['distance_km']} km")
    return lines


def register_microwave_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register microwave radius, search, stats, and authorization tools."""

    @mcp.tool(
        name="microwave_nearby",
        description=(
            "Find ISED-licensed microwave links near a GPS point. Default "
            "radius is 2 km (a 5 km live call returned hundreds of links); "
            "radius is clamped to 1–25 km. Lat/lon must be within Canadian "
            "bounds (lat 41–84, lon −142 to −52)."
        ),
    )
    async def microwave_nearby(
        lat: float = None,
        lon: float = None,
        radius_km: float = _DEFAULT_RADIUS_KM,
        limit: int = 50,
        ctx: Context = None,
    ) -> str:
        """Get microwave links near a GPS point.

        Args:
            lat: Latitude (Canadian bounds).
            lon: Longitude (Canadian bounds).
            radius_km: Search radius in km (1-25, default 2).
            limit: Max results (1-200, default 50).
        """
        gps_error = canadian_gps_error(lat, lon)
        if gps_error:
            return gps_error

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                "/api/microwave/radius",
                params={
                    "lat": lat,
                    "lon": lon,
                    "radius_km": _clamp_radius(radius_km),
                    "limit": clamp_limit(limit, maximum=200),
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No microwave links found near GPS {lat}, {lon}.",
            )

        rows = _rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} microwave links"]
        for row in rows:
            if isinstance(row, dict):
                lines.extend(_format_link(row))
        return "\n".join(lines)

    @mcp.tool(
        name="microwave_search",
        description=(
            "Search ISED-licensed microwave links. Pass a licensee or keyword "
            "as `q` (preferred) or `query` (alias). If both are given, `q` "
            "wins. Empty or whitespace-only `q` is treated as missing so "
            "`query` is used. The search term is sent as the API `licensee` "
            "filter."
        ),
    )
    async def microwave_search(
        q: str | None = None,
        query: str | None = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Search microwave links by licensee keyword.

        Args:
            q: Licensee or keyword (preferred). Wins if both q and query are non-empty.
            query: Alias for q. Used when q is omitted, empty, or whitespace-only.
            limit: Max results (1-200, default 20).
        """
        search = nonempty_term(q) or nonempty_term(query)
        if search is None:
            return (
                "Error: provide q or query (licensee or keyword). "
                "If both are given, q wins."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                "/api/microwave/search",
                params={
                    "licensee": search,
                    "limit": clamp_limit(limit, maximum=200),
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No microwave links found for {search!r}.",
            )

        rows = _rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} microwave links"]
        for row in rows:
            if isinstance(row, dict):
                lines.extend(_format_link(row))
        return "\n".join(lines)

    @mcp.tool(
        name="microwave_stats",
        description="Get national ISED microwave-link network statistics.",
    )
    async def microwave_stats(ctx: Context = None) -> str:
        """Get microwave network stats."""
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get("/api/microwave/stats", api_key=upstream_key)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found="No microwave stats are available.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Microwave stats"]
        for key, value in data.items():
            if key == "_message":
                continue
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for inner_key, inner_value in value.items():
                    lines.append(f"- {inner_key}: {inner_value}")
            else:
                lines.append(f"{key}: {value}")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="microwave_by_authorization",
        description=(
            "Get one ISED microwave authorization by number (for example "
            "0002315559). Pass the id as `authorization_number` (preferred), "
            "`q`, or `query`. If more than one is given, authorization_number "
            "wins, then q."
        ),
    )
    async def microwave_by_authorization(
        authorization_number: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a microwave authorization by id.

        Args:
            authorization_number: Authorization number (preferred).
            q: Alias for authorization_number.
            query: Alias for authorization_number / q.
        """
        auth_id = (
            nonempty_term(authorization_number)
            or nonempty_term(q)
            or nonempty_term(query)
        )
        if auth_id is None:
            return (
                "Error: provide authorization_number (preferred), q, or query. "
                "If more than one is given, authorization_number wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        encoded = quote(auth_id, safe="")
        try:
            data = await client.get(
                f"/api/microwave/authorization/{encoded}",
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No microwave authorization found for {auth_id}.",
            )

        rows = _rows(data)
        if not rows and isinstance(data, dict):
            rows = [data]
        if not rows:
            return f"No microwave links returned for authorization {auth_id}."

        lines = [
            f"# Microwave authorization ({len(rows)} "
            f"link{'s' if len(rows) != 1 else ''})"
        ]
        for row in rows:
            if isinstance(row, dict):
                lines.extend(_format_link(row))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
