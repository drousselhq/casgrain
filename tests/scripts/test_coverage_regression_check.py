from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "coverage_regression_check.py"
SPEC = importlib.util.spec_from_file_location("coverage_regression_check", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CoverageRegressionCheckTests(unittest.TestCase):
    def test_compare_reports_detects_line_coverage_regression(self) -> None:
        baseline = {
            "totals": {
                "lines": {"count": 100, "covered": 91, "percent": 91.0},
                "functions": {"count": 10, "covered": 9, "percent": 90.0},
                "regions": {"count": 20, "covered": 16, "percent": 80.0},
            }
        }
        current = {
            "totals": {
                "lines": {"count": 120, "covered": 108, "percent": 90.0},
                "functions": {"count": 12, "covered": 10, "percent": 83.3333333333},
                "regions": {"count": 24, "covered": 18, "percent": 75.0},
            }
        }

        summary = MODULE.compare_reports(current=current, baseline=baseline, baseline_label="main")

        self.assertFalse(summary["meets_non_regression_gate"])
        self.assertAlmostEqual(summary["line_percent_delta"], -1.0)
        markdown = MODULE.render_markdown(summary)
        self.assertIn("Coverage non-regression vs main", markdown)
        self.assertIn("❌ Overall line coverage regressed", markdown)
        self.assertIn("91.00%", markdown)
        self.assertIn("90.00%", markdown)

    def test_compare_reports_accepts_improvement(self) -> None:
        baseline = {
            "totals": {
                "lines": {"count": 100, "covered": 90, "percent": 90.0},
                "functions": {"count": 10, "covered": 8, "percent": 80.0},
                "regions": {"count": 20, "covered": 16, "percent": 80.0},
            }
        }
        current = {
            "totals": {
                "lines": {"count": 120, "covered": 111, "percent": 92.5},
                "functions": {"count": 12, "covered": 10, "percent": 83.3333333333},
                "regions": {"count": 24, "covered": 20, "percent": 83.3333333333},
            }
        }

        summary = MODULE.compare_reports(current=current, baseline=baseline, baseline_label="main")

        self.assertTrue(summary["meets_non_regression_gate"])
        self.assertAlmostEqual(summary["line_percent_delta"], 2.5)
        markdown = MODULE.render_markdown(summary)
        self.assertIn("✅ Overall line coverage stayed at or above the main baseline.", markdown)

    def test_load_summary_rejects_missing_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = Path(tmp_dir) / "coverage-report.json"
            bad_path.write_text('{"file_count": 1}', encoding="utf-8")

            with self.assertRaises(MODULE.CoverageRegressionError):
                MODULE.load_summary(bad_path)

    def test_run_without_baseline_marks_check_skipped(self) -> None:
        current = {
            "totals": {
                "lines": {"count": 120, "covered": 111, "percent": 92.5},
                "functions": {"count": 12, "covered": 10, "percent": 83.3333333333},
                "regions": {"count": 24, "covered": 20, "percent": 83.3333333333},
            }
        }

        summary = MODULE.compare_reports(current=current, baseline=None, baseline_label="main")

        self.assertEqual(summary["status"], "skipped")
        self.assertIsNone(summary["meets_non_regression_gate"])
        markdown = MODULE.render_markdown(summary)
        self.assertIn("Non-regression check skipped", markdown)


if __name__ == "__main__":
    unittest.main()
