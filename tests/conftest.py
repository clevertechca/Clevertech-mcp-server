"""Test fixtures for CleverTech MCP Server.

Provides shared fixtures for all test modules including:
- Mock CleverTechClient with AsyncMock get/post
- Mock FastMCP that captures registered tool functions
- Sample response data for properties, permits, DLS, zoning, etc.
- A helper to register tools and extract the inner async function.

Usage in test files:
    from tests.conftest import register_and_get_tool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Mock MCP class — captures tool functions registered via @mcp.tool()
# ---------------------------------------------------------------------------

class MockMCP:
    """A lightweight stand-in for ``mcp.server.fastmcp.FastMCP`` that
    captures tool functions registered with ``@mcp.tool()`` into a
    dictionary so tests can call them directly without a running server."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None, description: str | None = None):
        """Decorator that registers the function and returns it unchanged."""
        def decorator(fn):
            key = name if name else fn.__name__
            self.tools[key] = fn
            return fn
        return decorator


# ---------------------------------------------------------------------------
# Shared helper — wire up a tool module and return the captured function
# ---------------------------------------------------------------------------

def register_and_get_tool(
    register_fn,
    mock_client,
    mock_config,
    tool_name: str,
    mock_rate_limiter=None,
):
    """Call *register_fn* with a MockMCP, capture tool functions, and return
    the one named *tool_name*.

    Example::

        tool = register_and_get_tool(register_dls_tools, client, cfg, "dls_convert")
        result = await tool(direction="gps_to_dls", lat=51.0, lon=-114.0)
    """
    mcp = MockMCP()
    if mock_rate_limiter is None:
        mock_rate_limiter = MagicMock()
    register_fn(mcp, mock_client, mock_config, mock_rate_limiter)
    fn = mcp.tools.get(tool_name)
    if fn is None:
        available = list(mcp.tools.keys())
        raise KeyError(
            f"Tool '{tool_name}' not found. Available: {available}"
        )
    return fn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_clevertech_api_key(monkeypatch):
    """Keep tests independent of a developer machine's CLEVERTECH_API_KEY.

    Several tools assert ``api_key=None`` on the mocked client. If the env var
    is set, ``_get_user_api_key`` treats it as a user key and those assertions
    fail. Tests that need the var set it themselves with ``patch.dict``.
    """
    monkeypatch.delenv("CLEVERTECH_API_KEY", raising=False)


