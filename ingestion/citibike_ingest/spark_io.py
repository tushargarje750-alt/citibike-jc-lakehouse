"""The only module that talks to Spark: reads and updates the landing manifest table.

The manifest is a Delta table with one row per source file. It is what makes the
landing step incremental: a file whose key and ETag are already in the manifest
is not downloaded again.
"""
from __future__ import annotations

MANIFEST_COLUMNS = [
    ("source_key", "STRING"),
    ("month", "STRING"),
    ("source_size_bytes", "BIGINT"),
    ("source_etag", "STRING"),
    ("source_last_modified", "TIMESTAMP"),
    ("name_issue", "STRING"),
    ("zip_path", "STRING"),
    ("zip_sha256", "STRING"),
    ("csv_paths", "ARRAY<STRING>"),
    ("csv_member_names", "ARRAY<STRING>"),
    ("csv_bytes", "BIGINT"),
    ("schema_version", "STRING"),
    ("column_count", "INT"),
    ("header_signature", "STRING"),
    ("data_rows", "BIGINT"),
    ("landed_at", "TIMESTAMP"),
    ("run_id", "STRING"),
]
MANIFEST_DDL = ", ".join(f"{name} {dtype}" for name, dtype in MANIFEST_COLUMNS)


def ensure_manifest(spark, table: str) -> None:
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({MANIFEST_DDL})")


def read_landed(spark, table: str) -> dict[str, str]:
    """source_key -> ETag for everything landed so far."""
    rows = spark.table(table).select("source_key", "source_etag").collect()
    return {row["source_key"]: row["source_etag"] for row in rows}


def upsert_manifest(spark, table: str, records: list[dict]) -> int:
    """Insert new files and overwrite the row of any republished file (matched on source_key)."""
    if not records:
        return 0
    names = [name for name, _ in MANIFEST_COLUMNS]
    rows = [tuple(record[name] for name in names) for record in records]
    updates = spark.createDataFrame(rows, schema=MANIFEST_DDL)
    updates.createOrReplaceTempView("citibike_landing_updates")
    spark.sql(f"""
        MERGE INTO {table} AS t
        USING citibike_landing_updates AS s
        ON t.source_key = s.source_key
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    return len(rows)
