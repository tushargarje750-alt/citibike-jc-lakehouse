import os

import pytest

from citibike_ingest import landing
from conftest import CURRENT_HEADER, LEGACY_HEADER, FakeBucket, csv_text, make_zip


# ----------------------------------------------------------------- file names

@pytest.mark.parametrize("key, month, issue", [
    ("JC-202309-citibike-tripdata.csv.zip", "202309", None),
    ("JC-201708 citibike-tripdata.csv.zip", "201708", "space_after_month"),
    ("JC-202207-citbike-tripdata.csv.zip", "202207", "misspelled_citibike"),
    ("JC-202510-citibike-tripdata.zip", "202510", "missing_csv_suffix"),
])
def test_month_and_name_issue_are_parsed_from_real_world_names(key, month, issue):
    match = landing.JC_KEY_RE.match(key)
    assert match and match.group(1) + match.group(2) == month
    assert landing.name_issue(key) == issue


@pytest.mark.parametrize("key", [
    "202401-citibike-tripdata.zip",        # NYC file, not Jersey City
    "JC-202413-citibike-tripdata.csv.zip",  # month 13 does not exist
    "JC-2024-citibike-tripdata.zip",
    "index.html",
])
def test_non_jc_or_invalid_keys_are_not_matched(key):
    assert landing.JC_KEY_RE.match(key) is None


# ----------------------------------------------------------------- bucket listing

def test_listing_keeps_only_jc_files_sorted_by_month(bucket):
    files, ignored = landing.list_source_files(bucket.fetch)
    assert [f.month for f in files] == ["202012", "202102", "202207", "202610"]
    assert ignored == []
    assert files[0].etag and not files[0].etag.startswith('"')


def test_listing_follows_pagination():
    bucket = FakeBucket(page_size=2)
    for month in ("202101", "202102", "202103", "202104", "202105"):
        bucket.put(f"JC-{month}-citibike-tripdata.csv.zip", b"x")
    files, _ = landing.list_source_files(bucket.fetch)
    assert len(files) == 5


def test_two_keys_for_one_month_keeps_the_newest():
    bucket = FakeBucket()
    bucket.put("JC-202510-citibike-tripdata.csv.zip", b"old", last_modified="2025-11-01T00:00:00.000Z")
    bucket.put("JC-202510-citibike-tripdata.zip", b"new", last_modified="2025-11-04T00:00:00.000Z")
    files, ignored = landing.list_source_files(bucket.fetch)
    assert [f.key for f in files] == ["JC-202510-citibike-tripdata.zip"]
    assert ignored == ["JC-202510-citibike-tripdata.csv.zip"]


def test_download_url_encodes_spaces():
    bucket = FakeBucket()
    bucket.put("JC-201708 citibike-tripdata.csv.zip", b"x")
    files, _ = landing.list_source_files(bucket.fetch)
    assert files[0].url.endswith("/JC-201708%20citibike-tripdata.csv.zip")


# ----------------------------------------------------------------- incremental selection

def test_select_new_skips_same_etag_and_relands_changed_etag(bucket):
    files, _ = landing.list_source_files(bucket.fetch)
    already = {files[0].key: files[0].etag, files[1].key: "an-older-etag"}
    todo = landing.select_new(files, already)
    assert [f.month for f in todo] == ["202102", "202207", "202610"]


def test_select_new_honours_min_month_and_max_files(bucket):
    files, _ = landing.list_source_files(bucket.fetch)
    assert [f.month for f in landing.select_new(files, {}, min_month="202102")] == ["202102", "202207", "202610"]
    assert [f.month for f in landing.select_new(files, {}, max_files=1)] == ["202012"]


# ----------------------------------------------------------------- headers

def test_header_normalisation_and_schema_detection():
    current = landing.normalize_header(CURRENT_HEADER)
    legacy = landing.normalize_header(LEGACY_HEADER)
    assert current[0] == "ride_id" and len(current) == 13
    assert legacy[3] == "start_station_id" and len(legacy) == 15
    assert landing.classify_schema(current) == "current"
    assert landing.classify_schema(legacy) == "legacy"


def test_header_handles_bom_and_capitalised_legacy_names():
    cols = landing.normalize_header("﻿Trip Duration,Start Time,User Type")
    assert cols == ["trip_duration", "start_time", "user_type"]
    assert landing.classify_schema(cols) == "legacy"
    assert landing.classify_schema(["a", "b"]) == "unknown"


# ----------------------------------------------------------------- zip contents

def test_zip_inspection_ignores_mac_junk_and_counts_data_rows():
    data = make_zip({
        "JC-202102-citibike-tripdata.csv": csv_text(CURRENT_HEADER, 4) + "\n\n",  # trailing blank lines
        "__MACOSX/._JC-202102-citibike-tripdata.csv": "junk",
    })
    members = landing.read_csv_members(data)
    assert len(members) == 1
    assert members[0].data_rows == 4
    assert members[0].schema_version == "current"


def test_zip_without_csv_is_rejected():
    with pytest.raises(ValueError):
        landing.read_csv_members(make_zip({"readme.txt": "nothing here"}))