@pytest.fixture
def mock_client():
    """Create a mock CleverTechClient with AsyncMock get/post methods."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_config():
    """Default config dict used across tests (matches load_config output)."""
    return {
        "api_url": "https://clevertech.ca",
        "api_key": None,
        "port": 8001,
        "transport": "stdio",
        "log_level": "INFO",
        "rate_limit_anon_daily": 50,
        "rate_limit_anon_burst": 10,
        "sentry_dsn": None,
    }


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_property():
    """Sample property assessment data returned by the API."""
    return {
        "roll_number": "1234567",
        "address": "123 Main St",
        "assessed_value": 500000,
        "land_value": 200000,
        "improvement_value": 300000,
        "property_type": "Residential",
        "year_built": 1990,
        "lot_size_sqm": 500,
        "dls": "NW-16-24-1-W5",
    }


@pytest.fixture
def sample_permit():
    """Sample building permit data returned by the API."""
    return {
        "permit_number": "BP-2024-001",
        "permit_type": "Building",
        "status": "Issued",
        "address": "456 Oak Ave",
        "applicant": "John Smith",
        "job_value": 250000,
        "issued_date": "2024-01-15",
    }


@pytest.fixture
def sample_dls_result():
    """Sample GPS→DLS conversion result."""
    return {
        "dls": "NW-16-24-1-W5",
        "province": "AB",
        "lat": 51.0447,
        "lon": -114.0719,
        "confidence": "exact",
        "distance_km": 0.35,
    }


@pytest.fixture
def sample_gps_result():
    """Sample DLS→GPS conversion result."""
    return {
        "lat": 51.0447,
        "lon": -114.0719,
        "province": "AB",
        "dls": "NW-16-24-1-W5",
        "confidence": "exact",
    }


@pytest.fixture
def sample_zoning():
    """Sample zoning lookup result."""
    return {
        "zone_code": "R-CG",
        "description": "Residential — Contextual Grade-Oriented",
        "district_name": "Beltline",
        "land_use": "Residential Multi-Family",
        "boundaries": {"type": "Polygon", "coordinates": [[[-114.07, 51.04], [-114.06, 51.04], [-114.06, 51.05], [-114.07, 51.05], [-114.07, 51.04]]]},
    }


@pytest.fixture
def sample_business():
    """Sample business registry result."""
    return {
        "corporation_name": "ACME CANADA INC.",
        "corporation_number": "123456-7",
        "status": "Active",
        "jurisdiction": "AB",
        "registered_address": "100 Business Park, Calgary AB T2P 1A1",
    }


@pytest.fixture
def sample_census_profile():
    """Sample CensusProfile returned by /census/profile or nested in by-gps."""
    return {
        "da_id": "48060645",
        "census_year": 2021,
        "geography_name": "Calgary",
        "geography_type": "DA",
        "population": 1027,
        "households": 480,
        "avg_income": 52000,
        "median_age": 30.4,
        "median_income": 44400,
        "dwelling_count": 510,
        "data": {"density": 4200.5, "household_size": 2.1},
    }


@pytest.fixture
def sample_census_by_gps(sample_census_profile):
    """Sample CensusByDLSResponse from /census/by-gps."""
    return {
        "dls": None,
        "lat": 51.045,
        "lon": -114.072,
        "da_id": "48060645",
        "ct_id": "8250001.00",
        "cma_id": "825",
        "profile": sample_census_profile,
        "matched_by": "point_in_polygon",
        "distance_km": 0.0,
    }


@pytest.fixture
def sample_census_by_dls(sample_census_profile):
    """Sample CensusByDLSResponse from /census/by-dls."""
    return {
        "dls": "NW-16-24-1-W5",
        "lat": 51.0447,
        "lon": -114.0719,
        "da_id": "48060645",
        "profile": sample_census_profile,
        "matched_by": "exact_dls",
        "distance_km": 0.12,
    }


@pytest.fixture
def sample_safety_incident():
    """Sample SafetyInvolvedPerson row (Toronto live-check style id)."""
    return {
        "source_record_id": "toronto_shootings:GO-2004195761",
        "source_family": "toronto_shootings",
        "category": "shooting",
        "injury": "none",
        "neighbourhood": "Yonge-St. Clair",
        "street_label": "Yonge St",
        "occurred_at": "2004-01-15T00:00:00",
        "road_user": None,
        "lat": 43.7141,
        "lon": -79.3895,
        "city_slug": "toronto",
    }


@pytest.fixture
def sample_tower():
    """Sample ISED tower row."""
    return {
        "tower_id": "T-1001",
        "carrier": "Rogers",
        "client_name": "Rogers Communications",
        "city": "Calgary",
        "province": "AB",
        "technology": "5G",
        "height_meters": 45.0,
        "latitude": 51.045,
        "longitude": -114.072,
        "address": "308 4 AV SW",
    }


@pytest.fixture
def sample_microwave_link():
    """Sample ISED microwave link / authorization row."""
    return {
        "authorization_number": "0002315559",
        "licensee": "TELUS",
        "frequency_band": "11 GHz",
        "province": "AB",
        "distance_km": 1.2,
    }


@pytest.fixture
def sample_safety_stats():
    """Sample /safety/stats payload."""
    return {
        "total_rows": 12840,
        "distinct_collisions": 4100,
        "by_injury": {"none": 9000, "minor": 3000, "fatal": 40},
        "by_category": {"collision": 12000, "shooting": 840},
    }


@pytest.fixture
def sample_census_stats():
    """Sample /census/stats payload."""
    return {
        "total_profiles": 3919,
        "census_years": [2016, 2021],
        "by_geography_type": {"DA": 3800, "CT": 119},
    }


@pytest.fixture
def sample_property_report():
    """Full property report response including assessment, permits, and zoning."""
    return {
        "address": "123 Main St",
        "roll_number": "1234567",
        "dls": "NW-16-24-1-W5",
        "generated_at": "2024-06-08T12:00:00Z",
        "property": {
            "assessed_value": 500000,
            "land_value": 200000,
            "improvement_value": 300000,
            "property_type": "Residential",
            "year_built": 1990,
            "lot_size_sqm": 500,
        },
        "permits": [
            {"permit_number": "BP-2024-001", "permit_type": "Building", "job_value": 250000},
            {"permit_number": "BP-2023-045", "permit_type": "Electrical", "job_value": 15000},
        ],
        "zoning": {
            "zone_code": "R-CG",
            "description": "Residential — Contextual Grade-Oriented",
        },
        "_message": "Report generated from live data.",
    }
