"""
CleverTech MCP Server — configuration loader.

Loads settings from environment variables via python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    """Load and return the server configuration as a dict.

    Environment variables read:
        CLEVERTECH_API_URL      — base URL for the CleverTech API
        CLEVERTECH_API_KEY      — API key for authenticated requests
        PORT                    — port for SSE transport
        TRANSPORT               — transport mode (stdio or sse)
        LOG_LEVEL               — logging level
        RATE_LIMIT_ANON_DAILY   — max anonymous requests per day
        RATE_LIMIT_ANON_BURST   — max anonymous requests per minute
        SENTRY_DSN              — Sentry DSN for error tracking
    """
    return {
        "api_url": os.getenv("CLEVERTECH_API_URL", "https://clevertech.ca"),
        "api_key": os.getenv("CLEVERTECH_API_KEY"),
        "port": int(os.getenv("PORT", "8001")),
        "transport": os.getenv("TRANSPORT", "stdio"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "rate_limit_anon_daily": int(os.getenv("RATE_LIMIT_ANON_DAILY", "50")),
        "rate_limit_anon_burst": int(os.getenv("RATE_LIMIT_ANON_BURST", "10")),
        "sentry_dsn": os.getenv("SENTRY_DSN"),
    }
