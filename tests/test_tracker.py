import importlib.util
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "track_signals.py"
spec = importlib.util.spec_from_file_location("tracker", SOURCE)
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


def data_for(day="2026-10-13", price=10.0, last_bar=None):
    actual_bar = last_bar or day
    rows = [{"code": f"{i:06d}", "name": f"stock-{i}", "price": price,
             "amount": 1000000} for i in range(1200)]
    return {
        "status": "ok", "generated_at": f"{day}T18:00:00+08:00",
        "stocks": rows,
        "histories": {
            "000725": {"last_bar": actual_bar,
                       "bars": [{"date": actual_bar, "close": price}]},
            "000001": {"last_bar": actual_bar,
                       "bars": [{"date": actual_bar, "close": price}]},
            "000002": {"last_bar": actual_bar,
                       "bars": [{"date": actual_bar, "close": price}]},
        },
        "candidates": [{"code": "000725", "signal": "放量突破"}],
        "alphasift": {"status": "ok", "strategy": "dual_low",
                      "picks": [{"code": "000001", "price": price}]},
    }


class TrackerTests(unittest.TestCase):
    def test_new_records_and_no_fictitious_returns(self):
        result, summary = tracker.evolve(data_for())
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["added_today"], 2)
        self.assertEqual(summary["horizons"]["1"]["matured_signals"], 0)
        self.assertEqual(len(result["records"]), 2)

    def test_same_session_is_idempotent(self):
        first, _ = tracker.evolve(data_for())
        second, summary = tracker.evolve(data_for(), first)
        self.assertEqual(summary["added_today"], 0)
        self.assertEqual(len(second["records"]), 2)
        self.assertEqual(len(second["records"][0]["observations"]), 1)

    def test_real_future_observation(self):
        first, _ = tracker.evolve(data_for())
        second, summary = tracker.evolve(data_for("2026-10-14", 11.0), first)
        self.assertEqual(summary["added_today"], 2)
        self.assertEqual(summary["horizons"]["1"]["matured_signals"], 2)
        self.assertEqual(summary["horizons"]["1"]["mean_sampled_change_pct"], 10.0)
        self.assertEqual(second["records"][0]["checkpoints"]["1"]["sampled_price_change_pct"], 10.0)

    def test_skips_non_session_or_stale_daily_bars(self):
        first, _ = tracker.evolve(data_for())
        next_snapshot = data_for("2026-10-14", 11.0, last_bar="2026-10-13")
        second, summary = tracker.evolve(next_snapshot, first)
        self.assertEqual(summary["status"], "skipped")
        self.assertEqual(second["records"], first["records"])

    def test_requires_consistent_bar_dates(self):
        snapshot = data_for()
        snapshot["histories"]["000001"]["last_bar"] = "2026-10-12"
        _, summary = tracker.evolve(snapshot)
        self.assertEqual(summary["status"], "skipped")

    def test_no_return_record_when_quote_missing(self):
        first, _ = tracker.evolve(data_for())
        day2 = data_for("2026-10-14")
        for row in day2["stocks"]:
            if row["code"] == "000725":
                row["amount"] = 0
        second, summary = tracker.evolve(day2, first)
        record = next(r for r in second["records"] if r["code"] == "000725" and r["start_date"] == "2026-10-13")
        self.assertEqual(len(record["observations"]), 1)
        self.assertEqual(record["missing_observations"], 1)
        self.assertEqual(summary["horizons"]["1"]["matured_signals"], 1)

    def test_invalid_quotes_do_not_create_signals(self):
        d = data_for()
        for row in d["stocks"]:
            if row["code"] == "000725":
                row["price"] = None
        result, summary = tracker.evolve(d)
        self.assertEqual(summary["added_today"], 1)
        self.assertEqual(result["records"][0]["code"], "000001")


if __name__ == "__main__":
    unittest.main()
