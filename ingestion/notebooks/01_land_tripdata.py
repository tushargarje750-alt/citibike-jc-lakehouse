# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Land Citi Bike Jersey City trip files
# MAGIC
# MAGIC Lists the public `tripdata` bucket, downloads **only the months that are new or republished**,
# MAGIC and stores them in a Unity Catalog Volume:
# MAGIC
# MAGIC | Where | What |
# MAGIC |---|---|
# MAGIC | `/Volumes/<catalog>/citibike_landing/raw/tripdata/zip/` | each monthly zip, byte-for-byte as published |
# MAGIC | `/Volumes/<catalog>/citibike_landing/raw/tripdata/csv/<format>/` | the CSV extracted from it, grouped by file format |
# MAGIC | `<catalog>.citibike_landing.tripdata_manifest` | one row per file: size, checksum, header, row count |
# MAGIC
# MAGIC Run it twice: the second run should land nothing. That is the incremental behaviour.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("min_month", "", "First month to land (yyyymm, blank = all)")
dbutils.widgets.text("max_files", "0", "Max files this run (0 = no limit)")

# COMMAND ----------

import os
import re
import sys

# Make the shared code in ingestion/citibike_ingest importable from this notebook.
_here = os.getcwd()
for _candidate in (os.path.join(_here, ".."), _here, os.path.join(_here, "ingestion")):
    if os.path.isdir(os.path.join(_candidate, "citibike_ingest")):
        sys.path.insert(0, os.path.abspath(_candidate))
        break
else:
    raise RuntimeError(f"Cannot find the citibike_ingest folder from {_here}")

from citibike_ingest import landing, spark_io

# COMMAND ----------

catalog = dbutils.widgets.get("catalog").strip()
min_month = dbutils.widgets.get("min_month").strip() or None
max_files = int(dbutils.widgets.get("max_files").strip() or 0)

if not re.fullmatch(r"[A-Za-z0-9_]+", catalog):
    raise ValueError(f"Unexpected catalog name: {catalog!r}")
if min_month and not re.fullmatch(r"\d{6}", min_month):
    raise ValueError("min_month must look like 202102")

schema = f"{catalog}.citibike_landing"
manifest = f"{schema}.tripdata_manifest"
volume_root = f"/Volumes/{catalog}/citibike_landing/raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {schema}.raw")
spark_io.ensure_manifest(spark, manifest)
print(f"landing volume: {volume_root}\nmanifest table: {manifest}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Land new files

# COMMAND ----------

already_landed = spark_io.read_landed(spark, manifest)
result = landing.land_new_files(
    volume_root=volume_root,
    already_landed=already_landed,
    min_month=min_month,
    max_files=max_files,
)
spark_io.upsert_manifest(spark, manifest, result.records)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run summary
# MAGIC Copy the block below into `docs/metrics_log.md` (or send it to whoever keeps the log).

# COMMAND ----------

by_format = spark.sql(f"""
    SELECT schema_version,
           count(*)               AS months,
           min(month)             AS first_month,
           max(month)             AS last_month,
           sum(data_rows)         AS data_rows,
           sum(source_size_bytes) AS zip_bytes,
           sum(csv_bytes)         AS csv_bytes
    FROM {manifest}
    GROUP BY schema_version
    ORDER BY first_month
""").collect()

overall = spark.sql(f"""
    SELECT count(*) AS months, min(month) AS first_month, max(month) AS last_month,
           sum(data_rows) AS data_rows, sum(source_size_bytes) AS zip_bytes, sum(csv_bytes) AS csv_bytes,
           count(DISTINCT header_signature) AS header_variants,
           count(name_issue) AS name_issues,
           collect_list(month) AS month_list
    FROM {manifest}
""").collect()[0]


def _months_between(first: str, last: str) -> list:
    year, month, out = int(first[:4]), int(first[4:]), []
    while f"{year}{month:02d}" <= last:
        out.append(f"{year}{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


missing_months = []
if overall["months"]:
    missing_months = sorted(set(_months_between(overall["first_month"], overall["last_month"]))
                            - set(overall["month_list"]))

mb = lambda b: f"{(b or 0) / 1_000_000:,.1f} MB"

print("===== LANDING RUN SUMMARY (copy this block) =====")
print(f"run_id:                    {result.run_id}")
print(f"JC files in bucket:        {result.files_in_bucket}")
print(f"already landed (skipped):  {result.already_landed}")
print(f"landed this run:           {len(result.records)}")
print(f"failed this run:           {len(result.failures)}")
print(f"ignored keys:              {len(result.ignored_keys)} {result.ignored_keys or ''}")
print(f"zip size this run:         {mb(result.zip_bytes)}")
print(f"data rows this run:        {result.data_rows:,}")
print(f"landing duration:          {result.seconds} s")
print("----- manifest totals (everything landed so far) -----")
print(f"months landed:             {overall['months']} ({overall['first_month']}..{overall['last_month']})")
print(f"missing months in range:   {len(missing_months)} "
      f"{(missing_months[:12] + ['...']) if len(missing_months) > 12 else (missing_months or '')}")
print(f"data rows:                 {(overall['data_rows'] or 0):,}")
print(f"zip size / csv size:       {mb(overall['zip_bytes'])} / {mb(overall['csv_bytes'])}")
print(f"distinct header variants:  {overall['header_variants']}")
print(f"odd file names:            {overall['name_issues']}")
for row in by_format:
    print(f"format {row['schema_version']:<8} {row['months']:>3} months "
          f"({row['first_month']}..{row['last_month']}), {row['data_rows']:,} rows")
print("==================================================")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data discovery
# MAGIC Which months use which file format, and which header variants exist.

# COMMAND ----------

display(spark.sql(f"""
    SELECT schema_version, column_count, header_signature,
           count(*) AS months, min(month) AS first_month, max(month) AS last_month,
           sum(data_rows) AS data_rows
    FROM {manifest}
    GROUP BY schema_version, column_count, header_signature
    ORDER BY first_month
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT month, source_key, name_issue
    FROM {manifest}
    WHERE name_issue IS NOT NULL
    ORDER BY month
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT month, schema_version, data_rows, source_size_bytes, csv_bytes,
           source_last_modified, landed_at, run_id
    FROM {manifest}
    ORDER BY month
"""))

# COMMAND ----------

# Fail the run (and therefore the job task) if any file could not be landed.
# Files that did land are already recorded; the failed ones are retried next run.
if result.failures:
    for key, error in result.failures:
        print(f"FAILED {key}: {error}")
    raise RuntimeError(f"{len(result.failures)} file(s) failed to land")
