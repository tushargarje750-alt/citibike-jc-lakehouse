"""Landing step for Citi Bike Jersey City / Hoboken trip files.

What it does, in order:
  1. Lists the public S3 bucket and keeps the keys that look like JC monthly files.
  2. Skips files already landed with the same ETag (incremental load).
  3. Downloads each new zip and stores it unchanged in the landing volume.
  4. Extracts the CSV(s) next to it, grouped by file format, ready for Auto Loader.
  5. Returns one manifest record per file: sizes, checksum, header, row count.

File names in the bucket are not consistent (a space, a typo, missing ".csv"), so
months are parsed from a bucket listing with a regex; URLs are never guessed.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote, urlencode

from .http_util import http_get

BUCKET_URL = "https://s3.amazonaws.com/tripdata"
KEY_PREFIX = "JC-"

# JC-<yyyymm><anything>.zip  -> month is captured even when the rest of the name is odd
JC_KEY_RE = re.compile(r"^JC-(\d{4})(0[1-9]|1[0-2])[^/]*\.zip$", re.IGNORECASE)
CANONICAL_KEY_RE = re.compile(r"^JC-\d{6}-citibike-tripdata\.csv\.zip$")

SCHEMA_CURRENT = "current"   # ride_id, rideable_type, started_at, ... member_casual
SCHEMA_LEGACY = "legacy"     # tripduration, starttime, ... birth year, gender
SCHEMA_UNKNOWN = "unknown"

Fetch = Callable[[str], bytes]


# --------------------------------------------------------------------------- listing

@dataclass(frozen=True)
class SourceFile:
    key: str
    month: str                    # yyyymm
    size_bytes: int
    etag: str
    last_modified: datetime
    name_issue: Optional[str]     # None when the name follows the usual pattern

    @property
    def url(self) -> str:
        return f"{BUCKET_URL}/{quote(self.key)}"


def name_issue(key: str) -> Optional[str]:
    """Describe how a key deviates from JC-yyyymm-citibike-tripdata.csv.zip (None if it doesn't)."""
    if CANONICAL_KEY_RE.match(key):
        return None
    issues = []
    if re.match(r"^JC-\d{6} ", key):
        issues.append("space_after_month")
    if "citibike" not in key.lower():
        issues.append("misspelled_citibike")
    if not key.lower().endswith(".csv.zip"):
        issues.append("missing_csv_suffix")
    return ",".join(issues) or "other"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_listing(xml_bytes: bytes) -> tuple[list[dict], Optional[str]]:
    """Parse one page of an S3 ListObjectsV2 response -> (objects, next continuation token)."""
    root = ET.fromstring(xml_bytes)
    objects, truncated, token = [], False, None
    for element in root:
        tag = _local(element.tag)
        if tag == "Contents":
            objects.append({_local(child.tag): (child.text or "") for child in element})
        elif tag == "IsTruncated":
            truncated = (element.text or "").strip().lower() == "true"
        elif tag == "NextContinuationToken":
            token = element.text
    return objects, (token if truncated else None)


def _parse_s3_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def list_source_files(fetch: Fetch = http_get) -> tuple[list[SourceFile], list[str]]:
    """List JC monthly files in the bucket.

    Returns (files, ignored_keys). If two keys exist for the same month, the most
    recently modified one wins and the other is reported in ignored_keys.
    """
    raw: list[dict] = []
    token: Optional[str] = None
    for _ in range(50):  # hard stop; the bucket has well under 1,000 JC keys
        params = {"list-type": "2", "prefix": KEY_PREFIX}
        if token:
            params["continuation-token"] = token
        page, token = parse_listing(fetch(f"{BUCKET_URL}?{urlencode(params)}"))
        raw.extend(page)
        if not token:
            break

    by_month: dict[str, SourceFile] = {}
    ignored: list[str] = []
    for obj in raw:
        key = obj.get("Key", "")
        match = JC_KEY_RE.match(key)
        if not match:
            if key.startswith(KEY_PREFIX):
                ignored.append(key)
            continue
        candidate = SourceFile(
            key=key,
            month=match.group(1) + match.group(2),
            size_bytes=int(obj.get("Size") or 0),
            etag=obj.get("ETag", "").strip('"'),
            last_modified=_parse_s3_time(obj["LastModified"]),
            name_issue=name_issue(key),
        )
        current = by_month.get(candidate.month)
        if current is None:
            by_month[candidate.month] = candidate
        elif candidate.last_modified > current.last_modified:
            ignored.append(current.key)
            by_month[candidate.month] = candidate
        else:
            ignored.append(candidate.key)
    return [by_month[m] for m in sorted(by_month)], ignored


def select_new(
    files: list[SourceFile],
    already_landed: dict[str, str],
    min_month: Optional[str] = None,
    max_files: int = 0,
) -> list[SourceFile]:
    """Files that still need landing: never seen, or seen with a different ETag (republished)."""
    todo = [
        f for f in files
        if (not min_month or f.month >= min_month) and already_landed.get(f.key) != f.etag
    ]
    return todo[:max_files] if max_files and max_files > 0 else todo


# --------------------------------------------------------------------------- inspecting

def normalize_header(header_line: str) -> list[str]:
    """'Start Station ID' -> 'start_station_id'; also strips a BOM and quotes."""
    cleaned = header_line.lstrip("﻿").strip()
    if not cleaned:
        return []
    columns = next(csv.reader([cleaned]))
    return [re.sub(r"\s+", "_", c.strip().strip('"').strip().lower()) for c in columns]


def classify_schema(columns: list[str]) -> str:
    squashed = {c.replace("_", "") for c in columns}
    if "rideid" in squashed and "membercasual" in squashed:
        return SCHEMA_CURRENT
    if "tripduration" in squashed and "usertype" in squashed:
        return SCHEMA_LEGACY
    return SCHEMA_UNKNOWN


@dataclass
class CsvMember:
    name: str
    data: bytes
    header_raw: str
    columns: list[str]
    schema_version: str
    data_rows: int


def _is_data_csv(name: str) -> bool:
    base = os.path.basename(name)
    return (
        name.lower().endswith(".csv")
        and not name.startswith("__MACOSX/")
        and not base.startswith("._")
    )


def read_csv_members(zip_bytes: bytes) -> list[CsvMember]:
    """Open a zip in memory and describe each real CSV inside it (Mac junk entries are ignored)."""
    members: list[CsvMember] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir() or not _is_data_csv(info.filename):
                continue
            data = archive.read(info)
            lines = io.BytesIO(data)
            header_raw = lines.readline().decode("utf-8-sig", "replace").rstrip("\r\n")
            data_rows = sum(1 for line in lines if line.strip())
            columns = normalize_header(header_raw)
            members.append(CsvMember(
                name=info.filename,
                data=data,
                header_raw=header_raw,
                columns=columns,
                schema_version=classify_schema(columns),
                data_rows=data_rows,
            ))
    if not members:
        raise ValueError("zip contains no CSV file")
    return members


# --------------------------------------------------------------------------- landing

def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def land_file(src: SourceFile, volume_root: str, fetch: Fetch, run_id: str, now: datetime) -> dict:
    """Download one zip, store it unchanged, extract its CSV(s), return its manifest record."""
    data = fetch(src.url)
    if src.size_bytes and len(data) != src.size_bytes:
        raise ValueError(f"size mismatch: listing says {src.size_bytes} bytes, downloaded {len(data)}")

    members = read_csv_members(data)
    versions = {m.schema_version for m in members}
    schema_version = versions.pop() if len(versions) == 1 else "mixed"

    zip_path = f"{volume_root}/tripdata/zip/JC-{src.month}.zip"
    _write(zip_path, data)

    # Remove CSVs from an earlier landing of the same month (a republished file may differ).
    for stale in glob.glob(f"{volume_root}/tripdata/csv/*/JC-{src.month}*.csv"):
        os.remove(stale)

    csv_paths = []
    for index, member in enumerate(members, start=1):
        suffix = "" if len(members) == 1 else f"_{index}"
        path = f"{volume_root}/tripdata/csv/{member.schema_version}/JC-{src.month}{suffix}.csv"
        _write(path, member.data)
        csv_paths.append(path)

    first = members[0]
    return {
        "source_key": src.key,
        "month": src.month,
        "source_size_bytes": src.size_bytes,
        "source_etag": src.etag,
        "source_last_modified": src.last_modified,
        "name_issue": src.name_issue,
        "zip_path": zip_path,
        "zip_sha256": hashlib.sha256(data).hexdigest(),
        "csv_paths": csv_paths,
        "csv_member_names": [m.name for m in members],
        "csv_bytes": sum(len(m.data) for m in members),
        "schema_version": schema_version,
        "column_count": len(first.columns),
        "header_signature": "|".join(first.columns),
        "data_rows": sum(m.data_rows for m in members),
        "landed_at": now,
        "run_id": run_id,
    }


@dataclass
class LandingResult:
    run_id: str
    files_in_bucket: int = 0
    ignored_keys: list[str] = field(default_factory=list)
    already_landed: int = 0
    selected: int = 0
    records: list[dict] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def zip_bytes(self) -> int:
        return sum(r["source_size_bytes"] for r in self.records)

    @property
    def data_rows(self) -> int:
        return sum(r["data_rows"] for r in self.records)


def land_new_files(
    volume_root: str,
    already_landed: dict[str, str],
    min_month: Optional[str] = None,
    max_files: int = 0,
    fetch: Fetch = http_get,
    log: Callable[[str], None] = print,
) -> LandingResult:
    """Land every file that is new or republished. One bad file never stops the others."""
    started = time.time()
    result = LandingResult(run_id=uuid.uuid4().hex[:12])

    files, result.ignored_keys = list_source_files(fetch)
    in_scope = [f for f in files if not min_month or f.month >= min_month]
    todo = select_new(files, already_landed, min_month, max_files)
    result.files_in_bucket = len(files)
    result.selected = len(todo)
    result.already_landed = sum(1 for f in in_scope if already_landed.get(f.key) == f.etag)

    log(f"run {result.run_id}: {len(files)} JC files in bucket, "
        f"{result.already_landed} already landed, {len(todo)} to land")

    for position, src in enumerate(todo, start=1):
        try:
            record = land_file(src, volume_root, fetch, result.run_id, datetime.now(timezone.utc))
            result.records.append(record)
            log(f"[{position:>3}/{len(todo)}] {src.month}  {src.size_bytes:>9,} bytes  "
                f"{record['data_rows']:>8,} rows  {record['schema_version']}"
                + (f"  (name: {src.name_issue})" if src.name_issue else ""))
        except Exception as err:  # noqa: BLE001 - report and continue with the next file
            result.failures.append((src.key, f"{type(err).__name__}: {err}"))
            log(f"[{position:>3}/{len(todo)}] {src.month}  FAILED  {type(err).__name__}: {err}")

    result.seconds = round(time.time() - started, 1)
    return result
