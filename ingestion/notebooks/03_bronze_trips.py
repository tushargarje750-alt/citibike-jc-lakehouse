# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Bronze: load trip CSVs into Delta
# MAGIC
# MAGIC Loads the landed CSV files of the **current** trip format into
# MAGIC `<catalog>.citibike_bronze.trips_raw` with **Auto Loader**.
# MAGIC
# MAGIC - Every column stays text, exactly as published. Cleaning happens in silver.
# MAGIC - Six metadata columns record where each row came from and when it was loaded.
# MAGIC - Auto Loader remembers the files it has loaded, so a second run adds nothing.
# MAGIC - After loading, row counts per month are compared with the counts taken at landing time.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")

# COMMAND ----------

import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

_here = os.getcwd()
for _candidate in (os.path.join(_here, ".."), _here, os.path.join(_here, "ingestion")):
    if os.path.isdir(os.path.join(_candidate, "citibike_ingest")):
        sys.path.insert(0, os.path.abspath(_candidate))
        break
else:
    raise RuntimeError(f"Cannot find the citibike_ingest folder from {_here}")

from citibike_ingest import bronze

# COMMAND ----------

catalog = dbutils.widgets.get("catalog").strip()
if not re.fullmatch(r"[A-Za-z0-9_]+", catalog):
    raise ValueError(f"Unexpected catalog name: {catalog!r}")

manifest = f"{catalog}.citibike_landing.tripdata_manifest"
source_dir = f"/Volumes/{catalog}/citibike_landing/raw/tripdata/csv/current/"

bronze_schema = f"{catalog}.citibike_bronze"
trips_table = f"{bronze_schema}.trips_raw"
log_table = f"{bronze_schema}.ingest_log"
checkpoint = f"/Volumes/{catalog}/citibike_bronze/checkpoints/trips_raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {bronze_schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {bronze_schema}.checkpoints")
spark.sql(bronze.trips_table_ddl(trips_table))
spark.sql(f"CREATE TABLE IF NOT EXISTS {log_table} ({bronze.INGEST_LOG_DDL})")
print(f"source:     {source_dir}\ntarget:     {trips_table}\ncheckpoint: {checkpoint}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Safety check: do the landed files have the columns this table expects?

# COMMAND ----------

signatures = [
    row["header_signature"]
    for row in spark.sql(
        f"SELECT DISTINCT header_signature FROM {manifest} WHERE schema_version = 'current'"
    ).collect()
]
if signatures != [bronze.CURRENT_HEADER_SIGNATURE]:
    raise RuntimeError(
        "Landed 'current' files do not all have the expected header.\n"
        f"expected: {bronze.CURRENT_HEADER_SIGNATURE}\nfound:    {signatures}"
    )
print("header check passed: every landed 'current' file has the expected 13 columns")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load new files

# COMMAND ----------

def _counts():
    row = spark.sql(
        f"SELECT count(*) AS n, count(DISTINCT _source_file) AS files FROM {trips_table}"
    ).collect()[0]
    return row["n"], row["files"]


run_id = uuid.uuid4().hex[:12]
rows_before, files_before = _counts()
started_at = datetime.now(timezone.utc)
started = time.time()

bronze.ingest_trips(spark, source_dir, trips_table, checkpoint, run_id)

duration_s = round(time.time() - started, 1)
finished_at = datetime.now(timezone.utc)
rows_after, files_after = _counts()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reconcile with the landing manifest

# COMMAND ----------

reconciliation = spark.sql(bronze.reconciliation_sql(trips_table, manifest))
reconciliation.createOrReplaceTempView("bronze_reconciliation")

check = spark.sql("""
    SELECT count(*)                                         AS months,
           sum(CASE WHEN difference <> 0 THEN 1 ELSE 0 END) AS months_mismatched,
           sum(landed_rows)                                 AS landed_rows,
           sum(bronze_rows)                                 AS bronze_rows
    FROM bronze_reconciliation
""").collect()[0]
months_mismatched = check["months_mismatched"] or 0

quality = spark.sql(f"""
    SELECT sum(CASE WHEN _rescued_data IS NOT NULL THEN 1 ELSE 0 END) AS rescued_rows,
           sum(CASE WHEN ride_id IS NULL OR ride_id = '' THEN 1 ELSE 0 END) AS blank_ride_id,
           count(DISTINCT _source_month) AS months,
           min(_source_month) AS first_month,
           max(_source_month) AS last_month
    FROM {trips_table}
""").collect()[0]
rescued_rows = quality["rescued_rows"] or 0

landing_runs = spark.sql(f"""
    SELECT run_id, count(*) AS files,
           round(unix_timestamp(max(landed_at)) - unix_timestamp(min(landed_at))) AS span_s
    FROM {manifest}
    GROUP BY run_id
    ORDER BY min(landed_at)
""").collect()

spark.sql(f"""
    INSERT INTO {log_table} VALUES (
        '{run_id}', '{trips_table}',
        TIMESTAMP'{started_at:%Y-%m-%d %H:%M:%S}', TIMESTAMP'{finished_at:%Y-%m-%d %H:%M:%S}',
        {duration_s}, {rows_before}, {rows_after}, {rows_after - rows_before},
        {files_before}, {files_after}, {months_mismatched}, {rescued_rows}
    )
""")

print("===== BRONZE TRIPS RUN SUMMARY (copy this block) =====")
print(f"run_id:                      {run_id}")
print(f"rows before / after:         {rows_before:,} / {rows_after:,}")
print(f"rows added this run:         {rows_after - rows_before:,}")
print(f"files before / after:        {files_before} / {files_after}")
print(f"load duration:               {duration_s} s")
print("----- table totals -----")
print(f"months in bronze:            {quality['months']} ({quality['first_month']}..{quality['last_month']})")
print(f"rows counted at landing:     {(check['landed_rows'] or 0):,}")
print(f"rows in bronze:              {(check['bronze_rows'] or 0):,}")
print(f"months with a row mismatch:  {months_mismatched} of {check['months']}")
print(f"rows with rescued data:      {rescued_rows:,}")
print(f"rows with blank ride_id:     {(quality['blank_ride_id'] or 0):,}")
print("----- landing runs recorded in the manifest -----")
for row in landing_runs:
    print(f"landing run {row['run_id']}: {row['files']} files, first-to-last file {int(row['span_s'] or 0)} s")
print("=======================================================")

# COMMAND ----------

# MAGIC %md
# MAGIC Months where bronze and landing disagree (empty when everything reconciles):

# COMMAND ----------

display(spark.sql("SELECT * FROM bronze_reconciliation WHERE difference <> 0 ORDER BY month"))

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {log_table} ORDER BY started_at DESC"))

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {trips_table} LIMIT 5"))

# COMMAND ----------

# Fail the run (and the job task) if bronze does not match what was landed.
if months_mismatched:
    raise RuntimeError(f"{months_mismatched} month(s) have a different row count in bronze than at landing")
