"""Property-related MCP tools.

Search, lookup, and report on properties across Canadian cities.
Provides assessment data, building permits, zoning, and DLS coordinates.
"""

import json

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip


def register_property_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register property search, by-roll, and report tools."""

    @mcp.tool(
        name="property_search",
        description=(
            "Search for properties by address across 13+ Canadian cities. "
            "Returns assessment data including value, lot size, year built, "
            "and DLS coordinates. Supports sorting by assessed_value, address, "
            "year_built, community, and value range filtering."
        ),
    )
    async def property_search(
        city: str,
        address: str,
        limit: int = 10,
        offset: int = 0,
        sort_by: str = None,
        order: str = "asc",
        min_value: float = None,
        max_value: float = None,
        ctx: Context = None,
    ) -> str:
        """Search for properties by address.

        Args:
            city: City slug (calgary, toronto, vancouver, montreal, edmonton,
                  etc.).
            address: Street address to search (partial matches supported).
            limit: Max results (1-200, default 10).
            offset: Pagination offset.
            sort_by: Sort column: assessed_value, address, year_built, community, lot_size_sqft.
            order: Sort order: asc or desc.
            min_value: Only return properties with assessed_value >= this.
            max_value: Only return properties with assessed_value <= this.
        """
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {
            "address": address,
            "limit": min(limit, 200),
            "offset": offset,
        }
        if sort_by:
            params["sort_by"] = sort_by
        if order:
            params["order"] = order
        if min_value is not None:
            params["min_value"] = min_value
        if max_value is not None:
            params["max_value"] = max_value

        data = await client.get(
            f"/api/{city}/property/search",
            params=params,
            api_key=upstream_key,
        )

        results = data.get("results", [])
        total = data.get("total", 0)
        message = data.get("_message", "")

        lines: list[str] = [f"Found {len(results)} of {total} properties"]
        if message:
            lines.append(f"\n{message}")

        for r in results:
            lines.extend(
                [
                    "",
                    "---",
                    f"Address: {r.get('address', 'N/A')}",
                    f"Roll: {r.get('roll_number', 'N/A')}",
                ]
            )
            if r.get("assessed_value") is not None:
                lines.append(f"Assessed Value: ${r['assessed_value']:,.0f}")
            else:
                lines.append("Assessed Value: N/A")
            lines.append(f"Type: {r.get('property_type', 'N/A')}")
            if r.get("dls"):
                lines.append(f"DLS: {r['dls']}")

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
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(f"/api/{city}/property/report/{roll_number}", api_key=upstream_key)

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
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(f"/api/{city}/property/by-roll/{roll_number}", api_key=upstream_key)
        return json.dumps(data, indent=2, default=str)

    @mcp.tool(
        name="property_top",
        description=(
            "Get the top-N properties in a city sorted by assessed value, "
            "year built, or lot size. Perfect for finding the most expensive, "
            "oldest, or largest properties. Returns full assessment details "
            "for each result."
        ),
    )
    async def property_top(
        city: str,
        n: int = 10,
        sort_by: str = "assessed_value",
        order: str = "desc",
        min_value: float = None,
        max_value: float = None,
        ctx: Context = None,
    ) -> str:
        """Get top-N properties sorted by a numeric column.

        Args:
            city: City slug.
            n: Number of results (1-100, default 10).
            sort_by: Column to sort by: assessed_value, year_built, lot_size_sqft.
            order: Sort order: asc or desc (default desc for top-N).
            min_value: Optional minimum assessed value filter.
            max_value: Optional maximum assessed value filter.
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {
            "n": min(n, 100),
            "sort_by": sort_by,
            "order": order,
        }
        if min_value is not None:
            params["min_value"] = min_value
        if max_value is not None:
            params["max_value"] = max_value

        data = await client.get(
            f"/api/{city}/property/top",
            params=params,
            api_key=upstream_key,
        )

        results = data.get("results", [])
        lines: list[str] = [
            f"Top {len(results)} properties in {city.title()} "
            f"(sorted by {sort_by} {order}):"
        ]

        for i, r in enumerate(results, 1):
            lines.extend([
                "",
                f"## {i}. {r.get('address', 'N/A')}",
                f"- Roll: {r.get('roll_number', 'N/A')}",
            ])
            if r.get("assessed_value") is not None:
                lines.append(f"- Assessed Value: ${r['assessed_value']:,.0f}")
            if r.get("year_built"):
                lines.append(f"- Year Built: {r['year_built']}")
            if r.get("lot_size_sqm"):
                lines.append(f"- Lot Size: {r['lot_size_sqm']:,} m²")
            if r.get("property_type"):
                lines.append(f"- Type: {r['property_type']}")
            if r.get("dls"):
                lines.append(f"- DLS: {r['dls']}")

        return "\n".join(lines)
