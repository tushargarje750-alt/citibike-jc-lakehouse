"""Landing step for daily weather from the Open-Meteo historical archive API.

One raw JSON file per calendar year is stored unchanged in the landing volume.
Finished years are fetched once; the current year is re-fetched on every run
because new days keep arriving.

Weather data by Open-Meteo.com (CC BY 4.0).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from urllib.parse import urlencode

from .http_util import http_get

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# One point between downtown Jersey City and Hoboken. The archive is a gridded
# reanalysis, so the API snaps this to the nearest grid cell.
LATITUDE = 40.73
LONGITUDE = -74.04
TIMEZONE = "America/New_York"

DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
]

# The archive lags real time by a few days; asking for very recent days returns nulls.
LAG_DAYS = 6

Fetch = Callable[[str], bytes]


def build_url(start: date, end: date) -> str:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
    }
    return f"{ARCHIVE_URL}?{urlencode(params)}"


def year_path(volume_root: str, year: int) -> str:
    return f"{volume_root}/weather/open_meteo_daily_{year}.json"


def landed_last_day(path: str) -> Optional[str]:
    """Last date inside an already-landed year file, or None if it is missing or unreadable."""
    try:
        with open(path, "rb") as handle:
            return json.load(handle)["daily"]["time"][-1]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def plan_requests(first_day: date, today: date, complete_years: set[int]) -> list[tuple[int, date, date]]:
    """Which (year, start, end) ranges to request.

    complete_years are years whose landed file already runs to 31 December;
    those are skipped. Every other year up to the last available day is requested.
    """
    last_available = today - timedelta(days=LAG_DAYS)
    plan = []
    for year in range(first_day.year, last_available.year + 1):
        start = max(first_day, date(year, 1, 1))
        end = min(last_available, date(year, 12, 31))
        if start > end:
            continue
        if year in complete_years:
            continue
        plan.append((year, start, end))
    return plan


def validate_payload(payload: dict, start: date, end: date) -> dict:
    """Check the response covers exactly the requested days; return simple quality counts."""
    if payload.get("error"):
        raise ValueError(f"Open-Meteo error: {payload.get('reason')}")
    daily = payload.get("daily") or {}
    days = daily.get("time") or []
    expected = (end - start).days + 1
    if len(days) != expected or days[0] != start.isoformat() or days[-1] != end.isoformat():
        raise ValueError(
            f"expected {expected} days {start}..{end}, got {len(days)} "
            f"({days[0] if days else None}..{days[-1] if days else None})"
        )
    missing_variables = [v for v in DAILY_VARIABLES if v not in daily]
    if missing_variables:
        raise ValueError(f"response is missing variables: {missing_variables}")
    for variable in DAILY_VARIABLES:
        if len(daily[variable]) != expected:
            raise ValueError(f"{variable} has {len(daily[variable])} values, expected {expected}")
    return {
        "days": expected,
        "days_missing_temperature": sum(1 for v in daily["temperature_2m_mean"] if v is None),
        "days_missing_precipitation": sum(1 for v in daily["precipitation_sum"] if v is None),
    }


@dataclass
class WeatherResult:
    records: list[dict] = field(default_factory=list)
    skipped_years: list[int] = field(default_factory=list)
    failures: list[tuple[int, str]] = field(default_factory=list)
    seconds: float = 0.0


def land_weather(
    volume_root: str,
    first_day: date,
    today: Optional[date] = None,
    fetch: Fetch = http_get,
    log: Callable[[str], None] = print,
    pause_s: float = 0.5,
) -> WeatherResult:
    """Fetch the years that are missing or still open and store each response unchanged."""
    started = time.time()
    today = today or datetime.now(timezone.utc).date()
    result = WeatherResult()

    last_year = (today - timedelta(days=LAG_DAYS)).year
    all_years = list(range(first_day.year, last_year + 1))
    complete = {y for y in all_years if landed_last_day(year_path(volume_root, y)) == f"{y}-12-31"}
    plan = plan_requests(first_day, today, complete)
    planned_years = {year for year, _, _ in plan}
    result.skipped_years = [y for y in all_years if y not in planned_years]

    log(f"{len(plan)} year(s) to fetch, {len(result.skipped_years)} already complete")

    for position, (year, start, end) in enumerate(plan, start=1):
        try:
            body = fetch(build_url(start, end))
            quality = validate_payload(json.loads(body), start, end)
            path = year_path(volume_root, year)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(body)
            result.records.append({
                "year": year,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "path": path,
                "bytes": len(body),
                **quality,
            })
            log(f"[{position}/{len(plan)}] {year}: {quality['days']} days {start}..{end}, "
                f"{quality['days_missing_temperature']} without temperature")
        except Exception as err:  # noqa: BLE001 - report and continue with the next year
            result.failures.append((year, f"{type(err).__name__}: {err}"))
            log(f"[{position}/{len(plan)}] {year}: FAILED {type(err).__name__}: {err}")
        if pause_s and position < len(plan):
            time.sleep(pause_s)

    result.seconds = round(time.time() - started, 1)
    return result
