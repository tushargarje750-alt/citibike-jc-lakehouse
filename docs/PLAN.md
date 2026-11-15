# Project plan

## Architecture

```
 s3://tripdata (JC-*.zip)        Open-Meteo archive API
            │                            │
┌───────────┴──── Databricks Job (scheduled, defined in Terraform) ────┴──────────┐
│ Task 1  LAND    list bucket → download only new months → store files as-is     │
│                 in a Unity Catalog Volume                                       │
│ Task 2  BRONZE  unzip → Auto Loader → Delta tables + ingestion metadata         │
│ Task 3  dbt build                                                               │
│                 SILVER: typed, deduplicated, bad rows quarantined, weather join │
│                 GOLD:   6 analytics marts, all tests                            │
└─────────────────────────────────────────────────────────────────────────────────┘
            │
 AI/BI dashboard (SQL warehouse)          GitHub Actions CI on every push / PR
```

## Phases

| # | Milestone | Deliverable at the end |
|---|---|---|
| 0 | Setup | Workspace, CLI, GitHub repo, local dbt connected (`dbt debug` passes) |
| 1 | Landing + data discovery | Notebook that finds all JC files and lands only new months in a Volume; weather JSON; report of which months use which file format |
| 2 | Bronze (Delta Lake) | `trips_raw` and `weather_daily` with ingestion metadata; incremental loads; ingest log |
| 3 | Silver (dbt) | Sources, staging models, incremental merge on `ride_id`, quarantine table, station dimension, weather joined; generic + custom tests |
| 4 | Gold (dbt) + docs | 6 marts: daily ridership, top stations, peak hours, member vs casual, weather impact, trip-duration stats; dbt docs site |
| 5 | Orchestration as code | Terraform-defined Databricks Job (land → bronze → dbt build) on a schedule |
| 6 | CI | GitHub Actions runs `dbt build` on a one-month slice in a separate schema on every push / PR |
| 7 | Dashboard | AI/BI dashboard with 4–6 charts, exported to the repo, plus screenshots |
| 8 | Write-up | Final README, resume bullets, portfolio card |

## Repo layout

```
.github/workflows/     CI (Phase 6)
ingestion/notebooks/   landing + bronze notebooks (Phases 1–2)
ingestion/citibike_ingest/  plain-Python ingestion logic used by the notebooks
tests/                 unit tests for the ingestion logic (no Databricks needed)
dbt/                   dbt project: staging / intermediate / marts (Phases 3–4)
infra/terraform/       job definition as code (Phase 5)
dashboards/            exported dashboard JSON (Phase 7)
scripts/               helper scripts
docs/                  plan, decisions, metrics log, screenshots
```

## Free Edition limits this design works around

- Serverless compute only; one SQL warehouse, 2X-Small.
- At most 5 concurrent job tasks per account.
- A daily usage quota: going over it stops compute for the rest of the day. CI therefore runs
  on a one-month slice, not the full history.
- Outbound internet is restricted to an unpublished allowlist. Both data sources were tested
  and are reachable (see docs/metrics_log.md), but that could change, so the landing code is
  plain Python that can also run outside Databricks.
