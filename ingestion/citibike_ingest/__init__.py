"""Ingestion helpers for the Citi Bike JC lakehouse.

The modules here are plain Python (no Spark, no Databricks imports) so they can be
unit-tested on a laptop and in CI. Only spark_io.py touches Spark.
"""
