#!/usr/bin/env python3
"""Export the results shown on the demo website to site/data/demo.json.

Usage (from the repo root, with .env filled in):

    .venv/bin/python scripts/export_demo_data.py

It only reads. It runs, on the SQL warehouse named in .env:

* the dashboard's own seven dataset queries, taken unchanged from
  dashboards/citibike_ridership.lvdash.json, so the website and the Databricks
  dashboard show the same numbers;
* a few extra SELECTs for the data-quality and year-by-year sections.

The website is static: it reads only the JSON file this script writes and never
contacts Databricks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
import sys
from typing import Callable, Iterable, Sequence

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DASHBOARD = os.path.join(ROOT, "dashboards", "citibike_ridership.lvdash.json")
DEFAULT_OUT = os.path.join(ROOT, "site", "data", "demo.json")
CATALOG_IN_DASHBOARD = "workspace"

# Extra read-only queries. {catalog} is filled in from DBT_CATALOG.
EXTRA_QUERIES = {
    "quality_totals": """
        SELECT
          (SELECT count(*) FROM {catalog}.citibike_bronze.trips_raw)        AS bronze_rows,
          (SELECT count(*) FROM {catalog}.citibike_silver.fct_trips)        AS accepted_rows,
          (SELECT count(*) FROM {catalog}.citibike_silver.trips_quarantine) AS quarantined_rows
    """,
    "quality_reasons": """
        SELECT rejection_reason, count(*) AS row_count
        FROM {catalog}.citibike_silver.trips_quarantine
        GROUP BY rejection_reason
        ORDER BY row_count DESC, rejection_reason
    """,
    "yearly": """
        SELECT ride_year, sum(trips) AS trips, count(*) AS days_with_trips
        FROM {catalog}.citibike_gold.daily_ridership
        GROUP BY ride_year
        ORDER BY ride_year
    """,
    "period": """
        SELECT min(ride_date) AS first_day, max(ride_date) AS last_day,
               max_by(ride_date, trips) AS busiest_day, max(trips) AS busiest_day_trips
        FROM {catalog}.citibike_gold.daily_ridership
    """,
}

Table = dict  # {"columns": [...], "rows": [[...], ...]}
Runner = Callable[[str], tuple[Sequence[str], Iterable[Sequence]]]


def dashboard_queries(path: str = DASHBOARD) -> dict[str, str]:
    """The SQL of every dataset in the dashboard definition, keyed by dataset name."""
    with open(path) as handle:
        dashboard = json.load(handle)
    return {ds["name"]: "".join(ds["queryLines"]) for ds in dashboard["datasets"]}


def with_catalog(sql: str, catalog: str) -> str:
    """Point the dashboard SQL (written for the 'workspace' catalog) at another catalog."""
    if catalog == CATALOG_IN_DASHBOARD:
        return sql
    return sql.replace(f"{CATALOG_IN_DASHBOARD}.citibike_", f"{catalog}.citibike_")


def jsonable(value):
    """Turn a value from the SQL connector into something json.dump accepts."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, float):
        return round(value, 6)
    return value


def to_table(columns: Sequence[str], rows: Iterable[Sequence]) -> Table:
    return {"columns": list(columns), "rows": [[jsonable(v) for v in row] for row in rows]}


def first_row(table: Table) -> dict:
    return dict(zip(table["columns"], table["rows"][0]))


def build_payload(run: Runner, catalog: str, exported_at: str, queries: dict[str, str] | None = None) -> dict:
    """Run every query through `run` and assemble the demo data. Fails if the numbers disagree."""
    queries = queries if queries is not None else dashboard_queries()
    datasets = {name: to_table(*run(with_catalog(sql, catalog))) for name, sql in queries.items()}
    extra = {name: to_table(*run(sql.format(catalog=catalog))) for name, sql in EXTRA_QUERIES.items()}

    totals = first_row(extra["quality_totals"])
    if totals["bronze_rows"] != totals["accepted_rows"] + totals["quarantined_rows"]:
        raise ValueError(f"bronze rows are not all accounted for: {totals}")
    reasons_total = sum(row[1] for row in extra["quality_reasons"]["rows"])
    if reasons_total != totals["quarantined_rows"]:
        raise ValueError(f"quarantine reasons add up to {reasons_total}, not {totals['quarantined_rows']}")
    kpis = first_row(datasets["ds_kpis"]) if "ds_kpis" in datasets else None
    if kpis and kpis["total_trips"] != totals["accepted_rows"]:
        raise ValueError(f"gold total {kpis['total_trips']} differs from fct_trips {totals['accepted_rows']}")

    return {
        "meta": {
            "exported_at": exported_at,
            "source": "Databricks SQL warehouse: gold tables plus silver/bronze row counts",
            "dashboard_definition": "dashboards/citibike_ridership.lvdash.json",
            **first_row(extra["period"]),
        },
        "datasets": datasets,
        "quality": {**totals, "reasons": extra["quality_reasons"]},
        "yearly": extra["yearly"],
    }


def load_env(path: str) -> None:
    """Read KEY=value lines from .env into os.environ (values already set win)."""
    if not os.path.exists(path):
        return
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def databricks_runner():  # pragma: no cover - needs a real warehouse
    from databricks import sql  # installed with dbt-databricks

    missing = [k for k in ("DBT_DATABRICKS_HOST", "DBT_DATABRICKS_HTTP_PATH", "DBT_ENV_SECRET_DATABRICKS_TOKEN")
               if not os.environ.get(k) or os.environ[k].endswith("REPLACE_ME")]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)}")
    connection = sql.connect(
        server_hostname=os.environ["DBT_DATABRICKS_HOST"],
        http_path=os.environ["DBT_DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DBT_ENV_SECRET_DATABRICKS_TOKEN"],
    )

    def run(query: str):
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [d[0] for d in cursor.description]
            return columns, cursor.fetchall()

    return run, connection


def main() -> None:  # pragma: no cover - needs a real warehouse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    load_env(os.path.join(ROOT, ".env"))
    catalog = os.environ.get("DBT_CATALOG") or CATALOG_IN_DASHBOARD
    run, connection = databricks_runner()
    try:
        exported_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = build_payload(run, catalog, exported_at)
    finally:
        connection.close()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
    kpis = first_row(payload["datasets"]["ds_kpis"])
    print(f"wrote {os.path.relpath(args.out, ROOT)}: {kpis['total_trips']:,} trips, "
          f"{payload['meta']['first_day']} to {payload['meta']['last_day']}")


if __name__ == "__main__":
    main()
