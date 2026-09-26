"""Shared MCP parameter descriptions (JSON Schema) for CleverTech tools.

FastMCP exposes Pydantic ``Field(description=...)`` text to MCP clients;
docstring Args sections are not included in the tool input schema.
"""

# Meta / property / permits / zoning
CITY_SLUG = (
    "Lowercase city slug for API routes (not the display name). "
    "Required on all city-scoped tools. Call list_cities for the live list "
    "(e.g. calgary, edmonton, toronto, vancouver, montreal)."
)

ROLL_NUMBER = (
    "Municipal assessment roll number (parcel ID). "
    "Copy from property_search, property_top, or reverse_geocode output; "
    "format varies by city (often numeric, sometimes with prefixes)."
)

# DLS
DLS_DIRECTION = (
    "Conversion mode. Use exactly 'gps_to_dls' to convert WGS84 latitude/longitude "
    "to a Dominion Land Survey (DLS) string, or 'dls_to_gps' to convert a DLS string "
    "to latitude/longitude. Western Canada only (Alberta, Saskatchewan, Manitoba). "
    "dls_batch rejects any other value."
)

DLS_LAT = (
    "Latitude in decimal degrees (WGS84). Required when direction is 'gps_to_dls'. "
    "Example: 51.0447 for Calgary."
)

DLS_LON = (
    "Longitude in decimal degrees (WGS84). Required when direction is 'gps_to_dls'. "
    "Example: -114.0719 for Calgary."
)

DLS_STRING = (
    "Dominion Land Survey (DLS) location string. Required when direction is 'dls_to_gps'. "
    "Examples: 'NW-16-24-1-W5', '12-34-5-W4'. Include quarter/legal subdivision when known."
)

DLS_PROVINCE = (
    "Optional two-letter province code to disambiguate the grid: AB, SK, or MB. "
    "Omit to let the service auto-detect from coordinates or the DLS meridian."
)

DLS_BATCH_ITEMS = (
    "List of per-row inputs (max 100). For direction 'gps_to_dls', each item must include "
    "'lat' and 'lon' (optional per-item 'province'). For 'dls_to_gps', each item must "
    "include 'dls_string' (alias 'dls' also accepted). Prefer dls_convert for a single row."
)
