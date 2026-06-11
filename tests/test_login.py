"""
Tests for the device authorization login flow (login.py).

Tests the device_code → polling → save/load round-trip using
mocked httpx.Client so no real network calls are made.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from clevertech_mcp.login import (
    _save_api_key,
    load_saved_api_key,
    device_login,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_config_dir(monkeypatch):
    """Redirect ~/.clevertech to a temporary directory for isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_dir = os.path.join(tmpdir, ".clevertech")
        cfg_file = os.path.join(cfg_dir, "config.json")
        monkeypatch.setattr(
            "clevertech_mcp.login.CONFIG_DIR", cfg_dir
        )
        monkeypatch.setattr(
            "clevertech_mcp.login.CONFIG_FILE", cfg_file
        )
        yield cfg_dir, cfg_file


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockResponse:
    """Duck-typed httpx.Response for mocking."""
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self,
            )


# ---------------------------------------------------------------------------
# Tests: _save_api_key / load_saved_api_key
# ---------------------------------------------------------------------------

class TestSaveLoadApiKey:
    """Round-trip: save a key, load it back."""

    def test_save_and_load(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        _save_api_key("ctk_test_key_123")
        assert os.path.exists(cfg_file)
        loaded = load_saved_api_key()
        assert loaded == "ctk_test_key_123"

    def test_load_when_no_file(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        # No file saved yet
        result = load_saved_api_key()
        assert result is None

    def test_save_overwrites_existing(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        _save_api_key("old_key")
        _save_api_key("new_key")
        assert load_saved_api_key() == "new_key"

    def test_save_preserves_other_keys(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        # Manually create a config with extra keys
        os.makedirs(cfg_dir, exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump({"api_key": "old_key", "other_setting": "value"}, f)
        _save_api_key("new_key")
        with open(cfg_file) as f:
            data = json.load(f)
        assert data["api_key"] == "new_key"
        assert data["other_setting"] == "value"

    def test_load_handles_corrupt_json(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        os.makedirs(cfg_dir, exist_ok=True)
        with open(cfg_file, "w") as f:
            f.write("not valid json{{{")
        result = load_saved_api_key()
        assert result is None

    def test_load_handles_non_dict_config(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        os.makedirs(cfg_dir, exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump(["list", "not", "dict"], f)
        result = load_saved_api_key()
        assert result is None

    def test_file_permissions(self, temp_config_dir):
        cfg_dir, cfg_file = temp_config_dir
        _save_api_key("ctk_permission_test")
        mode = os.stat(cfg_file).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# ---------------------------------------------------------------------------
# Tests: device_login flow (mocked httpx)
# ---------------------------------------------------------------------------

class TestDeviceLogin:
    """Test the full device_login flow with mocked HTTP responses."""

    def _make_client_mock(self, code_response, token_responses):
        """
        Build a mock for httpx.Client that returns *code_response* on the
        first POST (device/code) and a sequence of *token_responses* on
        subsequent POSTs (device/token).
        """
        token_iter = iter(token_responses)

        class MockClient:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def post(self, url, json=None, **kwargs):
                if "/device/code" in url:
                    return MockResponse(**code_response)
                elif "/device/token" in url:
                    try:
                        resp = next(token_iter)
                    except StopIteration:
                        return MockResponse(
                            status_code=400,
                            json_data={"error": "expired_token"},
                        )
                    return MockResponse(**resp)
                return MockResponse(status_code=404, json_data={"error": "not_found"})

        return MockClient

    def test_successful_flow(self, temp_config_dir, monkeypatch):
        """Full happy path: get code, poll once with success."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_abc123",
                "user_code": "ABCD-EFGH",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=ABCD-EFGH",
                "expires_in": 900,
                "interval": 0,  # zero so we don't actually sleep in tests
            },
        }
        token_resps = [
            {"status_code": 200, "json_data": {"access_token": "ctk_real_key_xyz", "token_type": "bearer"}},
        ]

        MockClient = self._make_client_mock(code_resp, token_resps)
        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", MockClient)
        # Make time.sleep a no-op
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)

        result = device_login(base_url="https://clevertech.ca")
        assert result == "ctk_real_key_xyz"
        # Verify key was saved
        assert load_saved_api_key() == "ctk_real_key_xyz"

    def test_polling_authorization_pending_then_success(self, temp_config_dir, monkeypatch):
        """First poll returns authorization_pending, second returns success."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_pending",
                "user_code": "WXYZ-1234",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=WXYZ-1234",
                "expires_in": 900,
                "interval": 0,
            },
        }
        token_resps = [
            {"status_code": 400, "json_data": {"error": "authorization_pending"}},
            {"status_code": 200, "json_data": {"access_token": "ctk_pending_success", "token_type": "bearer"}},
        ]

        MockClient = self._make_client_mock(code_resp, token_resps)
        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", MockClient)
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)

        result = device_login(base_url="https://clevertech.ca")
        assert result == "ctk_pending_success"
        assert load_saved_api_key() == "ctk_pending_success"

    def test_access_denied(self, temp_config_dir, monkeypatch):
        """User denies the authorization request."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_denied",
                "user_code": "DENY-ME",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=DENY-ME",
                "expires_in": 900,
                "interval": 0,
            },
        }
        token_resps = [
            {"status_code": 400, "json_data": {"error": "access_denied"}},
        ]

        MockClient = self._make_client_mock(code_resp, token_resps)
        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", MockClient)
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)

        with pytest.raises(SystemExit) as exc_info:
            device_login(base_url="https://clevertech.ca")
        assert exc_info.value.code == 1

    def test_expired_token(self, temp_config_dir, monkeypatch):
        """Device code expires before user authorizes."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_expired",
                "user_code": "EXP-ME",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=EXP-ME",
                "expires_in": 1,  # very short expiry
                "interval": 0,
            },
        }
        token_resps = [
            {"status_code": 400, "json_data": {"error": "expired_token"}},
        ]

        MockClient = self._make_client_mock(code_resp, token_resps)
        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", MockClient)
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)

        with pytest.raises(SystemExit) as exc_info:
            device_login(base_url="https://clevertech.ca")
        assert exc_info.value.code == 1

    def test_timeout_waiting(self, temp_config_dir, monkeypatch):
        """Deadline passes while still receiving authorization_pending."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_timeout",
                "user_code": "TIME-ME",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=TIME-ME",
                "expires_in": 1,  # very short
                "interval": 0,
            },
        }
        token_resps = [
            {"status_code": 400, "json_data": {"error": "authorization_pending"}},
        ]

        MockClient = self._make_client_mock(code_resp, token_resps)
        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", MockClient)
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)
        # Force time to jump past deadline
        monkeypatch.setattr(
            "clevertech_mcp.login.time.time",
            lambda: 9999999999.0,  # far in the future
        )

        with pytest.raises(SystemExit) as exc_info:
            device_login(base_url="https://clevertech.ca")
        assert exc_info.value.code == 1

    def test_device_code_request_fails(self, temp_config_dir, monkeypatch):
        """Network error during device code request."""
        import httpx

        class FailingClient:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def post(self, url, json=None, **kwargs):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", FailingClient)

        with pytest.raises(SystemExit) as exc_info:
            device_login(base_url="https://clevertech.ca")
        assert exc_info.value.code == 1

    def test_trailing_slash_in_base_url(self, temp_config_dir, monkeypatch):
        """Base URL with trailing slash is normalized."""
        code_resp = {
            "status_code": 200,
            "json_data": {
                "device_code": "dc_slash",
                "user_code": "SLSH-OK",
                "verification_uri_complete": "https://clevertech.ca/auth/device/verify?code=SLSH-OK",
                "expires_in": 900,
                "interval": 0,
            },
        }
        token_resps = [
            {"status_code": 200, "json_data": {"access_token": "ctk_slash_test", "token_type": "bearer"}},
        ]

        # Track what URLs were called
        urls_called = []

        class TrackingClient:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def post(self, url, json=None, **kwargs):
                urls_called.append(url)
                if "/device/code" in url:
                    resp = code_resp
                else:
                    resp = token_resps[0]
                return MockResponse(**resp)

        monkeypatch.setattr("clevertech_mcp.login.httpx.Client", TrackingClient)
        monkeypatch.setattr("clevertech_mcp.login.time.sleep", lambda x: None)

        result = device_login(base_url="https://clevertech.ca/")
        assert result == "ctk_slash_test"
        # No double slashes
        for url in urls_called:
            assert "//" not in url.replace("https://", "https:")
