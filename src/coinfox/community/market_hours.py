"""NY Fox Exchange (NYFE) market-hours utilities.

All time arithmetic is pure Python - no pytz or zoneinfo required.
US Eastern DST rules are computed manually from POSIX-era rules
(second Sunday March to first Sunday November).
"""

from __future__ import annotations

import calendar
import time
from datetime import datetime, timedelta
from typing import Optional

from .models import MarketSession

# ---------------------------------------------------------------------------
# NYFE trading-hours constants (Eastern time)
# ---------------------------------------------------------------------------
NYFE_TIMEZONE = "America/New_York"
NYFE_OPEN_HOUR = 9
NYFE_OPEN_MINUTE = 30
NYFE_CLOSE_HOUR = 16
NYFE_CLOSE_MINUTE = 0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def nyfe_timestamp(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """Return a UTC Unix timestamp for a given Eastern wall-clock time."""
    return _eastern_to_timestamp(datetime(year, month, day, hour, minute))


def format_market_timestamp(ts: int) -> str:
    eastern = _eastern_from_timestamp(ts)
    return eastern.strftime("%a %I:%M %p") + f" {_eastern_tz_abbrev(eastern)}"


def market_now_text(now_ts: Optional[int] = None) -> str:
    eastern = _eastern_from_timestamp(now_ts)
    return eastern.strftime("%a %I:%M %p") + f" {_eastern_tz_abbrev(eastern)}"


def market_session(now_ts: Optional[int] = None) -> MarketSession:
    """Return the current (or next) NYFE market session window."""
    return _market_session(now_ts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _market_session(now_ts: Optional[int] = None) -> MarketSession:
    now_local = _eastern_from_timestamp(now_ts)
    open_dt = now_local.replace(hour=NYFE_OPEN_HOUR, minute=NYFE_OPEN_MINUTE, second=0, microsecond=0)
    close_dt = now_local.replace(hour=NYFE_CLOSE_HOUR, minute=NYFE_CLOSE_MINUTE, second=0, microsecond=0)
    is_weekday = now_local.weekday() < 5
    is_open = is_weekday and open_dt <= now_local < close_dt

    if is_open:
        next_open = open_dt
        next_close = close_dt
    else:
        if is_weekday and now_local < open_dt:
            next_open = open_dt
        else:
            next_open = open_dt + timedelta(days=1)
            while next_open.weekday() >= 5:
                next_open += timedelta(days=1)
        next_close = next_open.replace(
            hour=NYFE_CLOSE_HOUR, minute=NYFE_CLOSE_MINUTE, second=0, microsecond=0
        )
    return MarketSession(
        is_open=is_open,
        opens_at_ts=_eastern_to_timestamp(next_open),
        closes_at_ts=_eastern_to_timestamp(next_close),
    )


def _eastern_from_timestamp(now_ts: Optional[int] = None) -> datetime:
    utc_dt = datetime.utcfromtimestamp(now_ts if now_ts is not None else time.time())
    offset_hours = _eastern_utc_offset_hours(utc_dt)
    return utc_dt + timedelta(hours=offset_hours)


def _eastern_to_timestamp(local_dt: datetime) -> int:
    offset_hours = _eastern_local_offset_hours(local_dt)
    utc_dt = local_dt - timedelta(hours=offset_hours)
    return int(calendar.timegm(utc_dt.timetuple()))


def _eastern_tz_abbrev(local_dt: datetime) -> str:
    return "EDT" if _eastern_local_offset_hours(local_dt) == -4 else "EST"


def _eastern_utc_offset_hours(utc_dt: datetime) -> int:
    start_utc, end_utc = _us_eastern_dst_bounds_utc(utc_dt.year)
    return -4 if start_utc <= utc_dt < end_utc else -5


def _eastern_local_offset_hours(local_dt: datetime) -> int:
    start_local = datetime(
        local_dt.year, 3,
        _nth_weekday_of_month(local_dt.year, 3, 6, 2),
        2, 0,
    )
    end_local = datetime(
        local_dt.year, 11,
        _nth_weekday_of_month(local_dt.year, 11, 6, 1),
        2, 0,
    )
    return -4 if start_local <= local_dt < end_local else -5


def _us_eastern_dst_bounds_utc(year: int) -> tuple[datetime, datetime]:
    start_day = _nth_weekday_of_month(year, 3, 6, 2)
    end_day = _nth_weekday_of_month(year, 11, 6, 1)
    start_utc = datetime(year, 3, start_day, 7, 0)
    end_utc = datetime(year, 11, end_day, 6, 0)
    return start_utc, end_utc


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> int:
    first = datetime(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return 1 + delta + (occurrence - 1) * 7
