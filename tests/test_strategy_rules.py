"""Strategy catalog unit tests. Synthetic prices are test fixtures, NOT market results."""
import unittest
from datetime import datetime, timedelta

import pandas as pd

from scripts.strategy_rules import STRATEGIES, evaluate_rules


def trending_frame(n=160):
    start = datetime(2025, 1, 1)
    closes = [10.0 + i * 0.027 for i in range(n)]
    closes[-1] += 0.35
    volumes = [1000.0] * n
    volumes[-1] = 2000.0
    return pd.DataFrame({
        "date": [start + timedelta(days=i) for i in range(n)],
        "close": closes,
        "open": [p * .997 for p in closes],
        "high": [p * 1.01 for p in closes],
        "low": [p * .99 for p in closes],
        "volume": volumes,
    })


class StrategyLibraryTests(unittest.TestCase):
    def test_unique_named_definitions_and_data_pending(self):
        ids = [x["id"] for x in STRATEGIES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 7)
        self.assertEqual(sum(x["state"] == "experimental" for x in STRATEGIES), 4)
        self.assertEqual(sum(x["state"] == "data_pending" for x in STRATEGIES), 3)

    def test_breakout_detects_only_completed_current_bar(self):
        rows = evaluate_rules(trending_frame(), "000725", "京东方A")
        self.assertIn("volume_breakout_v1", [r["strategy_id"] for r in rows])
        self.assertTrue(all(r["status"] == "hypothesis_only" for r in rows))
        self.assertTrue(all(r["forward_performance"] is None for r in rows))
        self.assertTrue(all(r["signal_date"] == "2025-06-09" for r in rows))

    def test_does_not_use_current_day_to_construct_prior_high(self):
        f = trending_frame()
        f.loc[f.index[-1], "volume"] = 1200.0
        rows = evaluate_rules(f, "000725", "京东方A")
        self.assertNotIn("volume_breakout_v1", [r["strategy_id"] for r in rows])

    def test_insufficient_history_returns_no_signals(self):
        self.assertEqual(evaluate_rules(trending_frame(125), "000001", "test"), [])

    def test_suspended_or_invalid_price_returns_no_signals(self):
        f = trending_frame()
        f.loc[f.index[-1], "volume"] = 0.0
        self.assertEqual(evaluate_rules(f, "000001", "test"), [])
        f = trending_frame()
        f.loc[f.index[-1], "high"] = f.close.iloc[-1] - 1
        self.assertEqual(evaluate_rules(f, "000001", "test"), [])

    def test_deterministic_on_repeated_inputs(self):
        f = trending_frame()
        self.assertEqual(evaluate_rules(f, "000001", "test"),
                         evaluate_rules(f, "000001", "test"))

    def test_unsorted_input_same_result(self):
        f = trending_frame()
        rows = evaluate_rules(f, "000001", "test")
        self.assertEqual(rows, evaluate_rules(f.sample(frac=1, random_state=7), "000001", "test"))


if __name__ == "__main__":
    unittest.main()
