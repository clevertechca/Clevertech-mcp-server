"""Building permit MCP tools."""

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip


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
            lines.extend([
                "",
                "---",
                f"Permit: {r.get('permit_number', 'N/A')}",
                f"Type: {r.get('permit_type', 'N/A')}",
                f"Status: {r.get('status', 'N/A')}",
                f"Address: {r.get('address', 'N/A')}",
                f"Applicant: {r.get('applicant', 'N/A')}",
                f"Value: ${r.get('job_value', 0):,.0f}" if r.get('job_value') is not None else "Value: N/A",
                f"Issued: {r.get('issued_date', 'N/A')}",
            ])

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
            lines.extend([
                "",
                "---",
                f"Permit: {r.get('permit_number', 'N/A')}",
                f"Type: {r.get('permit_type', 'N/A')}",
                f"Status: {r.get('status', 'N/A')}",
                f"Address: {r.get('address', 'N/A')}",
                f"Value: ${r.get('job_value', 0):,.0f}" if r.get('job_value') is not None else "Value: N/A",
                f"Issued: {r.get('issued_date', 'N/A')}",
            ])

        return "\n".join(lines)
