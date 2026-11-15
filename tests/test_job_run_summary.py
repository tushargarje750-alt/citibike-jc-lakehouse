import job_run_summary as summary

RUN = {
    "run_id": 111,
    "run_name": "citibike-jc-lakehouse",
    "trigger": "ONE_TIME",
    "start_time": 1_794_762_000_000,
    "end_time": 1_794_762_215_500,
    "state": {"life_cycle_state": "TERMINATED", "result_state": "SUCCESS"},
    "tasks": [
        {"task_key": "dbt_build", "start_time": 1_794_762_100_000, "end_time": 1_794_762_215_000,
         "state": {"result_state": "SUCCESS"}},
        {"task_key": "land_tripdata", "start_time": 1_794_762_001_000, "end_time": 1_794_762_031_000,
         "state": {"result_state": "SUCCESS"}},
        {"task_key": "bronze_trips", "start_time": 1_794_762_032_000, "end_time": 1_794_762_090_000,
         "status": {"state": "TERMINATED", "termination_details": {"code": "SUCCESS"}}},
    ],
}


def test_latest_run_id_accepts_both_cli_output_shapes():
    assert summary.latest_run_id([{"run_id": 7}, {"run_id": 6}]) == 7
    assert summary.latest_run_id({"runs": [{"run_id": 9}]}) == 9
    assert summary.latest_run_id([]) is None
    assert summary.latest_run_id({}) is None


def test_result_is_read_from_old_and_new_api_shapes():
    assert summary.result_of({"state": {"result_state": "FAILED"}}) == "FAILED"
    assert summary.result_of({"status": {"state": "TERMINATED", "termination_details": {"code": "SUCCESS"}}}) == "SUCCESS"
    assert summary.result_of({"status": {"state": "RUNNING"}}) == "RUNNING"
    assert summary.result_of({}) == "UNKNOWN"


def test_duration_prefers_wall_clock_then_falls_back():
    assert summary.duration_seconds({"start_time": 1000, "end_time": 31_500}) == 30.5
    assert summary.duration_seconds({"run_duration": 12_000}) == 12.0
    assert summary.duration_seconds({"setup_duration": 1000, "execution_duration": 4000}) == 5.0
    assert summary.duration_seconds({"start_time": 1000, "end_time": 0}) is None


def test_summary_lists_tasks_in_start_order_with_durations():
    lines = summary.summarize(RUN)
    text = "\n".join(lines)
    assert "result:         SUCCESS" in text
    assert "total duration: 215.5 s" in text
    assert "tasks:          3 of 3 succeeded" in text
    task_lines = [line.split()[0] for line in lines if line.startswith("  ")]
    assert task_lines == ["land_tripdata", "bronze_trips", "dbt_build"]
    assert any("bronze_trips" in line and "58.0 s" in line for line in lines)
