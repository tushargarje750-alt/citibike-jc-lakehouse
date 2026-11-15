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

## Phase 1 — landing and data discovery (2026-11-15)

### Trip files (notebook 01, run summary)

| Item | Value |
|---|---|
| JC files found in the bucket | 134 |
| Files landed / failed | 134 / 0 |
| Months covered | 2015-09 to 2026-10, 0 missing |
| Data rows landed | 7,129,105 |
| Zip size / extracted CSV size | 223.4 MB / 1,441.0 MB |
| File names that break the usual pattern | 6 (matches the Phase 0 inventory) |
| Immediate second run | 0 files landed, 134 skipped, 0.1 s |
| First-run duration | Pending (reported by notebook 03 from manifest timestamps) |

### Data discovery: two incompatible file formats

| Format | Months | Range | Rows | Columns |
|---|---|---|---|---|
| legacy (`tripduration`, `usertype`, `birth year`, …) | 65 | 2015-09 to 2021-01 | 1,702,660 | 15 |
| current (`ride_id`, `member_casual`, …) | 69 | 2021-02 to 2026-10 | 5,426,445 | 13 |

- The format switches in **February 2021**.
- 3 distinct header variants in total: 2 spellings of the legacy header
  (`tripduration` and `Trip Duration` style) and 1 current header.

### Weather (notebook 02, run summary)

| Item | Value |
|---|---|
| Year files landed | 12 (2015 to 2026) |
| Days covered | 4,088 (2015-09-01 to 2026-11-09) |
| Days without a temperature value | 0 |
| Daily variables | 10 |
| Size | 249.8 kB |
| First-run duration | 87.3 s |

### Code quality

| Item | Value | Source |
|---|---|---|
| Unit tests passing (Phase 1 code) | 33 of 33 | `pytest` on the Mac |

## Phase 2 — bronze (Delta Lake)

| Item | Value | Source |
|---|---|---|
| Unit tests passing | Pending (37 in the suite) | `pytest` on the Mac |
| Rows loaded into `trips_raw`, first run | Pending | notebook 03 run summary |
| Files loaded | Pending | notebook 03 run summary |
| First-load duration | Pending | notebook 03 run summary |
| Months where bronze and landing row counts differ | Pending (expected 0) | notebook 03 run summary |
| Rows with rescued (unexpected) data | Pending | notebook 03 run summary |
| Rows added on an immediate second run | Pending (expected 0) | notebook 03 run summary |
| Weather rows in `weather_daily_raw` | Pending | notebook 04 run summary |
