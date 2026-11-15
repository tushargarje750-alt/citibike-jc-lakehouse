# Design decisions

Short record of choices that shaped the project, and why.

| ID | Decision | Why | Status |
|---|---|---|---|
| D1 | Download source files **inside** the Databricks job (land → bronze → dbt build). | An egress test on 2026-11-14 showed the workspace can reach both the Citi Bike S3 bucket and the Open-Meteo archive API. Keeps the whole pipeline in one scheduled job. Landing code stays plain Python so it can run elsewhere if the Free Edition allowlist changes. | Accepted |
| D2 | Define the job in **Terraform** (Databricks provider) from the start, rather than building it in the UI first. Fallback: Databricks Asset Bundles. | One source of truth for the job; avoids building it twice. Terraform state stays local; CI only runs `fmt` and `validate`. | Proposed |
| D3 | **dbt Core 1.12 + dbt-databricks 1.13**, not dbt v2. | v1 is what the Databricks dbt job task installs by default (`dbt-databricks>=1.0.0,<2.0.0`); v2 only reached general availability in September 2026. | Proposed |
| D4 | Core scope is the **newer trip file format** (`ride_id`, `member_casual`, …). The older format (`tripduration`, `birth year`, …) is a stretch goal. | Two incompatible schemas; the exact switch-over month is verified from file headers in Phase 1. | Proposed |
| D5 | Find files by **listing the bucket and parsing the month with a regex**, never by building URLs. | File names are inconsistent: one has a space, one is misspelled, four omit `.csv` (see metrics log). | Accepted |
| D6 | Secrets only in environment variables: a git-ignored `.env` locally, GitHub Actions secrets in CI. The token variable uses dbt's `DBT_ENV_SECRET_` prefix so dbt masks it in logs. | Public repo; `profiles.yml` can be committed safely. | Accepted |
