"""Checks on the dashboard definition, so a broken chart is caught in CI, not in the browser."""
import json
import os
import re

import pytest

PATH = os.path.join(os.path.dirname(__file__), "..", "dashboards", "citibike_ridership.lvdash.json")
GRID_COLUMNS = 12
SPEC_VERSION = {"counter": 2, "table": 2, "bar": 3, "line": 3, "scatter": 3, "area": 3, "pie": 3}


@pytest.fixture(scope="module")
def dashboard():
    with open(PATH) as handle:
        return json.load(handle)


def _widgets(dashboard):
    return [item for page in dashboard["pages"] for item in page["layout"]]


def _charts(dashboard):
    return [item["widget"] for item in _widgets(dashboard) if "spec" in item["widget"]]


def _encoded_fields(encodings):
    for encoding in encodings.values():
        if "fieldName" in encoding:
            yield encoding["fieldName"]
        for field in encoding.get("fields", []):
            yield field["fieldName"]


def test_every_dataset_reads_only_gold_tables(dashboard):
    for dataset in dashboard["datasets"]:
        sql = "".join(dataset["queryLines"])
        tables = re.findall(r"(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+\.[a-z_]+)", sql)
        assert tables, dataset["name"]
        assert all(table.startswith("workspace.citibike_gold.") for table in tables), dataset["name"]
        assert all(line.endswith("\n") for line in dataset["queryLines"])


def test_every_chart_uses_an_existing_dataset_and_its_columns(dashboard):
    sql_by_dataset = {d["name"]: "".join(d["queryLines"]) for d in dashboard["datasets"]}
    for widget in _charts(dashboard):
        query = widget["queries"][0]["query"]
        assert widget["queries"][0]["name"] == "main_query"
        assert query["datasetName"] in sql_by_dataset, widget["name"]
        for field in query["fields"]:
            assert field["expression"] == f"`{field['name']}`"
            assert re.search(rf"\b{field['name']}\b", sql_by_dataset[query["datasetName"]]), (widget["name"], field)


def test_every_encoding_refers_to_a_field_the_widget_selects(dashboard):
    for widget in _charts(dashboard):
        selected = {field["name"] for field in widget["queries"][0]["query"]["fields"]}
        encoded = set(_encoded_fields(widget["spec"]["encodings"]))
        assert encoded == selected, widget["name"]


def test_widget_types_use_the_spec_version_databricks_expects(dashboard):
    for widget in _charts(dashboard):
        kind = widget["spec"]["widgetType"]
        assert widget["spec"]["version"] == SPEC_VERSION[kind], widget["name"]


def test_widget_names_are_unique_and_valid(dashboard):
    names = [item["widget"]["name"] for item in _widgets(dashboard)]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,60}", name) for name in names)


def test_layout_fills_the_grid_without_gaps_or_overlaps(dashboard):
    for page in dashboard["pages"]:
        assert page["pageType"] == "PAGE_TYPE_CANVAS" and page["layoutVersion"] == "GRID_V1"
        cells = {}
        for item in page["layout"]:
            p = item["position"]
            assert p["x"] >= 0 and p["x"] + p["width"] <= GRID_COLUMNS, item["widget"]["name"]
            for row in range(p["y"], p["y"] + p["height"]):
                for column in range(p["x"], p["x"] + p["width"]):
                    assert (row, column) not in cells, f"{item['widget']['name']} overlaps {cells[(row, column)]}"
                    cells[(row, column)] = item["widget"]["name"]
        rows = max(row for row, _ in cells) + 1
        assert len(cells) == rows * GRID_COLUMNS, "the layout has gaps"


def test_dashboard_has_the_planned_content(dashboard):
    kinds = [widget["spec"]["widgetType"] for widget in _charts(dashboard)]
    assert kinds.count("counter") == 4
    assert len([kind for kind in kinds if kind != "counter"]) == 6
