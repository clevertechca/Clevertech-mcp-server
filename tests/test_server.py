"""Tests for server.py — entry point and server creation.

Validates that ``create_server`` returns a FastMCP instance and that
the ``main`` entry point can be invoked without crashing.
"""

import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------

class TestCreateServer:
    """Tests for ``create_server``."""

    def test_create_server_returns_fastmcp(self):
        """create_server(config) builds and returns a FastMCP instance."""
        # We mock the dependencies that do actual HTTP / tool wiring
        # so the test stays fast and offline.
        with (
            patch("clevertech_mcp.server.CleverTechClient") as mock_client_cls,
            patch("clevertech_mcp.server.register_all_tools") as mock_register,
        ):
            from clevertech_mcp.server import create_server

            config = {
                "api_url": "https://test-api.example.com",
                "api_key": "test-key-123",
            }

            mcp = create_server(config)

            # Verify CleverTechClient was constructed with correct args
            mock_client_cls.assert_called_once_with(
                base_url="https://test-api.example.com",
                api_key="test-key-123",
            )

            # Verify tools were registered (with rate_limiter as 4th arg)
            mock_register.assert_called_once()
            call_args = mock_register.call_args
            assert call_args[0][0] is mcp
            assert call_args[0][1] is mock_client_cls.return_value
            assert call_args[0][2] == config
            assert hasattr(call_args[0][3], "check_or_raise")  # rate_limiter

            # Verify we got back a FastMCP instance
            # (the actual class, not a mock, since we only mock its deps)
            from mcp.server.fastmcp import FastMCP
            assert isinstance(mcp, FastMCP)
            assert mcp.name == "clevertech-mcp"  # type: ignore[attr-defined]

    def test_create_server_imports_fastmcp_and_lists_tools(self):
        """Smoke: FastMCP still imports from mcp.server.fastmcp and tools are registered."""
        from mcp.server.fastmcp import FastMCP

        from clevertech_mcp.server import create_server

        mcp = create_server({
            "api_url": "https://test-api.example.com",
            "api_key": "test-key-123",
        })
        assert isinstance(mcp, FastMCP)

        tools = mcp._tool_manager.list_tools()
        names = {t.name for t in tools}
        assert "business_registry_search" in names
        assert "property_search" in names
        assert "list_cities" in names
        assert "census_lookup_by_gps" in names
        assert "census_profile" in names
        assert "census_stats" in names
        assert "census_lookup_by_dls" in names
        assert "safety_nearby" in names
        assert "safety_search" in names
        assert "safety_stats" in names
        assert "safety_by_id" in names
        assert "safety_summary" in names
        assert "telecom_towers_nearby" in names
        assert "telecom_towers_search" in names
        assert "telecom_stats" in names
        assert "microwave_nearby" in names
        assert "microwave_search" in names
        assert "microwave_stats" in names
        assert "microwave_by_authorization" in names
        assert "business_registry_get" in names
        assert "business_registry_advanced" in names
        assert "business_registry_stats" in names
        assert "location_resolve" in names
        assert "location_context" in names
        assert "property_nearby" in names
        assert "property_stats" in names
        assert "property_batch" in names
        assert "zoning_codes" in names
        assert "zoning_by_code" in names
        assert "building_permit_nearby" in names
        assert "building_permit_get" in names
        assert "building_permit_stats" in names
        assert "building_permit_batch" in names
        assert len(names) == 41

        biz = next(t for t in tools if t.name == "business_registry_search")
        schema = biz.parameters
        props = schema.get("properties", schema)
        assert "q" in props
        assert "query" in props
        description = getattr(biz, "description", "") or ""
        assert "query" in description.lower()
        assert "alias" in description.lower() or "q wins" in description.lower()

    def test_create_server_no_api_key(self):
        """create_server works without an API key (anonymous mode)."""
        with (
            patch("clevertech_mcp.server.CleverTechClient") as mock_client_cls,
            patch("clevertech_mcp.server.register_all_tools"),
        ):
            from clevertech_mcp.server import create_server

            mcp = create_server({"api_url": "https://clevertech.ca"})

            mock_client_cls.assert_called_once_with(
                base_url="https://clevertech.ca",
                api_key=None,
            )
            assert mcp is not None


# ---------------------------------------------------------------------------
# main (CLI entry point)
# ---------------------------------------------------------------------------

class TestMain:
    """Smoke tests for the ``main`` CLI entry point."""

    def test_main_importable(self):
        """The main function can be imported without side effects."""
        from clevertech_mcp.server import main
        assert callable(main)

    def test_main_help_flag(self, capsys):
        """--help prints usage and exits cleanly."""
        with patch("sys.argv", ["clevertech-mcp-server", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                from clevertech_mcp.server import main
                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "CleverTech MCP Server" in captured.out
        assert "--transport" in captured.out
        assert "--host" in captured.out
        assert "--port" in captured.out


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------


class TestLandingPage:
    """Tests for the root landing page."""

    def test_root_returns_html(self):
        """GET / returns 200 with text/html content type."""
        from starlette.testclient import TestClient
        from starlette.routing import Route
        from clevertech_mcp.server import create_server, root_endpoint

        config = {"api_url": "https://test-api.example.com"}
        with (
            patch("clevertech_mcp.server.CleverTechClient"),
            patch("clevertech_mcp.server.register_all_tools"),
        ):
            mcp = create_server(config)
            sse_app = mcp.sse_app()
            # Register / route — same pattern as main()
            sse_app.router.routes.insert(0, Route("/", endpoint=root_endpoint))

            with TestClient(sse_app) as client:
                response = client.get("/")
                assert response.status_code == 200
                content_type = response.headers.get("content-type", "")
                assert "text/html" in content_type
                assert "CleverTech MCP Server" in response.text
