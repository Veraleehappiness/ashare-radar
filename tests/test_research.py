"""Offline contract tests: no fake market data or network calls."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "enrich_research.py"
spec = importlib.util.spec_from_file_location("research_enrich", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ResearchContractTests(unittest.TestCase):
    def test_finite_numbers_only(self):
        self.assertIsNone(mod.safe_number(float("nan")))
        self.assertIsNone(mod.safe_number(float("inf")))
        self.assertEqual(mod.safe_number("2.50"), 2.5)

    def test_attribute_or_dict_access(self):
        self.assertEqual(mod.attr({"name": "a"}, "name"), "a")
        self.assertEqual(mod.attr(object(), "missing", "fallback"), "fallback")

    def test_invalid_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market.json"
            path.write_text(json.dumps({"status": "ok", "stocks": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                mod.enrich(path)

    def test_no_backtest_fabrication_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market.json"
            path.write_text(json.dumps({
                "status": "ok", "stocks": [{"code": "000001"}],
                "backtests": {}, "candidates": []}), encoding="utf-8")
            with patch.object(mod, "subprocess_research", side_effect=[
                {"status": "failed", "engine": "alphasift", "error": "offline"},
                {"status": "failed", "engine": "akquant", "error": "offline"}]):
                mod.enrich(path)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["backtests"], {})
            self.assertEqual(saved["alphasift"]["status"], "failed")
            self.assertEqual(saved["research_backtests"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
