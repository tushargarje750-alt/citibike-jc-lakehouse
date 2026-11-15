# Metrics log

Every number here was copied from real terminal, notebook or Databricks output on the date
shown. Nothing is estimated. "Pending" means not measured yet.

## Phase 0 — setup (2026-11-14)

### Environment

| Item | Value | Source |
|---|---|---|
| Databricks edition | Free Edition, serverless only | workspace |
| SQL warehouse | Serverless Starter Warehouse, 2X-Small | `databricks warehouses list` |
| Catalog | `workspace` | `databricks catalogs list` |
| Databricks CLI | 1.26.0 | `databricks -v` |
| Python | 3.12.16 | Homebrew install log |
| dbt Core | 1.12.6 | `dbt --version` |
| dbt-databricks adapter | 1.13.0 | `dbt --version` |
| `dbt debug` | All checks passed (2026-11-14, 23:40 ET) | `dbt debug` |

### Outbound network test from Databricks serverless compute

Run in a notebook before LinkedIn verification.

| Target | Result |
|---|---|
| `s3.amazonaws.com/tripdata` (Citi Bike zip) | HTTP 200, zip header `PK` |
| `archive-api.open-meteo.com` (weather JSON) | HTTP 200, JSON |
| `pypi.org` (control) | HTTP 200 |

### Source inventory (public bucket listing)

To be re-verified by the landing notebook in Phase 1.

| Item | Value |
|---|---|
| Files with the `JC-` prefix | 134 |
| First month | 2015-09 (`JC-201509-citibike-tripdata.csv.zip`) |
| Latest month | 2026-10 (`JC-202610-citibike-tripdata.zip`) |
| Missing months between first and latest | 0 |
| File names that break the usual pattern | 6 |
| — space instead of hyphen | 1 (`JC-201708 citibike-tripdata.csv.zip`) |
| — misspelled "citbike" | 1 (`JC-202207-citbike-tripdata.csv.zip`) |
| — `.zip` without `.csv` | 4 (2025-10, 2026-01, 2026-04, 2026-10) |

## Phase 1 — landing and data discovery

| Item | Value | Source |
|---|---|---|
| Unit tests (landing + weather logic) | 33 | `pytest` |
| Unit tests passing locally | Pending | `pytest` on the Mac |
| Trip files landed, first run | Pending | notebook 01 run summary |
| Data rows landed | Pending | notebook 01 run summary |
| Zip size / CSV size | Pending | notebook 01 run summary |
| First run duration | Pending | notebook 01 run summary |
| Files landed on an immediate second run | Pending (expected 0) | notebook 01 run summary |
| Months per file format, and switch-over month | Pending | notebook 01 data discovery |
| Distinct header variants | Pending | notebook 01 data discovery |
| Weather days landed | Pending | notebook 02 run summary |
| Weather days without temperature | Pending | notebook 02 run summary |
