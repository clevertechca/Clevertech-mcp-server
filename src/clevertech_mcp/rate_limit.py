"""
Local in-memory rate limiter for anonymous users.

Tracks requests per source IP using a sliding-window approach:
- Daily limit (24-hour sliding window)
- Burst limit (1-minute sliding window)
"""

import time
import threading
from typing import Optional


class LocalRateLimiter:
    """Thread-safe in-memory rate limiter keyed by source IP."""

    def __init__(
        self,
        daily_limit: int = 50,
        burst_per_minute: int = 10,
    ) -> None:
        self._daily_limit = daily_limit
        self._burst_per_minute = burst_per_minute
        self._storage: dict[str, list[tuple[float, int]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _prune(self, key: str, now: float) -> None:
        """Remove entries older than 24 hours from *key*'s history."""
        if key not in self._storage:
            return
        cutoff = now - 86400.0  # 24 hours
        self._storage[key] = [
            (ts, cost) for ts, cost in self._storage[key] if ts > cutoff
        ]
        if not self._storage[key]:
            del self._storage[key]

    def _daily_usage(self, key: str) -> int:
        """Total cost accumulated by *key* in the last 24 hours."""
        return sum(cost for _, cost in self._storage.get(key, []))

    def _burst_usage(self, key: str, now: float) -> int:
        """Total cost accumulated by *key* in the last 60 seconds."""
        cutoff = now - 60.0
        return sum(
            cost
            for ts, cost in self._storage.get(key, [])
            if ts > cutoff
        )

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def check(self, source_ip: str, cost: int = 1) -> tuple[bool, str]:
        """Check whether *source_ip* is allowed to proceed.

        Returns ``(True, "")`` if allowed, or ``(False, message)`` if
        the request would exceed a rate limit.
        """
        now = time.time()
        with self._lock:
            self._prune(source_ip, now)

            daily = self._daily_usage(source_ip)
            if daily + cost > self._daily_limit:
                remaining = self._daily_limit - daily
                return False, (
                    f"Daily rate limit exceeded. "
                    f"{max(0, remaining)} of {self._daily_limit} requests remaining."
                )

            burst = self._burst_usage(source_ip, now)
            if burst + cost > self._burst_per_minute:
                return False, (
                    f"Burst rate limit exceeded. "
                    f"Max {self._burst_per_minute} requests per minute."
                )

            # Record the request
            self._storage.setdefault(source_ip, []).append((now, cost))
            return True, ""

    def remaining(self, source_ip: str) -> dict[str, int]:
        """Return a summary of remaining capacity for *source_ip*."""
        now = time.time()
        with self._lock:
            self._prune(source_ip, now)
            daily = self._daily_usage(source_ip)
            burst = self._burst_usage(source_ip, now)
            return {
                "daily_used": daily,
                "daily_remaining": max(0, self._daily_limit - daily),
                "daily_limit": self._daily_limit,
                "burst_remaining": max(0, self._burst_per_minute - burst),
            }
