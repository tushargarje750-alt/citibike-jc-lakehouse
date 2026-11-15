import json

import pytest

import dbt_run_summary
import prepare_docs_site

RUN_RESULTS = {
    "metadata": {"dbt_version": "1.12.6"},
    "elapsed_time": 95.27,
    "results": [
        {"unique_id": "model.citibike_lakehouse.fct_trips", "status": "success", "execution_time": 10.7},
        {"unique_id": "model.citibike_lakehouse.dim_stations", "status": "success", "execution_time": 4.6},
        {"unique_id": "test.citibike_lakehouse.unique_fct_trips_ride_id.abc", "status": "pass", "execution_time": 1.1},
        {"unique_id": "test.citibike_lakehouse.accepted_values_fct_trips_rideable_type.def", "status": "warn",
         "execution_time": 1.0, "message": "Got 1 result, configured to warn if != 0"},
        {"unique_id": "test.citibike_lakehouse.assert_gold_totals_match_fct_trips", "status": "fail",
         "execution_time": 2.0, "message": "Got 2 results, configured to fail if != 0"},
        {"unique_id": "unit_test.citibike_lakehouse.int_trips__checked.each_rule", "status": "pass", "execution_time": 1.9},
        {"unique_id": "model.citibike_lakehouse.daily_ridership", "status": "skipped", "execution_time": 0},
    ],
}


def test_run_summary_counts_by_kind_and_status():
    text = "\n".join(dbt_run_summary.summarize(RUN_RESULTS))
    assert "steps:          7 (4 ok, 1 warn, 1 failed, 1 skipped)" in text
    assert "models:         3 (1 skipped, 2 success)" in text
    assert "data tests:     3 (1 fail, 1 pass, 1 warn)" in text
    assert "unit tests:     1 (1 pass)" in text
    assert "total elapsed:  95.3 s" in text


def test_run_summary_lists_slowest_first_and_problems():
    lines = dbt_run_summary.summarize(RUN_RESULTS)
    slowest_index = lines.index("slowest steps:")
    assert "fct_trips" in lines[slowest_index + 1] and "10.7" in lines[slowest_index + 1]
    problems = lines[lines.index("warnings and failures:") + 1:]
    assert any(line.strip().startswith("warn") for line in problems)
    assert any(line.strip().startswith("fail") and "Got 2 results" in line for line in problems)


def test_run_summary_of_a_clean_run_has_no_problem_section():
    clean = {"elapsed_time": 3, "results": [r for r in RUN_RESULTS["results"] if r["status"] in ("success", "pass")]}
    assert "warnings and failures:" not in dbt_run_summary.summarize(clean)


def test_docs_site_gets_three_files_and_no_owner_emails(tmp_path):
    target, site = tmp_path / "target", tmp_path / "site"
    target.mkdir()
    (target / "index.html").write_text("<html></html>")
    (target / "manifest.json").write_text("{}")
    (target / "catalog.json").write_text(json.dumps({
        "nodes": {"model.x.a": {"metadata": {"owner": "someone@example.com", "name": "a"}},
                  "model.x.b": {"metadata": {"owner": None, "name": "b"}}},
        "sources": {"source.x.s": {"metadata": {"owner": "someone@example.com"}}},
    }))

    removed = prepare_docs_site.build_site(str(target), str(site))

    assert removed == 2
    assert sorted(p.name for p in site.iterdir()) == ["catalog.json", "index.html", "manifest.json"]
    assert "example.com" not in (site / "catalog.json").read_text()
    assert json.loads((site / "catalog.json").read_text())["nodes"]["model.x.a"]["metadata"]["name"] == "a"


def test_docs_site_fails_clearly_when_docs_were_not_generated(tmp_path):
    with pytest.raises(FileNotFoundError):
        prepare_docs_site.build_site(str(tmp_path), str(tmp_path / "site"))
