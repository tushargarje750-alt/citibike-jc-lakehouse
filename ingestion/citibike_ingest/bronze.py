"""Bronze layer: load landed CSV files into a Delta table, unchanged, with ingestion metadata.

Uses Auto Loader (the "cloudFiles" source). Auto Loader keeps a checkpoint of every
file it has already loaded, so each run picks up only files that are new since the
last run. Every column is kept as text exactly as it appears in the file; typing and
cleaning happen later, in the silver layer.

pyspark is imported inside the functions so the rest of the package stays importable
on a machine without Spark.
"""
from __future__ import annotations

# Column order of the current trip file format (February 2021 onwards).
CURRENT_COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]
CURRENT_HEADER_SIGNATURE = "|".join(CURRENT_COLUMNS)

METADATA_COLUMNS = [
    ("_rescued_data", "STRING", "Anything in a row that did not fit the expected columns"),
    ("_source_file", "STRING", "Full path of the CSV the row came from"),
    ("_source_month", "STRING", "yyyymm taken from the file name"),
    ("_source_file_modified_at", "TIMESTAMP", "Modification time of the CSV when it was read"),
    ("_ingested_at", "TIMESTAMP", "When the row was loaded into bronze"),
    ("_ingest_run_id", "STRING", "Identifier of the bronze run that loaded the row"),
]


def trips_table_ddl(table: str) -> str:
    data = [f"{name} STRING" for name in CURRENT_COLUMNS]
    meta = [f"{name} {dtype} COMMENT '{comment}'" for name, dtype, comment in METADATA_COLUMNS]
    return (
        f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(data + meta)}) "
        "CLUSTER BY (_source_month) "
        "COMMENT 'Citi Bike JC trips exactly as published (all text), plus ingestion metadata'"
    )


INGEST_LOG_DDL = (
    "run_id STRING, target_table STRING, started_at TIMESTAMP, finished_at TIMESTAMP, "
    "duration_s DOUBLE, rows_before BIGINT, rows_after BIGINT, rows_added BIGINT, "
    "files_before BIGINT, files_after BIGINT, months_mismatched BIGINT, rescued_rows BIGINT"
)


def ingest_trips(spark, source_dir: str, table: str, checkpoint: str, run_id: str,
                 source_format: str = "cloudFiles") -> None:
    """Load every CSV in source_dir that the checkpoint has not seen yet, then stop."""
    from pyspark.sql import functions as F

    reader = (
        spark.readStream.format(source_format)
        .option("header", "true")
        .schema(", ".join(f"{name} STRING" for name in CURRENT_COLUMNS))
    )
    if source_format == "cloudFiles":
        reader = (
            reader.option("cloudFiles.format", "csv")
            # A republished month overwrites its CSV; load the new version too.
            .option("cloudFiles.allowOverwrites", "true")
            .option("rescuedDataColumn", "_rescued_data")
        )
    raw = reader.load(source_dir)

    rescued = (
        F.col("_rescued_data") if "_rescued_data" in raw.columns
        else F.lit(None).cast("string").alias("_rescued_data")
    )
    bronze = raw.select(
        *[F.col(name) for name in CURRENT_COLUMNS],
        rescued,
        F.col("_metadata.file_path").alias("_source_file"),
        F.regexp_extract(F.col("_metadata.file_name"), r"JC-(\d{6})", 1).alias("_source_month"),
        F.col("_metadata.file_modification_time").alias("_source_file_modified_at"),
        F.current_timestamp().alias("_ingested_at"),
        F.lit(run_id).alias("_ingest_run_id"),
    )

    query = (
        bronze.writeStream
        .option("checkpointLocation", checkpoint)
        .trigger(availableNow=True)   # process what is there, then stop
        .toTable(table)
    )
    query.awaitTermination()


def reconciliation_sql(bronze_table: str, manifest_table: str) -> str:
    """Rows per month in bronze vs. rows counted at landing time (the control total).

    If a month was republished and loaded twice, only its newest file version is counted.
    """
    return f"""
        WITH versions AS (
            SELECT _source_month AS month, _source_file, _source_file_modified_at,
                   max(_source_file_modified_at) OVER (PARTITION BY _source_file) AS newest
            FROM {bronze_table}
        ),
        bronze AS (
            SELECT month, count(*) AS bronze_rows
            FROM versions
            WHERE _source_file_modified_at = newest
            GROUP BY month
        ),
        landed AS (
            SELECT month, data_rows AS landed_rows
            FROM {manifest_table}
            WHERE schema_version = 'current'
        )
        SELECT coalesce(l.month, b.month)                              AS month,
               l.landed_rows,
               b.bronze_rows,
               coalesce(b.bronze_rows, 0) - coalesce(l.landed_rows, 0) AS difference
        FROM landed l
        FULL OUTER JOIN bronze b ON l.month = b.month
    """
