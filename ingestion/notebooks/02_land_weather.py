# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Land daily weather (Open-Meteo archive)
# MAGIC
# MAGIC Fetches daily weather for Jersey City / Hoboken and stores each API response unchanged,
# MAGIC one JSON file per year, in `/Volumes/<catalog>/citibike_landing/raw/weather/`.
# MAGIC
# MAGIC Finished years are fetched once. The current year is fetched again on every run.
# MAGIC
# MAGIC Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")
dbutils.widgets.text("first_day", "2015-09-01", "First day (first month of JC trip data)")

# COMMAND ----------

import json
import os
import re
import sys
from datetime import date

_here = os.getcwd()
for _candidate in (os.path.join(_here, ".."), _here, os.path.join(_here, "ingestion")):
    if os.path.isdir(os.path.join(_candidate, "citibike_ingest")):
        sys.path.insert(0, os.path.abspath(_candidate))
        break
else:
    raise RuntimeError(f"Cannot find the citibike_ingest folder from {_here}")

from citibike_ingest import weather

# COMMAND ----------

catalog = dbutils.widgets.get("catalog").strip()
first_day = date.fromisoformat(dbutils.widgets.get("first_day").strip())

if not re.fullmatch(r"[A-Za-z0-9_]+", catalog):
    raise ValueError(f"Unexpected catalog name: {catalog!r}")

schema = f"{catalog}.citibike_landing"
volume_root = f"/Volumes/{catalog}/citibike_landing/raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {schema}.raw")
print(f"landing volume: {volume_root}")

# COMMAND ----------

result = weather.land_weather(volume_root=volume_root, first_day=first_day)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run summary

# COMMAND ----------

# Totals across every year file now in the volume (not only the ones fetched in this run).
weather_dir = f"{volume_root}/weather"
total_files, total_days, total_missing, total_bytes, first_date, last_date = 0, 0, 0, 0, None, None
for name in sorted(os.listdir(weather_dir)) if os.path.isdir(weather_dir) else []:
    if not name.endswith(".json"):
        continue
    path = os.path.join(weather_dir, name)
    with open(path, "rb") as handle:
        body = handle.read()
    daily = json.loads(body)["daily"]
    total_files += 1
    total_days += len(daily["time"])
    total_missing += sum(1 for v in daily["temperature_2m_mean"] if v is None)
    total_bytes += len(body)
    first_date = first_date or daily["time"][0]
    last_date = daily["time"][-1]

print("===== WEATHER RUN SUMMARY (copy this block) =====")
print(f"years fetched this run:    {len(result.records)} {[r['year'] for r in result.records]}")
print(f"years skipped (complete):  {len(result.skipped_years)}")
print(f"failed this run:           {len(result.failures)}")
print(f"days fetched this run:     {sum(r['days'] for r in result.records):,}")
print(f"duration:                  {result.seconds} s")
print("----- totals in the landing volume -----")
print(f"year files:                {total_files}")
print(f"days covered:              {total_days:,} ({first_date}..{last_date})")
print(f"days without temperature:  {total_missing}")
print(f"size:                      {total_bytes / 1000:,.1f} kB")
print(f"daily variables:           {len(weather.DAILY_VARIABLES)}")
print("=================================================")

# COMMAND ----------

display(spark.createDataFrame(result.records) if result.records else spark.sql("SELECT 'nothing fetched this run' AS note"))

# COMMAND ----------

if result.failures:
    for year, error in result.failures:
        print(f"FAILED {year}: {error}")
    raise RuntimeError(f"{len(result.failures)} year(s) failed to land")
