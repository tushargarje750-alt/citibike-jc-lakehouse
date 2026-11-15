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

## Phase 2 — bronze (Delta Lake) (2026-11-15)

### Trips: Auto Loader into `citibike_bronze.trips_raw` (notebook 03, run summary)

| Item | Value |
|---|---|
| Rows loaded, first run | 5,426,445 |
| Files loaded | 69 (2021-02 to 2026-10) |
| First-load duration | 25.3 s |
| Rows counted at landing vs rows in bronze | 5,426,445 vs 5,426,445 |
| Months where the two counts differ | 0 of 69 |
| Rows with rescued (unexpected) data | 0 |
| Rows with a blank ride_id | 0 |
| Rows added on an immediate second run | Pending (expected 0) |

### Landing first run, measured from the manifest

| Item | Value |
|---|---|
| Files landed in the first run | 134 |
| Time from first to last file | 98 s |

### Weather: `citibike_bronze.weather_daily_raw` (notebook 04, run summary)

| Item | Value |
|---|---|
| Rows written | 4,088 (2015-09-01 to 2026-11-09), all distinct days |
| Days without temperature / precipitation | 0 / 0 |
| Coldest / warmest value | -20.5 °C / 40.7 °C |
| Days with precipitation / snowfall | 2,124 / 256 |
| Duration | 14.1 s |

### Code quality

| Item | Value | Source |
|---|---|---|
| Unit tests in the suite | 37 | `pytest` |
| Unit tests passing on the Mac | Pending | `pytest` on the Mac |

## Phase 3 — silver (dbt) (2026-11-15)

### Build (`dbt build`, first full run)

| Item | Value |
|---|---|
| Models built | 7 (2 views, 4 tables, 1 incremental) |
| Tests run | 39 data tests + 1 unit test |
| Result | PASS=47, WARN=0, ERROR=0 |
| Duration | 34.52 s |

### Data quality (`dbt run-operation silver_summary`)

| Item | Value |
|---|---|
| Bronze rows staged | 5,426,445 |
| Accepted into `fct_trips` | 5,358,983 (98.76%) |
| Rejected into `trips_quarantine` | 67,462 (1.24%) |
| Rows unaccounted for | 0 |

| Rejection reason | Rows |
|---|---|
| Trip shorter than 60 seconds | 61,579 |
| Trip longer than 24 hours | 5,408 |
| End time not after start time | 234 |
| No start station | 201 |
| Duplicate ride_id | 40 |
| Missing ride_id, unreadable time, invalid rider type, start outside area | 0 each |

### What is in silver

| Item | Value |
|---|---|
| Trip days covered | 2021-02-01 to 2026-10-31 |
| Member / casual trips | 3,864,146 (72.1%) / 1,494,837 (27.9%) |
| Classic / electric / docked bike trips | 2,912,142 / 2,306,592 / 140,249 |
| Trips with no end station (kept, flagged) | 16,695 |
| Trips without a matching weather day | 0 |
| Median trip length | 6.6 minutes |
| Stations in `dim_stations` | 979 (86 Jersey City, 39 Hoboken, 854 outside) |

## Phase 4 — gold (dbt) and docs (2026-11-15)

### Build (`dbt build`, silver incremental + gold)

| Item | Value |
|---|---|
| Models in the project | 13 (7 silver, 6 gold) |
| Tests run | 73 data tests + 1 unit test |
| Result | PASS=87, WARN=0, ERROR=0 |
| Duration | Pending (the job run in Phase 5 records it) |

### Gold tables (`dbt run-operation gold_summary`)

| Table | Rows | Grain |
|---|---|---|
| `daily_ridership` | 2,097 | day |
| `top_stations` | 979 | station |
| `peak_hours` | 336 | weekday x hour x rider type |
| `member_vs_casual` | 138 | month x rider type |
| `weather_impact` | 20 | temperature band x wet/dry x weekend/weekday |
| `trip_duration_stats` | 28 | year x rider type x bike type |

### Headline analytics

| Item | Value |
|---|---|
| Total accepted trips | 5,358,983 (2021-02-01 to 2026-10-31) |
| Average trips per day | 2,556 |
| Busiest day | 2026-09-12, 4,815 trips |
| Member share / electric-bike share | 72.1% / 43.0% |
| Busiest hour, weekdays / weekends | 17:00 / 12:00 |
| Median trip, members / casual riders | 5.9 min / 9.3 min |
| Weekend share of trips, members / casual riders | 23.1% / 36.0% |
| Calendar days in the period with no trips at all | 2 of 2,099 |

| Year | Trips | Per day |
|---|---|---|
| 2021 (from February) | 618,101 | 1,856 |
| 2022 | 874,991 | 2,397 |
| 2023 | 965,200 | 2,644 |
| 2024 | 1,044,742 | 2,854 |
| 2025 | 1,002,341 | 2,746 |
| 2026 (to October) | 853,608 | 2,817 |

| Top start stations | Trips started |
|---|---|
| 1. Grove St PATH (Jersey City) | 175,616 |
| 2. Hoboken Terminal - River St & Hudson Pl (Hoboken) | 164,190 |
| 3. Hoboken Terminal - Hudson St & Hudson Pl (Hoboken) | 146,566 |
| 4. South Waterfront Walkway - Sinatra Dr & 1 St (Hoboken) | 145,388 |
| 5. Hamilton Park (Jersey City) | 121,934 |

| Area | Stations | Trips started | Trips ended |
|---|---|---|---|
| Jersey City | 86 | 2,987,874 | 2,957,511 |
| Hoboken | 39 | 2,370,625 | 2,372,613 |
| Outside JC/Hoboken | 854 | 484 | 12,164 |

### Weather impact (ridership index: 1.0 = a normal day for that month)

| Group | Days | Index |
|---|---|---|
| Dry days | 1,363 | 1.07 |
| Wet days (1 mm or more) | 736 | 0.87 |
| Dry and freezing | 163 | 0.88 |
| Dry and cold | 398 | 1.093 |
| Dry and mild | 409 | 1.113 |
| Dry and warm | 342 | 1.088 |
| Dry and hot | 51 | 1.042 |

## Phase 5 — orchestration (Databricks Job defined in Terraform)

| Item | Value | Source |
|---|---|---|
| Unit tests passing | Pending (41 in the suite) | `pytest` on the Mac |
| Terraform resources created | Pending | `terraform apply` |
| Job tasks | 5 (2 landing, 2 bronze, 1 dbt build) | `infra/terraform/main.tf` |
| First job run: result | Pending | `python scripts/job_run_summary.py` |
| First job run: total duration | Pending | `python scripts/job_run_summary.py` |
| Duration per task | Pending | `python scripts/job_run_summary.py` |
