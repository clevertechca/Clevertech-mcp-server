"""Building permit MCP tools."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip
from clevertech_mcp.schema_hints import CITY_SLUG

_BUILDING_PERMIT_SEARCH_DESCRIPTION = (
    "Full-text search of issued building permits in a city by address fragment, "
    "contractor, applicant name, or permit ID. Returns permit type, status, job value, "
    "and issue date for each match (paginated up to limit). "
    "Use building_permit_recent for a chronological feed of the newest permits city-wide "
    "without a search query; use property_report for permits tied to one assessment roll. "
    "Requires CLEVERTECH_API_KEY."
)

_BUILDING_PERMIT_RECENT_DESCRIPTION = (
    "List the most recently issued building permits in a city (newest first), without "
    "a search query — useful for construction activity monitoring or news digests. "
    "Use building_permit_search when you need to filter by address, contractor, "
    "applicant, or permit number. Requires city slug from list_cities."
)


def _permit_id(r: dict) -> str:
    """Upstream uses permit_id; older fixtures/docs used permit_number."""
    return r.get("permit_id") or r.get("permit_number") or "N/A"


def _permit_value(r: dict):
    """Upstream uses estimated_value; older fixtures used job_value."""
    if r.get("estimated_value") is not None:
        return r.get("estimated_value")
    return r.get("job_value")


def _permit_issued(r: dict) -> str:
    """Upstream uses issue_date; older fixtures used issued_date."""
    return r.get("issue_date") or r.get("issued_date") or "N/A"


def _format_permit_block(r: dict) -> list[str]:
    value = _permit_value(r)
    value_line = f"Value: ${value:,.0f}" if value is not None else "Value: N/A"
    return [
        "",
        "---",
        f"Permit: {_permit_id(r)}",
        f"Type: {r.get('permit_type', 'N/A')}",
        f"Status: {r.get('status', 'N/A')}",
        f"Address: {r.get('address', 'N/A')}",
        f"Applicant: {r.get('applicant', 'N/A')}",
        value_line,
        f"Issued: {_permit_issued(r)}",
    ]


def register_building_tools(mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter):
    """Register building permit tools."""

    @mcp.tool(
        name="building_permit_search",
        description=_BUILDING_PERMIT_SEARCH_DESCRIPTION,
    )
    async def building_permit_search(
        city: Annotated[str, Field(description=CITY_SLUG)],
        q: Annotated[
            str,
            Field(
                description=(
                    "Search text: street address, contractor name, applicant, or permit "
                    "number/ID. Required."
                )
            ),
        ],
        permit_type: Annotated[
            Optional[str],
            Field(
                description=(
                    "Optional filter on permit category (city-specific), e.g. Building, "
                    "Demolition, Electrical."
                )
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Max permits to return (1–200, default 20).", ge=1, le=200),
        ] = 20,
        ctx: Context = None,
    ) -> str:
        """Search building permits."""
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {"q": q, "limit": min(limit, 200)}
        if permit_type:
            params["permit_type"] = permit_type

        data = await client.get(f"/api/{city}/building/search", params=params, api_key=upstream_key)

        results = data.get("results", [])
        total = data.get("total", 0)
        message = data.get("_message", "")

        lines = [f"Found {len(results)} of {total} building permits"]
        if message:
            lines.append(f"\n{message}")

        for r in results:
            lines.extend(_format_permit_block(r))

        return "\n".join(lines)

    @mcp.tool(
        name="building_permit_recent",
        description=_BUILDING_PERMIT_RECENT_DESCRIPTION,
    )
    async def building_permit_recent(
        city: Annotated[str, Field(description=CITY_SLUG)],
        limit: Annotated[
            int,
            Field(description="Number of recent permits to return (1–100, default 20).", ge=1, le=100),
        ] = 20,
        ctx: Context = None,
    ) -> str:
        """Get recently issued permits."""
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get(
            f"/api/{city}/building/recent",
            params={"limit": min(limit, 100)},
            api_key=upstream_key,
        )

        results = data.get("results", [])
        message = data.get("_message", "")

        lines = [f"Recent building permits ({len(results)})"]
        if message:
            lines.append(f"\n{message}")

        for r in results:
            lines.extend(_format_permit_block(r))

        return "\n".join(lines)
