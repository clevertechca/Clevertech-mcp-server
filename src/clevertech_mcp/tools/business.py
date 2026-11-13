"""Business registry MCP tools."""

import httpx
from mcp.server.fastmcp import FastMCP, Context
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import _get_user_api_key, get_upstream_key, is_authenticated, _extract_client_ip
from clevertech_mcp.http_errors import tool_http_error
from clevertech_mcp.params import clamp_limit, nonempty_term, parse_positive_int


def _format_corporation(r: dict) -> list[str]:
    lines = [
        "",
        "---",
        f"Name: {r.get('corporation_name', r.get('name', 'N/A'))}",
        f"Number: {r.get('corporation_number', r.get('number', 'N/A'))}",
        f"Status: {r.get('status', 'N/A')}",
        f"Jurisdiction: {r.get('jurisdiction', r.get('province', 'N/A'))}",
    ]
    if r.get("registered_address"):
        lines.append(f"Address: {r['registered_address']}")
    corp_id = r.get("corporation_id", r.get("id"))
    if corp_id is not None:
        lines.append(f"Id: {corp_id}")
    return lines


def register_business_tools(mcp: FastMCP, client: CleverTechClient, config: dict, rate_limiter: LocalRateLimiter):
    """Register business registry tools."""

    @mcp.tool(
        name="business_registry_search",
        description=(
            "Search the Canadian federal business registry. Find corporations by name, "
            "province, city, status, or industry act. Pass the search term as `q` "
            "(preferred) or `query` (alias). If both are given, `q` wins. Empty or "
            "whitespace-only `q` is treated as missing so `query` is used."
        ),
    )
    async def business_registry_search(
        q: str | None = None,
        query: str | None = None,
        province: str = None,
        city: str = None,
        status: str = None,
        limit: int = 25,
        ctx: Context = None,
    ) -> str:
        """Search the business registry.

        Args:
            q: Corporation name or keyword (preferred). Wins if both q and query are non-empty.
            query: Alias for q. Used when q is omitted, empty, or whitespace-only.
            province: Two-letter province code (AB, BC, ON, QC, etc.)
            city: City name
            status: Corporation status (Active, Dissolved, etc.)
            limit: Max results (1-100, default 25)
        """
        search = nonempty_term(q) or nonempty_term(query)
        if search is None:
            return "Error: provide q or query (corporation name or keyword). If both are given, q wins."

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {"q": search, "limit": clamp_limit(limit, maximum=100)}
        if province:
            params["province"] = province
        if city:
            params["city"] = city
        if status:
            params["status"] = status

        try:
            data = await client.get("/api/registry/search", params=params, api_key=upstream_key)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No corporations found for {search!r}.",
            )

        results = data.get("results", [])
        total = data.get("total", len(results))
        message = data.get("_message", "")

        lines = [f"Found {len(results)} of {total} corporations"]
        if message:
            lines.append(f"\n{message}")
        for r in results:
            lines.extend(_format_corporation(r))
        return "\n".join(lines)

    @mcp.tool(
        name="business_registry_get",
        description=(
            "Get one Canadian federal corporation by id. Pass the id as "
            "`corporation_id` (preferred), `q`, or `query`. If more than one is "
            "given, corporation_id wins, then q."
        ),
    )
    async def business_registry_get(
        corporation_id: str | None = None,
        q: str | None = None,
        query: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Get a corporation by id.

        Args:
            corporation_id: Corporation id (preferred).
            q: Alias for corporation_id.
            query: Alias for corporation_id / q.
        """
        raw_id = (
            nonempty_term(corporation_id)
            or nonempty_term(q)
            or nonempty_term(query)
        )
        if raw_id is None:
            return (
                "Error: provide corporation_id (preferred), q, or query. "
                "If more than one is given, corporation_id wins, then q."
            )
        corp_id, id_error = parse_positive_int(raw_id, label="corporation_id")
        if id_error:
            return id_error

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get(
                f"/api/registry/corporation/{corp_id}", api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=f"No corporation found for id {corp_id}.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Corporation"]
        lines.extend(_format_corporation(data))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="business_registry_advanced",
        description=(
            "Faceted search of the Canadian federal business registry. Same "
            "filters as business_registry_search (optional q/query, province, "
            "city, status) plus `act` and `corporation_type`. `q` is optional "
            "so facet-only searches are valid. If both q and query are given, "
            "`q` wins."
        ),
    )
    async def business_registry_advanced(
        q: str | None = None,
        query: str | None = None,
        province: str = None,
        city: str = None,
        status: str = None,
        act: str = None,
        corporation_type: str = None,
        limit: int = 50,
        ctx: Context = None,
    ) -> str:
        """Advanced / faceted corporation search.

        Args:
            q: Corporation name or keyword (optional).
            query: Alias for q.
            province: Two-letter province code.
            city: City name.
            status: Corporation status.
            act: Industry / incorporating act filter.
            corporation_type: Corporation type facet.
            limit: Max results (1-500, default 50).
        """
        search = nonempty_term(q) or nonempty_term(query)

        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        params = {"limit": clamp_limit(limit, maximum=500)}
        if search:
            params["q"] = search
        if province:
            params["province"] = province
        if city:
            params["city"] = city
        if status:
            params["status"] = status
        if act:
            params["act"] = act
        if corporation_type:
            params["corporation_type"] = corporation_type

        try:
            data = await client.get(
                "/api/registry/advanced", params=params, api_key=upstream_key
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found=(
                    f"No corporations found for {search!r}."
                    if search
                    else "No corporations found."
                ),
            )

        results = data.get("results", data.get("corporations", []))
        total = data.get("total", len(results))
        facets = data.get("facets", data.get("aggregations", {}))
        lines = [f"Found {len(results)} of {total} corporations"]
        if isinstance(facets, dict) and facets:
            lines.append("Facets:")
            for key, value in facets.items():
                lines.append(f"- {key}: {value}")
        for r in results:
            lines.extend(_format_corporation(r))
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)

    @mcp.tool(
        name="business_registry_stats",
        description=(
            "Get aggregate federal corporation statistics (totals and counts "
            "by province)."
        ),
    )
    async def business_registry_stats(ctx: Context = None) -> str:
        """Get business registry aggregate stats."""
        user_key = _get_user_api_key(ctx)
        upstream_key = get_upstream_key(user_key, config.get("api_key"))
        if not is_authenticated(user_key):
            source_ip = _extract_client_ip(ctx)
            rate_limiter.check_or_raise(source_ip)

        try:
            data = await client.get("/api/registry/stats", api_key=upstream_key)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            return tool_http_error(
                exc,
                not_found="No business registry stats are available.",
            )

        if not isinstance(data, dict):
            return str(data)
        lines = ["# Business registry stats"]
        total = data.get("total_corporations", data.get("total"))
        if total is not None:
            lines.append(f"Total corporations: {total}")
        by_province = data.get("by_province", data.get("provinces", {}))
        if isinstance(by_province, dict) and by_province:
            lines.append("By province:")
            for key, value in by_province.items():
                lines.append(f"- {key}: {value}")
        for key, value in data.items():
            if key in (
                "total_corporations",
                "total",
                "by_province",
                "provinces",
                "_message",
            ):
                continue
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for inner_key, inner_value in value.items():
                    lines.append(f"- {inner_key}: {inner_value}")
            else:
                lines.append(f"{key}: {value}")
        if data.get("_message"):
            lines.append(f"\n{data['_message']}")
        return "\n".join(lines)
