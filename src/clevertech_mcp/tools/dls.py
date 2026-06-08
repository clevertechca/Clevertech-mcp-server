"""DLS conversion MCP tools.

Provides GPS ↔ Dominion Land Survey (DLS) coordinate conversion for Western
Canadian provinces (Alberta, Saskatchewan, Manitoba).
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP
from clevertech_mcp.client import CleverTechClient


def register_dls_tools(mcp: FastMCP, client: CleverTechClient, config: dict) -> None:
    """Register DLS conversion tools on the FastMCP server."""

    @mcp.tool(
        name="dls_convert",
        description=(
            "Convert between GPS coordinates and Dominion Land Survey (DLS) "
            "grid system used in Western Canada. Supports GPS→DLS and "
            "DLS→GPS directions."
        ),
    )
    async def dls_convert(
        direction: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        dls_string: Optional[str] = None,
        province: Optional[str] = None,
    ) -> str:
        """Convert a single coordinate between GPS and DLS.

        Args:
            direction: 'gps_to_dls' or 'dls_to_gps'.
            lat: Latitude (required for gps_to_dls).
            lon: Longitude (required for gps_to_dls).
            dls_string: DLS grid reference (required for dls_to_gps).
            province: Province code AB/SK/MB (optional, auto-detected).
        """
        if direction == "gps_to_dls":
            if lat is None or lon is None:
                return "Error: lat and lon are required for gps_to_dls direction."
            payload: dict = {"lat": lat, "lon": lon}
            if province:
                payload["province"] = province
            data = await client.post("/api/v1/convert/gps-to-dls", json=payload)
        else:
            if not dls_string:
                return "Error: dls_string is required for dls_to_gps direction."
            payload = {"dls_string": dls_string}
            if province:
                payload["province"] = province
            data = await client.post("/api/v1/convert/dls-to-gps", json=payload)

        lines: list[str] = []
        if data.get("dls"):
            lines.append(f"DLS: {data['dls']}")
        if data.get("province"):
            lines.append(f"Province: {data['province']}")
        if "lat" in data and "lon" in data:
            lines.append(f"GPS: {data['lat']}, {data['lon']}")
        if data.get("confidence"):
            lines.append(f"Confidence: {data['confidence']}")
        if data.get("distance_km"):
            lines.append(f"Distance to grid center: {data['distance_km']} km")
        if data.get("_message"):
            lines.append(f"\n{data['message']}")

        return "\n".join(lines) if lines else "No result returned."

    @mcp.tool(
        name="dls_batch",
        description=(
            "Convert multiple GPS coordinates to DLS or multiple DLS strings "
            "to GPS in a single batch request. Up to 100 items per batch."
        ),
    )
    async def dls_batch(
        direction: str,
        items: list[dict],
        province: Optional[str] = None,
    ) -> str:
        """Batch convert coordinates.

        Args:
            direction: 'gps_to_dls' or 'dls_to_gps'.
            items: List of coordinate objects.
                   gps_to_dls: [{"lat": 51.0, "lon": -114.0}, ...]
                   dls_to_gps: [{"dls_string": "NW-16-24-1-W5"}, ...]
            province: Province code (optional).
        """
        if not items:
            return "Error: items list is empty."
        if len(items) > 100:
            return "Error: batch limited to 100 items."

        payload: dict = {"direction": direction, "items": items}
        if province:
            payload["province"] = province

        data = await client.post("/api/v1/convert/batch", json=payload)

        results = data.get("results", [])
        lines: list[str] = [f"Batch result: {data.get('count', 0)} conversions"]

        for i, r in enumerate(results[:20]):
            if r.get("dls"):
                line = f"{i + 1}. {r['dls']}"
                if "lat" in r and "lon" in r:
                    line += f" → ({r['lat']}, {r['lon']})"
                lines.append(line)

        if len(results) > 20:
            lines.append(f"\n... and {len(results) - 20} more")

        if data.get("_message"):
            lines.append(f"\n{data['message']}")

        return "\n".join(lines)
