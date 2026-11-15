#!/usr/bin/env python3
"""Print the result and timings of the latest run of the pipeline job.

Usage (from the repo root):

    python scripts/job_run_summary.py

It asks Terraform for the job id and the Databricks CLI for the run details.
Options: --job-id 123 (skip Terraform), --profile citibike, --run-id 456.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone


def latest_run_id(listing) -> int | None:
    """The CLI returns either a list of runs or an object with a 'runs' list."""
    runs = listing.get("runs", []) if isinstance(listing, dict) else listing
    return runs[0]["run_id"] if runs else None


def result_of(item: dict) -> str:
    """Result of a run or task, across the old ('state') and new ('status') API shapes."""
    state = item.get("state") or {}
    if state.get("result_state"):
        return state["result_state"]
    status = item.get("status") or {}
    code = (status.get("termination_details") or {}).get("code")
    return code or status.get("state") or state.get("life_cycle_state") or "UNKNOWN"


def duration_seconds(item: dict) -> float | None:
    """Wall-clock seconds for a run or task."""
    start, end = item.get("start_time"), item.get("end_time")
    if start and end and end > start:
        return round((end - start) / 1000, 1)
    if item.get("run_duration"):
        return round(item["run_duration"] / 1000, 1)
    parts = [item.get(k) or 0 for k in ("setup_duration", "execution_duration", "cleanup_duration")]
    return round(sum(parts) / 1000, 1) if any(parts) else None


def summarize(run: dict) -> list[str]:
    started = run.get("start_time")
    started_text = (
        datetime.fromtimestamp(started / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if started else "unknown"
    )
    tasks = sorted(run.get("tasks") or [], key=lambda t: t.get("start_time") or 0)
    succeeded = sum(1 for t in tasks if result_of(t) == "SUCCESS")

    lines = [
        "===== JOB RUN SUMMARY (copy this block) =====",
        f"job:            {run.get('run_name', 'unknown')}",
        f"run_id:         {run.get('run_id')}",
        f"trigger:        {run.get('trigger', 'unknown')}",
        f"started:        {started_text}",
        f"result:         {result_of(run)}",
        f"total duration: {duration_seconds(run)} s",
        f"tasks:          {succeeded} of {len(tasks)} succeeded",
    ]
    for task in tasks:
        lines.append(f"  {task.get('task_key', '?'):<16} {result_of(task):<10} {duration_seconds(task)} s")
    lines.append("=============================================")
    return lines


def _run(command: list[str]) -> str:
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(f"Command failed: {' '.join(command)}\n{done.stderr.strip()}")
    return done.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--job-id")
    parser.add_argument("--run-id")
    parser.add_argument("--profile", default="citibike")
    args = parser.parse_args()

    run_id = args.run_id
    if not run_id:
        job_id = args.job_id or _run(
            ["terraform", "-chdir=infra/terraform", "output", "-raw", "job_id"]
        ).strip()
        listing = json.loads(_run(
            ["databricks", "jobs", "list-runs", "--job-id", str(job_id), "--limit", "1",
             "-o", "json", "-p", args.profile]
        ) or "[]")
        run_id = latest_run_id(listing)
        if not run_id:
            sys.exit(f"Job {job_id} has no runs yet.")

    run = json.loads(_run(["databricks", "jobs", "get-run", str(run_id), "-o", "json", "-p", args.profile]))
    print("\n".join(summarize(run)))


if __name__ == "__main__":
    main()
