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
