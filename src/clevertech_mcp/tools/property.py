"""Property-related MCP tools.

Search, lookup, nearby, stats, batch, and report on properties across
Canadian cities.
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
    split_ids,
)


def _rows(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "properties", "found", "items"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def _format_property_row(r: dict) -> list[str]:
    lines = [
        "",
        "---",
        f"Address: {r.get('address', 'N/A')}",
        f"Roll: {r.get('roll_number', 'N/A')}",
    ]
    if r.get("assessed_value") is not None:
        lines.append(f"Assessed Value: ${r['assessed_value']:,.0f}")
    else:
        lines.append("Assessed Value: N/A")
    lines.append(f"Type: {r.get('property_type', 'N/A')}")
    if r.get("dls"):
        lines.append(f"DLS: {r['dls']}")
    return lines


def _format_stats(data: dict, *, title: str) -> str:
    lines = [f"# {title}"]
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


def register_property_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register property search, nearby, stats, batch, by-roll, and report tools."""

    @mcp.tool(
        name="property_search",
        description=(
            "Search for properties by address across 13+ Canadian cities. "
            "Returns assessment data including value, lot size, year built, "
            "and DLS coordinates."
        ),
    )
    async def property_search(
        city: str,
        address: str,
        limit: int = 10,
        offset: int = 0,
        ctx: Context = None,
    ) -> str:
        """Search for properties by address.

        Args:
            city: City slug (calgary, toronto, vancouver, montreal, edmonton,
                  etc.).
            address: Street address to search (partial matches supported).
            limit: Max results (1-200, default 10).
            offset: Pagination offset.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            f"/api/{city}/property/search",
            params={
                "address": address,
                "limit": min(limit, 200),
                "offset": offset,
            },
            api_key=upstream_key,
        )

        results = data.get("results", [])
        total = data.get("total", 0)
        message = data.get("_message", "")

        lines: list[str] = [f"Found {len(results)} of {total} properties"]
        if message:
            lines.append(f"\n{message}")
        for r in results:
            lines.extend(_format_property_row(r))
        return "\n".join(lines)

    @mcp.tool(
        name="property_nearby",
        description=(
            "Find properties near a GPS point. Lat/lon must be within Canadian "
            "bounds (lat 41–84, lon −142 to −52). Limit is clamped 1–100 "
            "(v1 by-gps rejects above 100). Optional radius_m (1–5000, "
            "default 100)."
        ),
    )
    async def property_nearby(
        city: str,
        lat: float = None,
        lon: float = None,
        limit: int = 20,
        radius_m: int = 100,
        ctx: Context = None,
    ) -> str:
        """Get properties near a GPS point.

        Args:
            city: City slug.
            lat: Latitude (Canadian bounds).
            lon: Longitude (Canadian bounds).
            limit: Max results (1-100, default 20).
            radius_m: Search radius in metres (1-5000, default 100).
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
                f"/api/{city}/property/by-gps",
                params={
                    "lat": lat,
                    "lon": lon,
                    "limit": clamp_limit(limit, maximum=100),
                    "radius_m": clamp_limit(radius_m, maximum=5000),
                },
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No properties found near GPS {lat}, {lon} in {city}.",
            )

        rows = _rows(data)
        total = data.get("total", len(rows)) if isinstance(data, dict) else len(rows)
        lines = [f"Found {len(rows)} of {total} properties"]
        for r in rows:
            if isinstance(r, dict):
                lines.extend(_format_property_row(r))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="property_stats",
        description="Get aggregate property assessment statistics for a city.",
    )
    async def property_stats(city: str, ctx: Context = None) -> str:
        """Get property stats for a city.

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
                f"/api/{city}/property/stats", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No property stats are available for {city}.",
            )

        if not isinstance(data, dict):
            return str(data)
        return _format_stats(data, title=f"Property stats ({city})")

    @mcp.tool(
        name="property_batch",
        description=(
            "Look up several properties by roll number in one call. Pass "
            "`roll_numbers` as a comma-separated string or a list."
        ),
    )
    async def property_batch(
        city: str,
        roll_numbers: str | list | None = None,
        ctx: Context = None,
    ) -> str:
        """Batch property lookup by roll number.

        Args:
            city: City slug.
            roll_numbers: Comma-separated rolls or a list of roll numbers.
        """
        ids = split_ids(roll_numbers)
        if not ids:
            return "Error: provide one or more roll_numbers."

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.post(
                f"/api/{city}/property/batch",
                json={"ids": ids},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No properties found for the given rolls in {city}.",
            )

        rows = _rows(data)
        not_found = data.get("not_found", []) if isinstance(data, dict) else []
        lines = [f"Found {len(rows)} properties"]
        if not_found:
            lines.append(f"Not found: {', '.join(str(n) for n in not_found)}")
        for r in rows:
            if isinstance(r, dict):
                lines.extend(_format_property_row(r))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="property_report",
        description=(
            "Get a consolidated property report — assessment data, building "
            "permits at this address, zoning information, and DLS coordinates "
            "in a single response."
        ),
    )
    async def property_report(city: str, roll_number: str, ctx: Context = None) -> str:
        """Get a consolidated property report.

        Args:
            city: City slug.
            roll_number: Property roll number.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            f"/api/{city}/property/report",
            params={"roll_number": roll_number},
            api_key=upstream_key,
        )

        message = data.get("_message", "")
        lines: list[str] = [
            "# Property Report",
            f"**Address:** {data.get('address', 'N/A')}",
            f"**Roll:** {data.get('roll_number', 'N/A')}",
            f"**DLS:** {data.get('dls', 'N/A')}",
            f"**Generated:** {data.get('generated_at', 'N/A')}",
        ]

        prop = data.get("property", {})
        if prop:
            lines.append("")
            lines.append("## Assessment")
            if prop.get("assessed_value") is not None:
                lines.append(f"- Assessed Value: ${prop['assessed_value']:,.0f}")
            else:
                lines.append("- Assessed Value: N/A")
            if prop.get("land_value") is not None:
                lines.append(f"- Land: ${prop['land_value']:,.0f}")
            else:
                lines.append("- Land: N/A")
            if prop.get("improvement_value") is not None:
                lines.append(f"- Building: ${prop['improvement_value']:,.0f}")
            else:
                lines.append("- Building: N/A")
            lines.append(f"- Year Built: {prop.get('year_built', 'N/A')}")
            lines.append(f"- Lot Size: {prop.get('lot_size_sqm', 'N/A')} m²")

        permits = data.get("permits", [])
        if permits:
            lines.append(f"\n## Building Permits ({len(permits)})")
            for p in permits[:10]:
                job_value = (
                    f"${p.get('job_value', 0):,.0f}"
                    if p.get("job_value") is not None
                    else "N/A"
                )
                lines.append(
                    f"- {p.get('permit_number', 'N/A')}: "
                    f"{p.get('permit_type', 'N/A')} — {job_value}"
                )

        zoning = data.get("zoning")
        if zoning:
            lines.extend(
                [
                    "",
                    "## Zoning",
                    f"- Zone: {zoning.get('zone_code', 'N/A')}",
                    f"- Description: {zoning.get('description', 'N/A')}",
                ]
            )

        if message:
            lines.append(f"\n{message}")

        return "\n".join(lines)

    @mcp.tool(
        name="property_by_roll",
        description=(
            "Get a single property assessment record by its roll number. "
            "Faster than search when you already know the roll number."
        ),
    )
    async def property_by_roll(city: str, roll_number: str, ctx: Context = None) -> str:
        """Get a property by its roll number.

        Args:
            city: City slug.
            roll_number: Property roll number.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            f"/api/{city}/property/by-roll/{roll_number}", api_key=upstream_key
        )
        if not isinstance(data, dict):
            return str(data)
        lines = ["# Property"]
        lines.extend(_format_property_row(data))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
