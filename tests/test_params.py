"""Tests for shared Canadian GPS bounds and limit clamping."""

from clevertech_mcp.params import (
    CANADA_LON_MAX,
    canadian_gps_error,
    clamp_limit,
    clamp_radius_km,
    parse_positive_int,
    split_ids,
)

# Official st-johns centre from v1 cities.json.
ST_JOHNS_LAT = 47.5615
ST_JOHNS_LON = -52.7126
CAPE_SPEAR_LAT = 47.52
CAPE_SPEAR_LON = -52.62


class TestStJohnsEastBound:
    """Lock the shared east longitude so Newfoundland stays inside Canada."""

    def test_st_johns_centre_is_inside_east_bound(self):
        assert CANADA_LON_MAX == -52.0
        assert canadian_gps_error(ST_JOHNS_LAT, ST_JOHNS_LON) is None

    def test_cape_spear_is_inside_east_bound(self):
        assert canadian_gps_error(CAPE_SPEAR_LAT, CAPE_SPEAR_LON) is None

    def test_east_bound_inclusive_at_minus_52(self):
        assert canadian_gps_error(ST_JOHNS_LAT, -52.0) is None

    def test_east_of_newfoundland_is_rejected(self):
        err = canadian_gps_error(ST_JOHNS_LAT, -51.9)
        assert err is not None
        assert "Canadian bounds" in err
        assert "−52" in err or "-52" in err


class TestClampLimit:
    def test_floor_is_one(self):
        assert clamp_limit(0, maximum=100) == 1
        assert clamp_limit(-5, maximum=100) == 1

    def test_cap_at_maximum(self):
        assert clamp_limit(500, maximum=100) == 100


class TestClampRadiusKm:
    def test_matches_upstream_telecom_range(self):
        assert clamp_radius_km(0.1) == 0.1
        assert clamp_radius_km(100) == 100.0
        assert clamp_radius_km(200) == 100.0
        assert clamp_radius_km(0.05) == 0.1


class TestParsePositiveInt:
    def test_parses_digits(self):
        value, err = parse_positive_int("42", label="corporation_id")
        assert value == 42
        assert err is None

    def test_rejects_non_integer(self):
        value, err = parse_positive_int("abc", label="corporation_id")
        assert value is None
        assert "must be an integer" in err


class TestSplitIds:
    def test_comma_string_and_list(self):
        assert split_ids("a, b,") == ["a", "b"]
        assert split_ids(["x", " y "]) == ["x", "y"]
