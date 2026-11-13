"""Shared parameter helpers for MCP tools.

Canadian GPS bounds match the documented safety nearby query schema
(lat 41–84, lon −142 to −52). Limit clamping uses a floor of 1.
"""

# Upstream safety/nearby OpenAPI bounds (Canadian latitude / longitude).
CANADA_LAT_MIN = 41.0
CANADA_LAT_MAX = 84.0
CANADA_LON_MIN = -142.0
CANADA_LON_MAX = -52.0


def nonempty_term(value: str | None) -> str | None:
    """Return a stripped term, or None if missing/blank."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def clamp_limit(limit: int, *, maximum: int) -> int:
    """Clamp *limit* to ``[1, maximum]``. Zero and negatives become 1."""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return 1
    return max(1, min(n, maximum))


def clamp_radius_km(
    radius_km: float,
    *,
    minimum: float = 0.1,
    maximum: float = 100.0,
    default: float = 5.0,
) -> float:
    """Clamp a kilometre radius to the upstream telecom nearby range."""
    try:
        n = float(radius_km)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(n, maximum))


def split_ids(value: str | list | tuple | None) -> list[str]:
    """Split a comma-separated string or list into stripped non-empty ids."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value).split(",")
    out: list[str] = []
    for item in items:
        term = nonempty_term(str(item)) if item is not None else None
        if term:
            out.append(term)
    return out


def parse_positive_int(value: str | None, *, label: str) -> tuple[int | None, str | None]:
    """Parse a required positive integer id. Returns (n, None) or (None, error)."""
    term = nonempty_term(value) if isinstance(value, str) or value is None else nonempty_term(str(value))
    if term is None:
        return None, f"Error: provide {label}."
    if not term.isdigit():
        return None, f"Error: {label} must be an integer."
    return int(term), None


def canadian_gps_error(lat: float | None, lon: float | None) -> str | None:
    """Return an error string if lat/lon are missing or outside Canada.

    Used by census, zoning, safety, telecom, microwave, location, and property GPS tools.
    """
    if lat is None or lon is None:
        return "Error: lat and lon are required."
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return "Error: lat and lon must be numbers."
    in_lat = CANADA_LAT_MIN <= lat_f <= CANADA_LAT_MAX
    in_lon = CANADA_LON_MIN <= lon_f <= CANADA_LON_MAX
    if in_lat and in_lon:
        return None
    return (
        "Error: lat and lon must be within Canadian bounds "
        f"(lat {CANADA_LAT_MIN:g}–{CANADA_LAT_MAX:g}, "
        f"lon {CANADA_LON_MIN:g}–{CANADA_LON_MAX:g})."
    )
