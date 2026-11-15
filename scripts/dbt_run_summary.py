#!/usr/bin/env python3
"""Summarise a dbt run from target/run_results.json.

Usage:
    python scripts/dbt_run_summary.py dbt/target/run_results.json

Prints how many models were built, how many tests passed, warned or failed,
how long the run took, and the slowest steps. Used locally and by CI.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

KINDS = {
    "model": "models",
    "test": "data tests",
    "unit_test": "unit tests",
    "seed": "seeds",
    "snapshot": "snapshots",
}
GOOD = {"success", "pass"}
BAD = {"error", "fail", "runtime error"}


def kind_of(unique_id: str) -> str:
    return KINDS.get(unique_id.split(".", 1)[0], "other")


def summarize(run_results: dict) -> list[str]:
    results = run_results.get("results", [])
    by_kind: dict[str, Counter] = {}
    for result in results:
        by_kind.setdefault(kind_of(result["unique_id"]), Counter())[result["status"]] += 1

    total = len(results)
    good = sum(1 for r in results if r["status"] in GOOD)
    warned = sum(1 for r in results if r["status"] == "warn")
    bad = sum(1 for r in results if r["status"] in BAD)
    skipped = sum(1 for r in results if r["status"] in {"skipped", "no-op"})

    lines = [
        "===== DBT RUN SUMMARY (copy this block) =====",
        f"dbt version:    {run_results.get('metadata', {}).get('dbt_version', 'unknown')}",
        f"steps:          {total} ({good} ok, {warned} warn, {bad} failed, {skipped} skipped)",
    ]
    for label in ("models", "data tests", "unit tests", "seeds", "snapshots", "other"):
        if label in by_kind:
            detail = ", ".join(f"{count} {status}" for status, count in sorted(by_kind[label].items()))
            lines.append(f"{label + ':':<15} {sum(by_kind[label].values())} ({detail})")
    lines.append(f"total elapsed:  {round(run_results.get('elapsed_time', 0), 1)} s")

    slowest = sorted(results, key=lambda r: r.get("execution_time") or 0, reverse=True)[:5]
    if slowest:
        lines.append("slowest steps:")
        for result in slowest:
            name = result["unique_id"].split(".")[-1] if kind_of(result["unique_id"]) == "models" \
                else result["unique_id"].split(".", 2)[-1]
            lines.append(f"  {round(result.get('execution_time') or 0, 1):>6} s  {name[:70]}")

    problems = [r for r in results if r["status"] in BAD or r["status"] == "warn"]
    if problems:
        lines.append("warnings and failures:")
        for result in problems:
            message = (result.get("message") or "").strip().splitlines()[0:1]
            lines.append(f"  {result['status']:<6} {result['unique_id'].split('.', 2)[-1][:60]}"
                         + (f" - {message[0][:80]}" if message else ""))
    lines.append("=============================================")
    return lines


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "dbt/target/run_results.json"
    with open(path) as handle:
        print("\n".join(summarize(json.load(handle))))


if __name__ == "__main__":
    main()
