"""Meta MCP tools — server info, capabilities, city listing.

Discovery endpoints so callers can learn which cities and services are
available before making domain-specific calls.
"""

import json

from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import (
    _get_user_api_key,
    get_upstream_key,
    is_authenticated,
    _extract_client_ip,
)


def register_meta_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register meta-discovery tools on the FastMCP server."""

    @mcp.tool(
        name="list_cities",
        description=(
            "List all available cities with their slugs, API capabilities, "
            "and property counts. Use this first to discover which cities are "
            "available and what services each supports."
        ),
    )
    async def list_cities(ctx: Context = None) -> str:
        """List available cities and their capabilities."""
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        data = await client.get("/api/cities", api_key=upstream_key)

        cities = data.get("cities", data.get("results", []))
        if not cities:
            return json.dumps(data, indent=2, default=str)

        lines: list[str] = ["# Available Cities\n"]
        for city in cities:
            name = city.get("name", city.get("city", "Unknown"))
            slug = city.get("slug", city.get("city_slug", "?"))
            props = city.get("property_count", city.get("count", "?"))
            services = city.get("services", city.get("capabilities", []))

            lines.append(f"## {name}")
            lines.append(f"- Slug: {slug}")
            if isinstance(props, int):
                lines.append(f"- Properties: {props:,}")
            else:
                lines.append(f"- Properties: {props}")
            if services:
                lines.append(f"- Services: {', '.join(services)}")
            lines.append("")

        return "\n".join(lines)
