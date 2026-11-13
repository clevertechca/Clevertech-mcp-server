"""Building permit MCP tools.

Wraps the documented ``/api/{city}/permits/*`` routes (search, recent,
nearby, by id, stats, batch).
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
from clevertech_mcp.params import (
    canadian_gps_error,
    clamp_limit,
    nonempty_term,
    split_ids,
)


def _rows(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "permits", "found", "items"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def _format_permit(r: dict, *, include_applicant: bool = True) -> list[str]:
    lines = [
        "",
        "---",
        f"Permit: {r.get('permit_number', r.get('id', 'N/A'))}",
        f"Type: {r.get('permit_type', 'N/A')}",
        f"Status: {r.get('status', 'N/A')}",
        f"Address: {r.get('address', 'N/A')}",
    ]
    if include_applicant:
        lines.append(f"Applicant: {r.get('applicant', 'N/A')}")
    if r.get("job_value") is not None:
        lines.append(f"Value: ${r['job_value']:,.0f}")
    else:
        lines.append("Value: N/A")
    lines.append(f"Issued: {r.get('issued_date', 'N/A')}")
    return lines


def register_building_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
):
    """Register building permit tools."""

    @mcp.tool(
        name="building_permit_search",
        description=(
            "Search building permits by address, contractor, applicant, or "
            "permit number across 13+ Canadian cities. Returns permit details "
            "including type, value, status, and dates."
        ),
    )
    async def building_permit_search(
        city: str,
        q: str,
        permit_type: str = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Search building permits.

        Args:
            city: City slug
            q: Search query (address, contractor, applicant, or permit number)
            permit_type: Filter by permit type (e.g., 'Building', 'Demolition', 'Electrical')
            limit: Max results (1-200, default 20)
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {"q": q, "limit": min(limit, 200)}
        if permit_type:
            params["permit_type"] = permit_type

        data = await client.get(
            f"/api/{city}/permits/search", params=params, api_key=upstream_key
        )

        results = data.get("results", [])
        total = data.get("total", 0)
        message = data.get("_message", "")

        lines = [f"Found {len(results)} of {total} building permits"]
        if message:
            lines.append(f"\n{message}")
        for r in results:
            lines.extend(_format_permit(r))
        return "\n".join(lines)

    @mcp.tool(
        name="building_permit_recent",
        description=(
            "Get the most recently issued building permits for a city. "
            "Useful for monitoring new construction activity."
        ),
    )
    async def building_permit_recent(
        city: str,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Get recently issued permits.

        Args:
            city: City slug
            limit: Max results (1-100, default 20)
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            f"/api/{city}/permits/recent",
            params={"limit": min(limit, 100)},
            api_key=upstream_key,
        )

        results = data.get("results", [])
        message = data.get("_message", "")

        lines = [f"Recent building permits ({len(results)})"]
        if message:
            lines.append(f"\n{message}")
        for r in results:
            lines.extend(_format_permit(r, include_applicant=False))
        return "\n".join(lines)

    @mcp.tool(
        name="building_permit_nearby",
        description=(
            "Find building permits near a GPS point. Lat/lon must be within "
            "Canadian bounds (lat 41–84, lon −142 to −52)."
        ),
    )
    async def building_permit_nearby(
        city: str,
        lat: float = None,
        lon: float = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Get permits near a GPS point.

        Args:
            city: City slug.
            lat: Latitude (Canadian bounds).
            lon: Longitude (Canadian bounds).
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
                f"/api/{city}/permits/nearby",
                params={
                    "lat": lat,
                    "lon": lon,
                    "limit": clamp_limit(limit, maximum=200),
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No building permits found near GPS {lat}, {lon} in {city}.",
            )

        rows = _rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} building permits"]
        for r in rows:
            if isinstance(r, dict):
                lines.extend(_format_permit(r))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="building_permit_get",
        description=(
            "Get one building permit by id. Pass `permit_id` (preferred), `q`, "
            "or `query`. If more than one is given, permit_id wins, then q."
        ),
    )
    async def building_permit_get(
        city: str,
        permit_id: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a permit by id.

        Args:
            city: City slug.
            permit_id: Permit number / id (preferred).
            q: Alias for permit_id.
            query: Alias for permit_id / q.
        """
        record_id = nonempty_term(permit_id) or nonempty_term(q) or nonempty_term(query)
        if record_id is None:
            return (
                "Error: provide permit_id (preferred), q, or query. "
                "If more than one is given, permit_id wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        encoded = quote(record_id, safe="")
        try:
            data = await client.get(
                f"/api/{city}/permits/{encoded}", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No building permit found for {record_id} in {city}.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Building permit"]
        lines.extend(_format_permit(data))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="building_permit_stats",
        description="Get aggregate building-permit statistics for a city.",
    )
    async def building_permit_stats(city: str, ctx: Context = None) -> str:
        """Get permit stats for a city.

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
                f"/api/{city}/permits/stats", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No building-permit stats are available for {city}.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = [f"# Building permit stats ({city})"]
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
        name="building_permit_batch",
        description=(
            "Look up several building permits by number in one call. Pass "
            "`permit_numbers` as a comma-separated string or a list."
        ),
    )
    async def building_permit_batch(
        city: str,
        permit_numbers: str | list | None = None,
        ctx: Context = None,
    ) -> str:
        """Batch permit lookup.

        Args:
            city: City slug.
            permit_numbers: Comma-separated ids or a list of permit numbers.
        """
        ids = split_ids(permit_numbers)
        if not ids:
            return "Error: provide one or more permit_numbers."

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.post(
                f"/api/{city}/permits/batch",
                json={"ids": ids},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No building permits found for the given ids in {city}.",
            )

        rows = _rows(data)
        not_found = data.get("not_found", []) if isinstance(data, dict) else []
        lines = [f"Found {len(rows)} building permits"]
        if not_found:
            lines.append(f"Not found: {', '.join(str(n) for n in not_found)}")
        for r in rows:
            if isinstance(r, dict):
                lines.extend(_format_permit(r))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
