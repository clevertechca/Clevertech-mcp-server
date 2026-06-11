"""
Device authorization flow (RFC 8628) for the CleverTech MCP server.

Provides the ``device_login`` function that:
1. POSTs to /auth/device/code to get a device code + verification URL
2. Prints the URL for the user to open in their browser
3. Polls /auth/device/token until the user authorizes or it expires
4. Saves the resulting API key to ~/.clevertech/config.json
5. Returns the API key string
"""

import json
import os
import sys
import time
import httpx

CONFIG_DIR = os.path.expanduser("~/.clevertech")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def _save_api_key(api_key: str) -> None:
    """Save the API key to the config file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config: dict = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}
    config["api_key"] = api_key
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)  # Protect the key


def load_saved_api_key() -> str | None:
    """Load a previously saved API key from the config file, if any."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            if isinstance(config, dict):
                return config.get("api_key")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def device_login(base_url: str = "https://clevertech.ca") -> str:
    """
    Run the device authorization flow interactively.

    Returns the API key (ctk_...) on success.
    Exits with an error message if the flow times out or fails.
    """
    # Step 1: Get device code
    code_url = f"{base_url.rstrip('/')}/auth/device/code"
    token_url = f"{base_url.rstrip('/')}/auth/device/token"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                code_url,
                json={"client_name": "clevertech-mcp-server", "scopes": "*"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        print(f"\n  ❌ Failed to request device code: {e}")
        sys.exit(1)

    try:
        device_code = data["device_code"]
        user_code = data["user_code"]
        verification_uri = data["verification_uri_complete"]
    except KeyError as e:
        print(f"\n  ❌ Unexpected response from server (missing field: {e})")
        sys.exit(1)
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 900)

    # Print the user-friendly message
    print("\n" + "=" * 60)
    print("  CleverTech MCP Server — Device Authorization")
    print("=" * 60)
    print(f"\n  Your user code: {user_code}")
    print("\n  Open this URL in your browser:")
    print(f"  {verification_uri}")
    print("\n  Sign in with your Google account and authorize the request.")
    print(f"  This code expires in {expires_in // 60} minutes.")
    print("\n  Waiting for authorization", end="", flush=True)

    # Step 2: Poll for token
    deadline = time.time() + expires_in
    try:
        while time.time() < deadline:
            time.sleep(interval)
            print(".", end="", flush=True)

            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        token_url,
                        json={"device_code": device_code},
                    )
                    if resp.status_code == 200:
                        token_data = resp.json()
                        api_key = token_data.get("access_token")
                        if api_key:
                            print("\n")
                            _save_api_key(api_key)
                            print("  ✅ Authorization successful!")
                            print(f"  API key saved to {CONFIG_FILE}")
                            print(f"  Your key: {api_key[:8]}...{api_key[-4:]}")
                            print("\n  The MCP server will use this key automatically.")
                            print("=" * 60 + "\n")
                            return api_key
                    elif resp.status_code == 400:
                        error_data = resp.json()
                        error = error_data.get("error", "")
                        if error == "authorization_pending":
                            continue  # Normal — user hasn't authorized yet
                        elif error == "access_denied":
                            print("\n")
                            print("  ❌ Authorization denied by user.")
                            sys.exit(1)
                        elif error == "expired_token":
                            print("\n")
                            print("  ❌ Device code expired. Please run --login again.")
                            sys.exit(1)
                        else:
                            print(f"\n  ❌ Unexpected error: {error}")
                            sys.exit(1)
                    else:
                        print(f"\n  ❌ HTTP {resp.status_code}: {resp.text}")
                        sys.exit(1)
            except httpx.RequestError as e:
                print(f"\n  ❌ Network error: {e}")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n")
        print("  ❌ Login cancelled.")
        sys.exit(130)

    print("\n")
    print("  ❌ Timed out waiting for authorization.")
    sys.exit(1)
