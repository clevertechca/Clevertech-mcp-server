"""Public-safety MCP tools.

Wraps the documented city safety endpoints plus the national
``GET /api/v2/safety/summary`` route. City slugs match list_cities
(hyphenated, e.g. toronto). The national summary is known to time out
on the current API; that failure is returned as a clear tool error.
"""

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


_SUMMARY_TIMEOUT = (
    "Error: the national safety summary timed out before a response arrived. "
    "This endpoint is currently slow (a CleverTech API fix is in progress). "
    "Retry later, or use safety_nearby / safety_stats for a single city."
)


def _format_incident(row: dict) -> list[str]:
    record_id = row.get("source_record_id", row.get("id", "N/A"))
    lines = [
        "",
        "---",
        f"Id: {record_id}",
        f"Category: {row.get('category', 'N/A')}",
        f"Injury: {row.get('injury', 'N/A')}",
        f"Neighbourhood: {row.get('neighbourhood', 'N/A')}",
        f"Occurred: {row.get('occurred_at', 'N/A')}",
    ]
    if row.get("street_label"):
        lines.append(f"Street: {row['street_label']}")
    if row.get("road_user"):
        lines.append(f"Road user: {row['road_user']}")
    if row.get("source_family"):
        lines.append(f"Source: {row['source_family']}")
    if row.get("lat") is not None and row.get("lon") is not None:
        lines.append(f"GPS: {row['lat']}, {row['lon']}")
    return lines


def register_safety_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register nearby, search, stats, by-id, and national summary tools."""

    @mcp.tool(
        name="safety_nearby",
        description=(
            "Look up public-safety incidents near a GPS point in a Canadian city "
            "(currently a small set of cities such as Toronto). Returns involved-"
            "person rows with category, injury, neighbourhood, and time. Use a "
            "city slug from list_cities. Default limit is 20."
        ),
    )
    async def safety_nearby(
        city: str,
        lat: float = None,
        lon: float = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Get safety incidents near a GPS point.

        Args:
            city: City slug (toronto, etc.).
            lat: Latitude.
            lon: Longitude.
            limit: Max results (1-200, default 20).
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
                f"/api/{city}/safety/nearby",
                params={"lat": lat, "lon": lon, "limit": clamp_limit(limit, maximum=200)},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=(
                    f"No safety incidents found near GPS {lat}, {lon} in {city}."
                ),
            )

        results = data.get("results", [])
        total = data.get("total", data.get("count", len(results)))
        message = data.get("_message", "")
        lines = [f"Found {len(results)} of {total} safety incidents"]
        if message:
            lines.append(f"\n{message}")
        for row in results:
            lines.extend(_format_incident(row))
        return "\n".join(lines)

    @mcp.tool(
        name="safety_search",
        description=(
            "Search involved-person public-safety rows for a Canadian city. "
            "Pass the search term as `q` (preferred) or `query` (alias). If both "
            "are given, `q` wins. Empty or whitespace-only `q` is treated as "
            "missing so `query` is used. City slug from list_cities (e.g. toronto)."
        ),
    )
    async def safety_search(
        city: str,
        q: str | None = None,
        query: str | None = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Search safety incidents.

        Args:
            city: City slug (toronto, etc.).
            q: Search query (preferred). Wins if both q and query are non-empty.
            query: Alias for q. Used when q is omitted, empty, or whitespace-only.
            limit: Max results (1-200, default 20).
        """
        search = nonempty_term(q) or nonempty_term(query)
        if search is None:
            return (
                "Error: provide q or query (keyword, neighbourhood, or record id). "
                "If both are given, q wins."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/safety/search",
                params={"q": search, "limit": clamp_limit(limit, maximum=200)},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No safety incidents found for {search!r} in {city}.",
            )

        results = data.get("results", [])
        total = data.get("total", data.get("count", len(results)))
        message = data.get("_message", "")
        lines = [f"Found {len(results)} of {total} safety incidents"]
        if message:
            lines.append(f"\n{message}")
        for row in results:
            lines.extend(_format_incident(row))
        return "\n".join(lines)

    @mcp.tool(
        name="safety_stats",
        description=(
            "Get aggregate public-safety statistics for a Canadian city: total "
            "rows and counts by injury. Use a city slug from list_cities "
            "(e.g. toronto)."
        ),
    )
    async def safety_stats(city: str, ctx: Context = None) -> str:
        """Get safety aggregate stats for a city.

        Args:
            city: City slug (toronto, etc.).
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/safety/stats", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No safety stats found for {city}.",
            )

        lines = [
            "# Safety stats",
            f"Total rows: {data.get('total_rows', data.get('total', 'N/A'))}",
        ]
        if data.get("distinct_collisions") is not None:
            lines.append(f"Distinct collisions: {data['distinct_collisions']}")
        by_injury = data.get("by_injury") or {}
        if isinstance(by_injury, dict) and by_injury:
            lines.append("By injury:")
            for label, count in by_injury.items():
                lines.append(f"- {label}: {count}")
        by_category = data.get("by_category") or {}
        if isinstance(by_category, dict) and by_category:
            lines.append("By category:")
            for label, count in by_category.items():
                lines.append(f"- {label}: {count}")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="safety_by_id",
        description=(
            "Get one public-safety source row by id (for example "
            "toronto_shootings:GO-2004195761). Colons in the id are URL-encoded. "
            "Pass the id as `source_record_id` (preferred), `q`, or `query`. If "
            "more than one is given, source_record_id wins, then q. Empty or "
            "whitespace-only `source_record_id` is treated as missing so `q` / "
            "`query` is used. City slug from list_cities (e.g. toronto)."
        ),
    )
    async def safety_by_id(
        city: str,
        source_record_id: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a single safety record by source_record_id.

        Args:
            city: City slug (toronto, etc.).
            source_record_id: Source row id (preferred). Wins if source_record_id,
                              q, and query are all non-empty.
            q: Alias for source_record_id. Used when source_record_id is omitted,
               empty, or whitespace-only. Wins over query when both q and query
               are given.
            query: Alias for source_record_id / q.
        """
        record_id = (
            nonempty_term(source_record_id)
            or nonempty_term(q)
            or nonempty_term(query)
        )
        if record_id is None:
            return (
                "Error: provide source_record_id (preferred), q, or query. "
                "If more than one is given, source_record_id wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        encoded = quote(record_id, safe="")
        try:
            data = await client.get(
                f"/api/{city}/safety/{encoded}", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No safety record found for {record_id} in {city}.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Safety record"]
        lines.extend(_format_incident(data))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="safety_summary",
        description=(
            "National / area public-safety summary from GET /api/v2/safety/summary. "
            "This route currently times out on the live API; on timeout the tool "
            "returns a clear error instead of a stack trace. Prefer safety_nearby "
            "or safety_stats for a single city until the API fix lands."
        ),
    )
    async def safety_summary(
        category: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get the national safety summary.

        Args:
            category: Optional category filter.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params: dict = {}
        if nonempty_term(category):
            params["category"] = category.strip()

        try:
            data = await client.get(
                "/api/v2/safety/summary",
                params=params or None,
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found="No national safety summary is available.",
                timeout=_SUMMARY_TIMEOUT,
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Safety summary"]
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