# ----------------------------------------------------------------- end to end

def test_first_run_lands_everything_unchanged(bucket, tmp_path):
    result = landing.land_new_files(str(tmp_path), {}, fetch=bucket.fetch, log=lambda _: None)

    assert result.files_in_bucket == 4 and result.selected == 4
    assert len(result.records) == 4 and result.failures == []
    assert result.data_rows == 3 + 5 + 7 + 2

    by_month = {r["month"]: r for r in result.records}
    assert by_month["202012"]["schema_version"] == "legacy"
    assert by_month["202102"]["schema_version"] == "current"
    assert by_month["202207"]["name_issue"] == "misspelled_citibike"

    # the zip is stored byte-for-byte, the CSV sits in a folder named after its format
    original = bucket.objects["JC-202102-citibike-tripdata.csv.zip"][0]
    with open(tmp_path / "tripdata/zip/JC-202102.zip", "rb") as handle:
        assert handle.read() == original
    assert os.path.exists(tmp_path / "tripdata/csv/current/JC-202102.csv")
    assert os.path.exists(tmp_path / "tripdata/csv/legacy/JC-202012.csv")


def test_second_run_lands_nothing(bucket, tmp_path):
    first = landing.land_new_files(str(tmp_path), {}, fetch=bucket.fetch, log=lambda _: None)
    already = {r["source_key"]: r["source_etag"] for r in first.records}
    downloads_before = len(bucket.downloads)

    second = landing.land_new_files(str(tmp_path), already, fetch=bucket.fetch, log=lambda _: None)

    assert second.selected == 0 and second.records == []
    assert second.already_landed == 4
    assert len(bucket.downloads) == downloads_before


def test_only_the_new_month_is_landed(bucket, tmp_path):
    first = landing.land_new_files(str(tmp_path), {}, fetch=bucket.fetch, log=lambda _: None)
    already = {r["source_key"]: r["source_etag"] for r in first.records}
    bucket.put("JC-202611-citibike-tripdata.csv.zip",
               make_zip({"JC-202611-citibike-tripdata.csv": csv_text(CURRENT_HEADER, 9)}))

    second = landing.land_new_files(str(tmp_path), already, fetch=bucket.fetch, log=lambda _: None)

    assert [r["month"] for r in second.records] == ["202611"]
    assert second.data_rows == 9


def test_republished_file_is_landed_again_and_replaces_the_csv(bucket, tmp_path):
    first = landing.land_new_files(str(tmp_path), {}, fetch=bucket.fetch, log=lambda _: None)
    already = {r["source_key"]: r["source_etag"] for r in first.records}
    bucket.put("JC-202102-citibike-tripdata.csv.zip",
               make_zip({"JC-202102-citibike-tripdata.csv": csv_text(CURRENT_HEADER, 6)}),
               etag="a-new-etag")

    second = landing.land_new_files(str(tmp_path), already, fetch=bucket.fetch, log=lambda _: None)

    assert [r["month"] for r in second.records] == ["202102"]
    assert second.records[0]["data_rows"] == 6
    with open(tmp_path / "tripdata/csv/current/JC-202102.csv") as handle:
        assert sum(1 for _ in handle) == 7  # header + 6 rows


def test_one_failed_download_does_not_stop_the_others(bucket, tmp_path):
    bucket.fail_keys.add("JC-202207-citbike-tripdata.csv.zip")
    result = landing.land_new_files(str(tmp_path), {}, fetch=bucket.fetch, log=lambda _: None)
    assert len(result.records) == 3
    assert [key for key, _ in result.failures] == ["JC-202207-citbike-tripdata.csv.zip"]


def test_truncated_download_is_rejected(bucket, tmp_path):
    key = "JC-202610-citibike-tripdata.zip"
    good_fetch = bucket.fetch

    def truncating_fetch(url):
        body = good_fetch(url)
        return body[:-10] if url.endswith(key) else body

    result = landing.land_new_files(str(tmp_path), {}, fetch=truncating_fetch, log=lambda _: None)
    assert [k for k, _ in result.failures] == [key]
    assert "size mismatch" in result.failures[0][1]
    assert not os.path.exists(tmp_path / "tripdata/zip/JC-202610.zip")


# ----------------------------------------------------------------- bronze contract

def test_bronze_expects_exactly_the_current_file_header():
    from citibike_ingest import bronze

    assert landing.normalize_header(CURRENT_HEADER) == bronze.CURRENT_COLUMNS
    assert bronze.CURRENT_HEADER_SIGNATURE == "|".join(landing.normalize_header(CURRENT_HEADER))


def test_bronze_table_has_every_data_and_metadata_column():
    from citibike_ingest import bronze

    ddl = bronze.trips_table_ddl("c.s.t")
    for name in bronze.CURRENT_COLUMNS + [m[0] for m in bronze.METADATA_COLUMNS]:
        assert f"{name} " in ddl
    assert ddl.startswith("CREATE TABLE IF NOT EXISTS c.s.t ")
