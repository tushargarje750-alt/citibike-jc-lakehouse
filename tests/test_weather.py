import json
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from citibike_ingest import weather


def fake_payload(start: date, end: date, missing_last: int = 0) -> dict:
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    daily = {"time": days}
    for variable in weather.DAILY_VARIABLES:
        values = [1.0] * len(days)
        if missing_last:
            values[-missing_last:] = [None] * missing_last
        daily[variable] = values
    return {"latitude": 40.7, "longitude": -74.0, "daily_units": {}, "daily": daily}


def fake_fetch(calls: list, missing_last: int = 0):
    def fetch(url: str) -> bytes:
        query = parse_qs(urlparse(url).query)
        start = date.fromisoformat(query["start_date"][0])
        end = date.fromisoformat(query["end_date"][0])
        calls.append((start, end))
        return json.dumps(fake_payload(start, end, missing_last)).encode()
    return fetch


def test_url_requests_every_variable_in_local_time():
    query = parse_qs(urlparse(weather.build_url(date(2024, 1, 1), date(2024, 1, 31))).query)
    assert query["daily"][0].split(",") == weather.DAILY_VARIABLES
    assert query["timezone"] == ["America/New_York"]
    assert query["start_date"] == ["2024-01-01"] and query["end_date"] == ["2024-01-31"]


def test_plan_covers_partial_first_year_and_stops_before_the_lag():
    plan = weather.plan_requests(date(2015, 9, 1), date(2017, 3, 20), complete_years=set())
    assert plan == [
        (2015, date(2015, 9, 1), date(2015, 12, 31)),
        (2016, date(2016, 1, 1), date(2016, 12, 31)),
        (2017, date(2017, 1, 1), date(2017, 3, 14)),
    ]


def test_plan_skips_years_that_are_already_complete():
    plan = weather.plan_requests(date(2015, 9, 1), date(2017, 3, 20), complete_years={2015, 2016})
    assert [year for year, _, _ in plan] == [2017]


def test_validation_counts_missing_values():
    start, end = date(2024, 1, 1), date(2024, 1, 10)
    quality = weather.validate_payload(fake_payload(start, end, missing_last=2), start, end)
    assert quality == {"days": 10, "days_missing_temperature": 2, "days_missing_precipitation": 2}


def test_validation_rejects_wrong_range_and_api_errors():
    start, end = date(2024, 1, 1), date(2024, 1, 10)
    with pytest.raises(ValueError):
        weather.validate_payload(fake_payload(start, date(2024, 1, 9)), start, end)
    with pytest.raises(ValueError):
        weather.validate_payload({"error": True, "reason": "bad request"}, start, end)


def test_first_run_writes_one_raw_file_per_year(tmp_path):
    calls = []
    result = weather.land_weather(str(tmp_path), date(2015, 9, 1), today=date(2017, 3, 20),
                                  fetch=fake_fetch(calls), log=lambda _: None, pause_s=0)
    assert [r["year"] for r in result.records] == [2015, 2016, 2017]
    assert sum(r["days"] for r in result.records) == 122 + 366 + 73
    assert (tmp_path / "weather/open_meteo_daily_2016.json").exists()


def test_second_run_refetches_only_the_open_year(tmp_path):
    first_calls, second_calls = [], []
    weather.land_weather(str(tmp_path), date(2015, 9, 1), today=date(2017, 3, 20),
                         fetch=fake_fetch(first_calls), log=lambda _: None, pause_s=0)
    result = weather.land_weather(str(tmp_path), date(2015, 9, 1), today=date(2017, 3, 21),
                                  fetch=fake_fetch(second_calls), log=lambda _: None, pause_s=0)
    assert [start.year for start, _ in second_calls] == [2017]
    assert result.skipped_years == [2015, 2016]


def test_year_landed_while_incomplete_is_fetched_again_once_it_ends(tmp_path):
    weather.land_weather(str(tmp_path), date(2016, 1, 1), today=date(2016, 11, 20),
                         fetch=fake_fetch([]), log=lambda _: None, pause_s=0)
    calls = []
    weather.land_weather(str(tmp_path), date(2016, 1, 1), today=date(2017, 2, 1),
                         fetch=fake_fetch(calls), log=lambda _: None, pause_s=0)
    assert (date(2016, 1, 1), date(2016, 12, 31)) in calls


def test_failed_year_is_reported_and_others_continue(tmp_path):
    good = fake_fetch([])

    def flaky(url):
        if "start_date=2016" in url:
            raise RuntimeError("simulated outage")
        return good(url)

    result = weather.land_weather(str(tmp_path), date(2015, 9, 1), today=date(2017, 3, 20),
                                  fetch=flaky, log=lambda _: None, pause_s=0)
    assert [year for year, _ in result.failures] == [2016]
    assert [r["year"] for r in result.records] == [2015, 2017]


def test_flatten_gives_one_row_per_day_in_table_column_order():
    start, end = date(2024, 2, 27), date(2024, 3, 1)
    payload = fake_payload(start, end)
    payload["elevation"] = 7
    payload["daily"]["weather_code"] = [3, 61, 71, None]
    payload["daily"]["snowfall_sum"] = [0, 0, 2.1, None]

    rows = weather.flatten_daily(payload, "/vol/weather/open_meteo_daily_2024.json")

    assert [row[0] for row in rows] == ["2024-02-27", "2024-02-28", "2024-02-29", "2024-03-01"]
    assert all(len(row) == len(weather.WEATHER_ROW_COLUMNS) for row in rows)
    as_dict = dict(zip(weather.WEATHER_ROW_COLUMNS, rows[2]))
    assert as_dict["weather_code"] == 71 and as_dict["snowfall_sum"] == 2.1
    assert as_dict["grid_elevation_m"] == 7.0
    assert as_dict["_source_file"].endswith("open_meteo_daily_2024.json")
    last = dict(zip(weather.WEATHER_ROW_COLUMNS, rows[3]))
    assert last["weather_code"] is None and last["snowfall_sum"] is None


def test_bronze_columns_cover_every_requested_variable():
    assert set(weather.DAILY_VARIABLES) <= set(weather.WEATHER_ROW_COLUMNS)
    # the DDL lists the variables in the same order flatten_daily emits them
    measures = [v for v in weather.DAILY_VARIABLES if v != "weather_code"]
    assert weather.WEATHER_ROW_COLUMNS[2:2 + len(measures)] == measures

