"""DLS conversion MCP tools.

Provides GPS ↔ Dominion Land Survey (DLS) coordinate conversion for Western
Canadian provinces (Alberta, Saskatchewan, Manitoba).
"""

from typing import Optional

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


def _format_batch_results(results: list, total_hint: Optional[int] = None) -> str:
    total = total_hint if total_hint is not None else len(results)
    lines: list[str] = [f"Batch result: {total} conversions"]

    for i, r in enumerate(results[:20]):
        # Upstream BatchResultItem: {success, data: {dls, lat, lon, ...}, error}
        if isinstance(r, dict) and "data" in r and isinstance(r.get("data"), dict):
            data = r["data"] or {}
            if not r.get("success", True):
                lines.append(f"{i + 1}. ERROR: {r.get('error', 'failed')}")
                continue
        else:
            data = r if isinstance(r, dict) else {}

        if data.get("dls"):
            line = f"{i + 1}. {data['dls']}"
            lat, lon = data.get("lat"), data.get("lon")
            if lat is not None and lon is not None:
                line += f" → ({lat}, {lon})"
            elif data.get("center_lat") is not None and data.get("center_lon") is not None:
                line += f" (center {data['center_lat']}, {data['center_lon']})"
            lines.append(line)
        elif "lat" in data and "lon" in data:
            dls = data.get("dls_string") or data.get("input") or ""
            lines.append(f"{i + 1}. {dls} → ({data['lat']}, {data['lon']})".strip())
        else:
            lines.append(f"{i + 1}. {data}")

    if len(results) > 20:
        lines.append(f"\n... and {len(results) - 20} more")

    return "\n".join(lines)


def register_dls_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
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
        ctx: Context = None,
    ) -> str:
        """Convert a single coordinate between GPS and DLS.

        Args:
            direction: 'gps_to_dls' or 'dls_to_gps'.
            lat: Latitude (required for gps_to_dls).
            lon: Longitude (required for gps_to_dls).
            dls_string: DLS grid reference (required for dls_to_gps).
            province: Province code AB/SK/MB (optional, auto-detected).
        """
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        if direction == "gps_to_dls":
            if lat is None or lon is None:
                return "Error: lat and lon are required for gps_to_dls direction."
            payload: dict = {"lat": lat, "lon": lon}
            if province:
                payload["province"] = province
            data = await client.post(
                "/api/v1/convert/gps-to-dls", json=payload, api_key=upstream_key
            )
        else:
            if not dls_string:
                return "Error: dls_string is required for dls_to_gps direction."
            payload = {"dls_string": dls_string}
            if province:
                payload["province"] = province
            data = await client.post(
                "/api/v1/convert/dls-to-gps", json=payload, api_key=upstream_key
            )

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
            lines.append(f"\n{data['_message']}")

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
        ctx: Context = None,
    ) -> str:
        """Batch convert coordinates.

        Args:
            direction: 'gps_to_dls' or 'dls_to_gps'.
            items: List of coordinate objects.
                   gps_to_dls: [{"lat": 51.0, "lon": -114.0}, ...]
                   dls_to_gps: [{"dls_string": "NW-16-24-1-W5"}, ...]
            province: Province code (optional).
        """
        # Resolve user API key and rate limit anonymous users
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        if not items:
            return "Error: items list is empty."
        if len(items) > 100:
            return "Error: batch limited to 100 items."
        if direction not in ("gps_to_dls", "dls_to_gps"):
            return "Error: direction must be 'gps_to_dls' or 'dls_to_gps'."

        # Live gateway paths (dls_batch_router prefix=/batch under /api/v1)
        batch_path = (
            "/api/v1/batch/gps-to-dls"
            if direction == "gps_to_dls"
            else "/api/v1/batch/dls-to-gps"
        )
        payload: dict = {"items": items}
        if province:
            payload["province"] = province

        try:
            data = await client.post(batch_path, json=payload, api_key=upstream_key)
            results = data.get("results", [])
            total = data.get("total", data.get("count", len(results)))
            out = _format_batch_results(results, total_hint=total)
            if data.get("successful") is not None:
                out += f"\nSuccessful: {data.get('successful')} / Failed: {data.get('failed', 0)}"
            if data.get("_message") or data.get("message"):
                out += f"\n{data.get('_message') or data.get('message')}"
            return out
        except httpx.HTTPStatusError:
            # Upstream batch is currently flaky (500s); fall back to sequential singles.
            pass
        except Exception:
            pass

        # Sequential fallback via single convert endpoints (known-good)
        results = []
        for item in items:
            try:
                if direction == "gps_to_dls":
                    single_payload = {
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                    }
                    if province or item.get("province"):
                        single_payload["province"] = province or item.get("province")
                    data = await client.post(
                        "/api/v1/convert/gps-to-dls",
                        json=single_payload,
                        api_key=upstream_key,
                    )
                    results.append({"success": True, "data": data})
                else:
                    dls_val = item.get("dls_string") or item.get("dls")
                    single_payload = {"dls_string": dls_val}
                    if province or item.get("province"):
                        single_payload["province"] = province or item.get("province")
                    data = await client.post(
                        "/api/v1/convert/dls-to-gps",
                        json=single_payload,
                        api_key=upstream_key,
                    )
                    results.append({"success": True, "data": data})
            except Exception as e:
                results.append({"success": False, "error": str(e), "data": {}})

        out = _format_batch_results(results)
        out += "\n(Note: used sequential convert fallback — batch endpoint unavailable)"
        return out
