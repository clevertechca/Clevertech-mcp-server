"""Business registry MCP tools."""

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_business_tools(mcp: FastMCP, client: CleverTechClient, config: dict):
    """Register business registry tools."""

    @mcp.tool(
        name="business_registry_search",
        description="Search the Canadian federal business registry. Find corporations by name, province, city, status, or industry act.",
    )
    async def business_registry_search(
        q: str,
        province: str = None,
        city: str = None,
        status: str = None,
        limit: int = 25,
    ) -> str:
        """Search the business registry.

        Args:
            q: Corporation name or keyword
            province: Two-letter province code (AB, BC, ON, QC, etc.)
            city: City name
            status: Corporation status (Active, Dissolved, etc.)
            limit: Max results (1-100, default 25)
        """
        params = {"q": q, "limit": min(limit, 100)}
        if province:
            params["province"] = province
        if city:
            params["city"] = city
        if status:
            params["status"] = status

        data = await client.get("/api/registry/search", params=params)

        results = data.get("results", [])
        total = data.get("total", len(results))
        message = data.get("_message", "")

        lines = [f"Found {len(results)} of {total} corporations"]
        if message:
            lines.append(f"\n{message}")

        for r in results:
            lines.extend([
                "",
                "---",
                f"Name: {r.get('corporation_name', r.get('name', 'N/A'))}",
                f"Number: {r.get('corporation_number', r.get('number', 'N/A'))}",
                f"Status: {r.get('status', 'N/A')}",
                f"Jurisdiction: {r.get('jurisdiction', r.get('province', 'N/A'))}",
            ])
            if r.get('registered_address'):
                lines.append(f"Address: {r['registered_address']}")

        return "\n".join(lines)
