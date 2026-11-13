"""Location v2 MCP tools — resolve and nearby-dataset context.

``POST /api/v2/locations/resolve`` takes a LocationRequest body with
exactly one of ``address``, ``coordinates``, or ``dls`` (optional
``city``). Unknown fields such as ``q`` are rejected by the API (422),
so this tool never sends ``q``.

``GET /api/v2/locations/context`` fans out to several upstream datasets
and may consume more than one API call / rate-limit unit.
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
from clevertech_mcp.params import canadian_gps_error, clamp_limit, nonempty_term


def _format_mapping(data: dict, *, skip: set[str] | None = None) -> list[str]:
    skip = skip or set()
    lines: list[str] = []
    for key, value in data.items():
        if key in skip or key == "_message" or value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for inner_key, inner_value in value.items():
                lines.append(f"- {inner_key}: {inner_value}")
        elif isinstance(value, list):
            lines.append(f"{key}: {len(value)} item(s)")
            for item in value[:8]:
                if isinstance(item, dict):
                    label = (
                        item.get("name")
                        or item.get("address")
                        or item.get("id")
                        or item
                    )
                    lines.append(f"- {label}")
                else:
                    lines.append(f"- {item}")
        else:
            lines.append(f"{key}: {value}")
    return lines


def register_location_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register location resolve and context tools."""

    @mcp.tool(
        name="location_resolve",
        description=(
            "Resolve a Canadian location from exactly one of: an address, a "
            "GPS pin, or a DLS legal land description via POST "
            "/api/v2/locations/resolve. Combinations are rejected locally "
            "(upstream requires exactly one). Send LocationRequest fields "
            "only (optional city) — never `q`, which the API rejects with "
            "422. GPS must be within Canadian bounds (lat 41–84, lon −142 "
            "to −52)."
        ),
    )
    async def location_resolve(
        address: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        dls: str | None = None,
        city: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Resolve exactly one of address, GPS, or DLS to a canonical location.

        Args:
            address: Street address (exactly one of address, lat+lon, or dls).
            lat: Latitude (with lon).
            lon: Longitude (with lat).
            dls: DLS legal land description.
            city: Optional city slug (e.g. calgary, quebec-city).
        """
        body: dict[str, Any] = {}
        addr = nonempty_term(address)
        dls_value = nonempty_term(dls)
        city_slug = nonempty_term(city)
        has_coords = lat is not None or lon is not None
        has_addr = bool(addr)
        has_dls = bool(dls_value)
        provided = sum((has_coords, has_addr, has_dls))
        if provided == 0:
            return (
                "Error: provide exactly one of address, lat+lon, or dls "
                "(LocationRequest; do not send q)."
            )
        if provided > 1:
            return (
                "Error: provide exactly one of address, lat+lon, or dls "
                "(not a combination)."
            )

        if has_coords:
            gps_error = canadian_gps_error(lat, lon)
            if gps_error:
                return gps_error
            body["coordinates"] = {"lat": lat, "lon": lon}
        if has_addr:
            if len(addr) < 3:
                return "Error: address must be at least 3 characters."
            body["address"] = addr
        if has_dls:
            if len(dls_value) < 5:
                return "Error: dls must be at least 5 characters."
            body["dls"] = dls_value
        if city_slug:
            body["city"] = city_slug

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.post(
                "/api/v2/locations/resolve", json=body, api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found="No location could be resolved for the given input.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Location"]
        location = data.get("location")
        if isinstance(location, dict):
            lines.extend(_format_mapping(location))
        quality = data.get("quality")
        if isinstance(quality, dict):
            lines.append(f"Quality: {quality.get('status', 'N/A')}")
            methods = quality.get("methods")
            if methods:
                lines.append(f"Methods: {', '.join(str(m) for m in methods)}")
        provenance = data.get("provenance")
        if isinstance(provenance, dict) and provenance:
            lines.append("Provenance:")
            lines.extend(f"- {k}: {v}" for k, v in provenance.items())
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="location_context",
        description=(
            "Datasets near a GPS point via GET /api/v2/locations/context. "
            "This call fans out and may consume several upstream API queries "
            "/ rate-limit units. Lat/lon must be within Canadian bounds "
            "(lat 41–84, lon −142 to −52). Optional city slug and radius_m "
            "(default 1000, max 50000)."
        ),
    )
    async def location_context(
        lat: float = None,
        lon: float = None,
        city: str | None = None,
        radius_m: int = 1000,
        ctx: Context = None,
    ) -> str:
        """Get datasets near a GPS point.

        Args:
            lat: Latitude (Canadian bounds).
            lon: Longitude (Canadian bounds).
            city: Optional city slug.
            radius_m: Search radius in metres (1-50000, default 1000).
        """
        gps_error = canadian_gps_error(lat, lon)
        if gps_error:
            return gps_error

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params: dict[str, Any] = {
            "lat": lat,
            "lon": lon,
            "radius_m": clamp_limit(radius_m, maximum=50000),
        }
        city_slug = nonempty_term(city)
        if city_slug:
            params["city"] = city_slug

        try:
            data = await client.get(
                "/api/v2/locations/context",
                params=params,
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No location context found near GPS {lat}, {lon}.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Location context"]
        lines.append(
            "Note: this endpoint may consume several upstream API calls."
        )
        lines.extend(_format_mapping(data))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
