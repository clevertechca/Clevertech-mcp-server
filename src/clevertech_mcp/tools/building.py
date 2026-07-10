"""Building permit MCP tools."""

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip


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
        description="Search building permits by address, contractor, applicant, or permit number across 13+ Canadian cities. Returns permit details including type, value, status, and dates.",
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
        description="Get the most recently issued building permits for a city. Useful for monitoring new construction activity.",
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
