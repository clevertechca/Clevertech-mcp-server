"""Census MCP tools.

Wraps the four documented city census endpoints: by-gps, profile, stats,
and by-dls. City slugs match list_cities (hyphenated, e.g. calgary,
quebec-city).
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
from clevertech_mcp.params import canadian_gps_error, nonempty_term


def _format_count(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    return str(value)


def _format_money(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _format_profile(profile: dict) -> list[str]:
    """Format a CensusProfile (or similar dict) as display lines."""
    geo_name = profile.get("geography_name", "N/A")
    geo_type = profile.get("geography_type", "N/A")
    lines = [
        f"DA: {profile.get('da_id', 'N/A')}",
        f"Year: {profile.get('census_year', 'N/A')}",
        f"Geography: {geo_name} ({geo_type})",
        f"Population: {_format_count(profile.get('population'))}",
        f"Households: {_format_count(profile.get('households'))}",
        f"Median age: {profile.get('median_age', 'N/A')}",
        f"Median income: {_format_money(profile.get('median_income'))}",
    ]
    if profile.get("avg_income") is not None:
        lines.append(f"Average income: {_format_money(profile.get('avg_income'))}")
    if profile.get("dwelling_count") is not None:
        lines.append(f"Dwellings: {_format_count(profile.get('dwelling_count'))}")
    extra = profile.get("data") or {}
    if isinstance(extra, dict):
        if extra.get("density") is not None:
            lines.append(f"Density: {extra['density']}")
        if extra.get("household_size") is not None:
            lines.append(f"Household size: {extra['household_size']}")
    return lines


def _profile_from_lookup(data: dict) -> dict:
    """Unwrap CensusByDLSResponse.profile, else treat data as the profile."""
    nested = data.get("profile")
    if isinstance(nested, dict):
        return nested
    return data


def register_census_tools(
    mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter
) -> None:
    """Register census lookup, profile, stats, and DLS tools."""

    @mcp.tool(
        name="census_lookup_by_gps",
        description=(
            "Look up the Statistics Canada census profile for a GPS point in a "
            "Canadian city. Returns dissemination-area (DA) id, census year, "
            "population, median age, and income. Use a city slug from list_cities "
            "(e.g. calgary, quebec-city)."
        ),
    )
    async def census_lookup_by_gps(
        city: str,
        lat: float = None,
        lon: float = None,
        ctx: Context = None,
    ) -> str:
        """Get a census profile at a GPS point.

        Args:
            city: City slug (calgary, toronto, quebec-city, etc.).
            lat: Latitude.
            lon: Longitude.
        """
        gps_error = canadian_gps_error(lat, lon)
        if gps_error:
            return gps_error

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/census/by-gps",
                params={"lat": lat, "lon": lon},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=(
                    f"No census profile found for GPS {lat}, {lon} in {city}."
                ),
            )

        lines: list[str] = ["# Census (by GPS)"]
        if data.get("dls"):
            lines.append(f"DLS: {data['dls']}")
        if "lat" in data and "lon" in data:
            lines.append(f"GPS: {data['lat']}, {data['lon']}")
        if data.get("matched_by"):
            lines.append(f"Matched by: {data['matched_by']}")
        if data.get("distance_km") is not None:
            lines.append(f"Distance: {data['distance_km']} km")
        lines.append("")
        lines.extend(_format_profile(_profile_from_lookup(data)))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="census_profile",
        description=(
            "Get a Statistics Canada census profile by dissemination-area (DA) "
            "id, or a CSD-style id such as CSD_4806016. Requires a city slug "
            "from list_cities (e.g. calgary, quebec-city)."
        ),
    )
    async def census_profile(
        city: str,
        da_id: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a census profile by DA or CSD id.

        Args:
            city: City slug (calgary, toronto, quebec-city, etc.).
            da_id: Dissemination Area id (preferred). Wins if da_id, q, and
                   query are all non-empty. Accepts CSD-style ids like CSD_4806016.
            q: Alias for da_id. Used when da_id is omitted, empty, or whitespace-only.
               Wins over query when both q and query are given.
            query: Alias for da_id / q. Used when da_id and q are omitted, empty,
                   or whitespace-only.
        """
        identifier = (
            nonempty_term(da_id) or nonempty_term(q) or nonempty_term(query)
        )
        if identifier is None:
            return (
                "Error: provide da_id (preferred), q, or query. "
                "If more than one is given, da_id wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/census/profile",
                params={"da_id": identifier},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No census profile found for {identifier} in {city}.",
            )

        lines = ["# Census profile"]
        lines.extend(_format_profile(data if isinstance(data, dict) else {}))
        if isinstance(data, dict) and data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="census_stats",
        description=(
            "Get aggregate census statistics for a Canadian city: profile count, "
            "available census years, and counts by geography type. Use a city "
            "slug from list_cities (e.g. calgary, quebec-city)."
        ),
    )
    async def census_stats(city: str, ctx: Context = None) -> str:
        """Get census aggregate stats for a city.

        Args:
            city: City slug (calgary, toronto, quebec-city, etc.).
        """
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(f"/api/{city}/census/stats", api_key=upstream_key)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No census stats found for {city}.",
            )

        total = data.get("total_profiles", data.get("total"))
        years = data.get("census_years", data.get("years", []))
        by_type = data.get(
            "by_geography_type",
            data.get("geography_types", data.get("by_type", {})),
        )

        lines = [
            "# Census stats",
            f"Total profiles: {_format_count(total)}",
        ]
        if years:
            if isinstance(years, list):
                lines.append(f"Census years: {', '.join(str(y) for y in years)}")
            else:
                lines.append(f"Census years: {years}")
        if isinstance(by_type, dict) and by_type:
            lines.append("By geography type:")
            for geo_type, count in by_type.items():
                lines.append(f"- {geo_type}: {_format_count(count)}")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="census_lookup_by_dls",
        description=(
            "Look up the Statistics Canada census profile for a Dominion Land "
            "Survey (DLS) legal land description. Coverage is thin (about 1,000 "
            "mapped parcels); a miss returns a clear not-found message. Pass the "
            "DLS string as `dls` (preferred), `q`, or `query`. If more than one "
            "is given, dls wins, then q. City slug from list_cities "
            "(e.g. calgary)."
        ),
    )
    async def census_lookup_by_dls(
        city: str,
        dls: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a census profile by DLS coordinates.

        Args:
            city: City slug (calgary, edmonton, etc.).
            dls: DLS coordinates QTR-SEC-TWP-RNG-MER (preferred). Wins if dls,
                 q, and query are all non-empty.
            q: Alias for dls. Used when dls is omitted, empty, or whitespace-only.
               Wins over query when both q and query are given.
            query: Alias for dls / q. Used when dls and q are omitted, empty,
                   or whitespace-only.
        """
        dls_value = nonempty_term(dls) or nonempty_term(q) or nonempty_term(query)
        if dls_value is None:
            return (
                "Error: provide dls (preferred), q, or query "
                "(DLS string such as NW-16-24-1-W5). If more than one is given, "
                "dls wins, then q."
            )

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/{city}/census/by-dls",
                params={"dls": dls_value},
                api_key=upstream_key,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=(
                    f"No census profile found for DLS {dls_value} in {city}. "
                    "The DLS-to-census map is small (about 1,000 parcels), so "
                    "many valid DLS strings have no mapped dissemination area. "
                    "Try census_lookup_by_gps with coordinates from dls_convert."
                ),
            )

        lines: list[str] = ["# Census (by DLS)"]
        lines.append(f"DLS: {data.get('dls', dls_value)}")
        if "lat" in data and "lon" in data:
            lines.append(f"GPS: {data['lat']}, {data['lon']}")
        if data.get("matched_by"):
            lines.append(f"Matched by: {data['matched_by']}")
        if data.get("distance_km") is not None:
            lines.append(f"Distance: {data['distance_km']} km")
        lines.append("")
        lines.extend(_format_profile(_profile_from_lookup(data)))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
