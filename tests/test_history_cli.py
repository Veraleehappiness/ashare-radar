"""Offline tests of the real-data batch CLI. Never inject samples into published datasets."""
import json
from unittest.mock import patch
import pytest
from scripts.update_history_store import parse_codes, run


def test_code_list_and_json_pool(tmp_path):
    pool=tmp_path / "pool.json"
    pool.write_text(json.dumps({"stocks":[{"code":"600519"},{"code":"000001"}]}))
    assert parse_codes("600519,300750",str(pool)) == ["600519","300750","000001"]
    with pytest.raises(ValueError):
        parse_codes("../secret",None)
    with pytest.raises(ValueError):
        parse_codes("",None)


def test_report_success_and_audited_counts(tmp_path):
    def fake(code, **kwargs):
        return {"code":code,"status":"ok","rows":301,"added_rows":4,
                "first_date":"2024-01-01","last_date":"2026-10-14"}
    with patch("scripts.update_history_store.update_stock_history",side_effect=fake):
        report=run(["600519","000001"],tmp_path/"db","20240101",
                   tmp_path/"report.json",retries=0)
    assert report["result"]=="PASS"
    assert report["succeeded"] == 2
    assert report["new_bars"] == 8
    assert json.loads((tmp_path/"report.json").read_text())["requested"] == 2


def test_reports_partial_failure_no_false_pass(tmp_path):
    def fake(code, **kwargs):
        if code=="000001":
            raise ConnectionError("downstream unavailable")
        return {"code":code,"status":"ok","rows":200,"added_rows":1,
                "first_date":"2025-01-01","last_date":"2026-10-14"}
    with patch("scripts.update_history_store.update_stock_history",side_effect=fake):
        report=run(["600519","000001"],tmp_path/"db","20240101",
                   tmp_path/"report.json",retries=0)
    assert report["result"] == "INCOMPLETE"
    assert report["failed"] == 1
    assert report["success_rate_pct"] == 50
    assert "downstream unavailable" in report["items"][1]["error"]
