# Citi Bike Jersey City & Hoboken — Lakehouse Pipeline

An end-to-end data engineering project on **Databricks Free Edition**: public Citi Bike trip data
for Jersey City and Hoboken, plus daily weather, moved through a bronze → silver → gold
(medallion) architecture on **Delta Lake**, transformed and tested with **dbt**, orchestrated by a
**Databricks Job**, and checked by **GitHub Actions CI**.

> **Status:** Phases 0–1 complete (setup, landing); Phase 2 (bronze) in progress. The full README, with architecture diagram, results and
> screenshots, is written in Phase 8 once the numbers exist.

- Plan and phases: [docs/PLAN.md](docs/PLAN.md)
- Design decisions: [docs/decisions.md](docs/decisions.md)
- Measured numbers (no estimates): [docs/metrics_log.md](docs/metrics_log.md)

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then fill in host, HTTP path and token
source scripts/activate.sh    # once per terminal window
cd dbt && dbt debug           # expect: All checks passed!
```

## Tests

```bash
pytest        # unit tests for the ingestion logic; no Databricks connection needed
```
