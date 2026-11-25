"""Checks on the demo-site export script and on the data file it wrote.

No Databricks needed: the SQL runner is replaced by a fake that answers from memory.
"""
import datetime as dt
import decimal
import json
import os

import pytest

import export_demo_data as export

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEMO_FILE = os.path.join(ROOT, "site", "data", "demo.json")


def fake_runner(bronze=10, accepted=9, quarantined=1, reasons=(("duration_too_short", 1),), kpi_total=9):
    """Answers each query by recognising a word in it."""
    def run(sql):
        if "bronze_rows" in sql:
            return ["bronze_rows", "accepted_rows", "quarantined_rows"], [(bronze, accepted, quarantined)]
        if "rejection_reason" in sql:
            return ["rejection_reason", "row_count"], list(reasons)
        if "days_with_trips" in sql:
            return ["ride_year", "trips", "days_with_trips"], [(2026, decimal.Decimal(9), 3)]
        if "busiest_day" in sql:
            return (["first_day", "last_day", "busiest_day", "busiest_day_trips"],
                    [(dt.date(2026, 10, 1), dt.date(2026, 10, 3), dt.date(2026, 10, 2), 5)])
        if "total_trips" in sql:
            return ["total_trips", "avg_trips_per_day", "member_share_pct", "electric_share_pct"], [
                (kpi_total, 3, decimal.Decimal("66.7"), decimal.Decimal("33.3"))]
        return ["ride_month", "member_trips"], [(dt.date(2026, 10, 1), 6)]
    return run


def test_dashboard_queries_are_the_seven_dashboard_datasets():
    queries = export.dashboard_queries()
    assert set(queries) == {
        "ds_kpis", "ds_monthly", "ds_top_stations", "ds_peak_hours",
        "ds_duration", "ds_weather", "ds_daily_weather",
    }
    assert all(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in queries.values())


def test_every_query_only_reads():
    sql = list(export.dashboard_queries().values()) + list(export.EXTRA_QUERIES.values())
    for statement in sql:
        words = statement.upper().split()
        for verb in ("INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "CREATE", "ALTER", "TRUNCATE", "GRANT"):
            assert verb not in words


def test_with_catalog_switches_only_the_project_schemas():
    sql = "SELECT 1 FROM workspace.citibike_gold.daily_ridership JOIN workspace.other.t"
    assert export.with_catalog(sql, "workspace") == sql
    assert export.with_catalog(sql, "dev") == "SELECT 1 FROM dev.citibike_gold.daily_ridership JOIN workspace.other.t"


@pytest.mark.parametrize("value, expected", [
    (decimal.Decimal("5"), 5),
    (decimal.Decimal("72.1"), 72.1),
    (dt.date(2026, 9, 12), "2026-09-12"),
    (True, True),
    (None, None),
    (0.1234567891, 0.123457),
    ("Grove St PATH", "Grove St PATH"),
])
def test_jsonable(value, expected):
    assert export.jsonable(value) == expected


def test_build_payload_shape():
    queries = {"ds_kpis": "SELECT total_trips", "ds_monthly": "SELECT month"}
    payload = export.build_payload(fake_runner(), "workspace", "2026-11-24T00:00:00Z", queries=queries)
    assert payload["meta"]["exported_at"] == "2026-11-24T00:00:00Z"
    assert payload["meta"]["first_day"] == "2026-10-01"
    assert payload["datasets"]["ds_kpis"]["columns"][0] == "total_trips"
    assert payload["datasets"]["ds_monthly"]["rows"] == [["2026-10-01", 6]]
    assert payload["quality"]["bronze_rows"] == 10
    assert payload["yearly"]["rows"] == [[2026, 9, 3]]
    json.dumps(payload)  # everything must be serialisable


def test_build_payload_refuses_rows_that_do_not_add_up():
    with pytest.raises(ValueError, match="not all accounted"):
        export.build_payload(fake_runner(bronze=11), "workspace", "x", queries={})


def test_build_payload_refuses_reasons_that_do_not_add_up():
    with pytest.raises(ValueError, match="reasons add up"):
        export.build_payload(fake_runner(reasons=(("duration_too_short", 2),)), "workspace", "x", queries={})


def test_build_payload_refuses_a_gold_total_that_differs_from_silver():
    with pytest.raises(ValueError, match="gold total"):
        export.build_payload(fake_runner(kpi_total=8), "workspace", "x", queries={"ds_kpis": "SELECT total_trips"})


# ---------- the saved file that the website reads ----------

@pytest.fixture(scope="module")
def demo():
    if not os.path.exists(DEMO_FILE):
        pytest.skip("site/data/demo.json has not been exported yet")
    with open(DEMO_FILE) as handle:
        return json.load(handle)


def rows(table):
    return [dict(zip(table["columns"], row)) for row in table["rows"]]


def test_demo_file_has_every_dashboard_dataset(demo):
    assert set(demo["datasets"]) == set(export.dashboard_queries())


def test_demo_file_numbers_agree_with_each_other(demo):
    kpis = rows(demo["datasets"]["ds_kpis"])[0]
    quality = demo["quality"]
    monthly = rows(demo["datasets"]["ds_monthly"])
    daily = rows(demo["datasets"]["ds_daily_weather"])
    yearly = rows(demo["yearly"])

    assert quality["bronze_rows"] == quality["accepted_rows"] + quality["quarantined_rows"]
    assert sum(r["row_count"] for r in rows(quality["reasons"])) == quality["quarantined_rows"]
    assert kpis["total_trips"] == quality["accepted_rows"]
    assert sum(m["member_trips"] + m["casual_trips"] for m in monthly) == kpis["total_trips"]
    assert sum(y["trips"] for y in yearly) == kpis["total_trips"]
    assert sum(d["trips"] for d in daily) == kpis["total_trips"]
    assert len(rows(demo["datasets"]["ds_top_stations"])) == 10
    assert len(rows(demo["datasets"]["ds_peak_hours"])) == 24
