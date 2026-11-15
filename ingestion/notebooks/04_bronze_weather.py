# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Bronze: daily weather into Delta
# MAGIC
# MAGIC Reads the landed Open-Meteo year files and writes one row per day to
# MAGIC `<catalog>.citibike_bronze.weather_daily_raw`.
# MAGIC
# MAGIC Values and units stay as delivered (°C, mm, cm of snow, km/h). The table is small
# MAGIC (a few thousand rows), so every run rebuilds it completely from the landed files.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Catalog")

# COMMAND ----------

import json
import os
import re
import sys
import time

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
if not re.fullmatch(r"[A-Za-z0-9_]+", catalog):
    raise ValueError(f"Unexpected catalog name: {catalog!r}")

weather_dir = f"/Volumes/{catalog}/citibike_landing/raw/weather"
bronze_schema = f"{catalog}.citibike_bronze"
weather_table = f"{bronze_schema}.weather_daily_raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {bronze_schema}")

# COMMAND ----------

started = time.time()
rows, files = [], 0
for name in sorted(os.listdir(weather_dir)):
    if not name.endswith(".json"):
        continue
    path = os.path.join(weather_dir, name)
    with open(path, "rb") as handle:
        rows.extend(weather.flatten_daily(json.load(handle), path))
    files += 1

if not rows:
    raise RuntimeError(f"No weather files found in {weather_dir}. Run 02_land_weather first.")

dates = [row[0] for row in rows]
if len(dates) != len(set(dates)):
    raise RuntimeError("The landed weather files contain the same day more than once")

(
    spark.createDataFrame(rows, schema=weather.WEATHER_ROW_DDL)
    .selectExpr("*", "current_timestamp() AS _ingested_at")
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(weather_table)
)
duration_s = round(time.time() - started, 1)

# COMMAND ----------

stats = spark.sql(f"""
    SELECT count(*) AS days, count(DISTINCT date) AS distinct_days,
           min(date) AS first_day, max(date) AS last_day,
           sum(CASE WHEN temperature_2m_mean IS NULL THEN 1 ELSE 0 END) AS missing_temperature,
           sum(CASE WHEN precipitation_sum IS NULL THEN 1 ELSE 0 END)   AS missing_precipitation,
           round(min(temperature_2m_min), 1) AS coldest_c,
           round(max(temperature_2m_max), 1) AS warmest_c,
           sum(CASE WHEN precipitation_sum > 0 THEN 1 ELSE 0 END) AS days_with_precipitation,
           sum(CASE WHEN snowfall_sum > 0 THEN 1 ELSE 0 END)      AS days_with_snow
    FROM {weather_table}
""").collect()[0]

print("===== BRONZE WEATHER RUN SUMMARY (copy this block) =====")
print(f"year files read:             {files}")
print(f"rows written:                {stats['days']:,} ({stats['first_day']}..{stats['last_day']})")
print(f"distinct days:               {stats['distinct_days']:,}")
print(f"days without temperature:    {stats['missing_temperature']}")
print(f"days without precipitation:  {stats['missing_precipitation']}")
print(f"coldest / warmest (°C):      {stats['coldest_c']} / {stats['warmest_c']}")
print(f"days with precipitation:     {stats['days_with_precipitation']:,}")
print(f"days with snowfall:          {stats['days_with_snow']:,}")
print(f"duration:                    {duration_s} s")
print("=========================================================")

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {weather_table} ORDER BY date DESC LIMIT 10"))
