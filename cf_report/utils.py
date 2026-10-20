"""
Shared utilities for number and byte formatting, time calculation, and country resolution.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import COUNTRY_MAP, CadenceDefinition
from .models import TimeWindow


def format_bytes(b: int | float) -> str:
    """Format bytes into human-readable GiB/MiB/KiB/B."""
    if b is None or b < 0:
        return "0 B"
    b_float = float(b)
    if b_float >= 1073741824:
        return f"{b_float / 1073741824:.2f} GiB"
    if b_float >= 1048576:
        return f"{b_float / 1048576:.2f} MiB"
    if b_float >= 1024:
        return f"{b_float / 1024:.2f} KiB"
    return f"{int(b_float)} B"


def format_number(n: Optional[int | float], default: str = "-") -> str:
    """Format integers/floats with thousands separators."""
    if n is None:
        return default
    return f"{n:,}"


def format_percent(part: float, total: float, decimals: int = 1) -> str:
    """Compute and format percentage."""
    if not total or total <= 0:
        return f"0.{'0' * decimals}%"
    pct = (part / total) * 100
    return f"{pct:.{decimals}f}%"


def get_country_name(code: str) -> str:
    """Resolve ISO country code to human-readable country name."""
    if not code:
        return "Unknown"
    return COUNTRY_MAP.get(code.upper(), code)


def calculate_time_window(
    cadence: CadenceDefinition,
    reference_dt: Optional[datetime] = None,
) -> TimeWindow:
    """
    Construct TimeWindow for GraphQL and REST APIs matching the exact
    semantics of the original reporting cadence.
    """
    now = reference_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if cadence.mode == "hourly":
        since = now - timedelta(hours=cadence.relative_amount)
        start_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        display_range = (
            f"{since.strftime('%Y-%m-%d %H:%M UTC')} to {now.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        from_ms = int(since.timestamp() * 1000)
        to_ms = int(now.timestamp() * 1000)
        return TimeWindow(
            mode="hourly",
            start_iso=start_iso,
            end_iso=end_iso,
            display_range=display_range,
            from_epoch_ms=from_ms,
            to_epoch_ms=to_ms,
            since_dt=start_iso,
            until_dt=end_iso,
        )

    # cadence.mode == "daily"
    yesterday = (now - timedelta(days=1)).date()
    since_date = (now - timedelta(days=cadence.relative_amount)).date()
    since_date_str = since_date.strftime("%Y-%m-%d")
    until_date_str = yesterday.strftime("%Y-%m-%d")
    since_dt = f"{since_date_str}T00:00:00Z"
    until_dt = f"{until_date_str}T23:59:59Z"
    display_range = f"{since_date_str} to {until_date_str} (through 23:59 UTC)"

    dt_start = datetime.strptime(since_dt, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    dt_end = datetime.strptime(until_dt, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    from_ms = int(dt_start.timestamp() * 1000)
    to_ms = int(dt_end.timestamp() * 1000)

    return TimeWindow(
        mode="daily",
        start_iso=since_dt,
        end_iso=until_dt,
        display_range=display_range,
        from_epoch_ms=from_ms,
        to_epoch_ms=to_ms,
        since_date=since_date_str,
        until_date=until_date_str,
        since_dt=since_dt,
        until_dt=until_dt,
    )
