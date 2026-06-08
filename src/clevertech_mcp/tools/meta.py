"""Meta MCP tools — server info, capabilities, city listing.

Discovery endpoints so callers can learn which cities and services are
available before making domain-specific calls.
"""

import json

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_meta_tools(mcp: FastMCP, client: CleverTechClient, config: dict) -> None:
    """Register meta-discovery tools on the FastMCP server."""

    @mcp.tool(
        name="list_cities",
        description=(
            "List all available cities with their slugs, API capabilities, "
            "and property counts. Use this first to discover which cities are "
            "available and what services each supports."
        ),
    )
    async def list_cities() -> str:
        """List available cities and their capabilities."""
        data = await client.get("/api/cities")

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
