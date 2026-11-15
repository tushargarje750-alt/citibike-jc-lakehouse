# Resume bullets and portfolio card

Everything here is backed by a number in [metrics_log.md](metrics_log.md). If a number
changes after a later run, update both files together.

## Resume bullets

**Citi Bike Lakehouse Pipeline** | Databricks, Delta Lake, dbt, Terraform, GitHub Actions, Python, SQL

- Built an incremental medallion pipeline on Databricks and Delta Lake that lands 134 monthly
  Citi Bike files (7.1M rows) plus 4,088 days of weather data, loads 5.4M trips with Auto Loader,
  and reconciles row counts for all 69 months against a manifest table with 0 mismatches.
- Modelled silver and gold layers in dbt (13 models, 73 data tests, 1 unit test, 2 custom generic
  tests) with an incremental merge on ride ID; quarantined 67,462 invalid rows (1.24%) under named
  rules while a reconciliation test accounts for 100% of bronze rows.
- Automated the pipeline as a 5-task Databricks job defined in Terraform (201 s end to end) and
  added GitHub Actions CI that runs 53 unit tests, Terraform validation and a full dbt build
  (87 steps in 71 s) on every push, with dbt docs auto-published and a dashboard deployed as code.

### Shorter variants (one line each)

- Built an incremental Databricks lakehouse (Delta Lake, Auto Loader) for 5.4M Citi Bike trips with manifest-based change detection and 0 row-count mismatches across 69 monthly loads.
- Developed 13 dbt models with 74 tests; quarantined 1.24% of rows by named rule with every bronze row accounted for.
- Defined a 5-task Databricks job and a dashboard in Terraform; GitHub Actions runs unit tests and a full dbt build on every push.

## Portfolio card

**Title:** Citi Bike Jersey City & Hoboken — Lakehouse Pipeline

**One-line summary:** An end-to-end Databricks lakehouse that turns 5.4 million public bike trips
and daily weather into tested analytics tables, with the job, the dashboard and CI all defined as code.

**Highlights:**

- Incremental ingestion of 134 monthly files with Auto Loader and a manifest table; a second run loads nothing, and bronze matches landing for all 69 months.
- dbt silver and gold layers with 13 models and 74 tests; 67,462 bad rows (1.24%) quarantined with a reason, none dropped silently.
- A 5-task Databricks job and a dashboard (4 KPI tiles, 6 charts) deployed with Terraform; the full pipeline runs in 201 seconds.
- GitHub Actions runs 53 unit tests, Terraform validation and a real dbt build on every push, and publishes the dbt docs site.

**Tech stack:** Databricks · Delta Lake · Auto Loader · dbt · Terraform · GitHub Actions · Python · SQL

**Links:**
- Code: https://github.com/tushargarje750-alt/citibike-jc-lakehouse
- dbt docs and lineage: https://tushargarje750-alt.github.io/citibike-jc-lakehouse/

**Finding worth mentioning in an interview:** wet days carry about a fifth fewer trips than dry
days in the same month (ridership index 0.87 against 1.07), measured after removing the system's
year-over-year growth.
