from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "coverage_report.py"
SPEC = importlib.util.spec_from_file_location("coverage_report", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CoverageReportTests(unittest.TestCase):
    def test_build_summary_aggregates_scopes_and_renders_markdown(self) -> None:
        payload = {
            "data": [
                {
                    "totals": {
                        "lines": {"count": 100, "covered": 90, "percent": 90.0},
                        "functions": {"count": 20, "covered": 16, "percent": 80.0},
                        "regions": {"count": 50, "covered": 40, "percent": 80.0},
                    },
                    "files": [
                        {
                            "filename": str(REPO_ROOT / "crates" / "runner" / "src" / "lib.rs"),
                            "summary": {
                                "lines": {"count": 40, "covered": 30, "percent": 75.0},
                                "functions": {"count": 8, "covered": 6, "percent": 75.0},
                                "regions": {"count": 20, "covered": 15, "percent": 75.0},
                            },
                        },
                        {
                            "filename": str(REPO_ROOT / "crates" / "runner" / "src" / "mock.rs"),
                            "summary": {
                                "lines": {"count": 20, "covered": 20, "percent": 100.0},
                                "functions": {"count": 4, "covered": 4, "percent": 100.0},
                                "regions": {"count": 10, "covered": 10, "percent": 100.0},
                            },
                        },
                        {
                            "filename": str(REPO_ROOT / "crates" / "ios" / "src" / "lib.rs"),
                            "summary": {
                                "lines": {"count": 40, "covered": 40, "percent": 100.0},
                                "functions": {"count": 8, "covered": 6, "percent": 75.0},
                                "regions": {"count": 20, "covered": 15, "percent": 75.0},
                            },
                        },
                    ],
                }
            ],
            "type": "llvm.coverage.json.export",
            "version": "2.0.1",
            "cargo_llvm_cov": "0.6.15",
        }

        summary = MODULE.build_summary(
            payload,
            repo_root=REPO_ROOT,
            threshold=75.0,
            top_files=2,
        )

        self.assertTrue(summary["meets_line_threshold"])
        self.assertEqual(summary["file_count"], 3)
        self.assertEqual(summary["lowest_line_coverage_files"][0]["path"], "crates/runner/src/lib.rs")
        self.assertEqual(summary["scopes"][0]["scope"], "runner")
        self.assertEqual(summary["scopes"][0]["lines"]["count"], 60)
        self.assertEqual(summary["scopes"][0]["lines"]["covered"], 50)
        self.assertAlmostEqual(summary["scopes"][0]["lines"]["percent"], 83.3333333333)

        markdown = MODULE.render_markdown(summary)
        self.assertIn("Coverage by scope", markdown)
        self.assertIn("runner", markdown)
        self.assertIn("crates/runner/src/lib.rs", markdown)
        self.assertIn("✅ Line coverage is above the configured 75% threshold.", markdown)
        self.assertIn("target/llvm-cov/lcov.info", markdown)

    def test_build_summary_flags_threshold_failure(self) -> None:
        payload = {
            "data": [
                {
                    "totals": {
                        "lines": {"count": 10, "covered": 6, "percent": 60.0},
                        "functions": {"count": 2, "covered": 1, "percent": 50.0},
                        "regions": {"count": 4, "covered": 2, "percent": 50.0},
                    },
                    "files": [
                        {
                            "filename": str(REPO_ROOT / "crates" / "domain" / "src" / "lib.rs"),
                            "summary": {
                                "lines": {"count": 10, "covered": 6, "percent": 60.0},
                                "functions": {"count": 2, "covered": 1, "percent": 50.0},
                                "regions": {"count": 4, "covered": 2, "percent": 50.0},
                            },
                        }
                    ],
                }
            ]
        }

        summary = MODULE.build_summary(
            payload,
            repo_root=REPO_ROOT,
            threshold=75.0,
            top_files=5,
        )

        self.assertFalse(summary["meets_line_threshold"])
        markdown = MODULE.render_markdown(summary)
        self.assertIn("❌ Line coverage is below the configured 75% threshold.", markdown)

    def test_build_summary_rejects_missing_or_malformed_shapes(self) -> None:
        malformed_payloads = [
            {},
            {"data": []},
            {"data": ["not-an-object"]},
            {"data": [{"totals": {}, "files": []}]},
            {
                "data": [
                    {
                        "totals": {
                            "lines": {"count": 1, "covered": 1, "percent": 100.0},
                            "functions": {"count": 1, "covered": 1, "percent": 100.0},
                            "regions": {"count": 1, "covered": 1, "percent": 100.0},
                        },
                        "files": [None],
                    }
                ]
            },
            {
                "data": [
                    {
                        "totals": {
                            "lines": {"count": 1, "covered": 1, "percent": 100.0},
                            "functions": {"count": 1, "covered": 1, "percent": 100.0},
                            "regions": {"count": 1, "covered": 1, "percent": 100.0},
                        },
                        "files": [{"filename": "", "summary": {}}],
                    }
                ]
            },
            {
                "data": [
                    {
                        "totals": {
                            "lines": {"count": 1, "covered": 1, "percent": 100.0},
                            "functions": {"count": 1, "covered": 1, "percent": 100.0},
                            "regions": {"count": 1, "covered": 1, "percent": 100.0},
                        },
                        "files": [
                            {
                                "filename": str(REPO_ROOT / "crates" / "domain" / "src" / "lib.rs"),
                                "summary": {
                                    "lines": {"count": 1, "covered": 1, "percent": 100.0},
                                    "functions": {"count": True, "covered": 1, "percent": 100.0},
                                    "regions": {"count": 1, "covered": 1, "percent": 100.0},
                                },
                            }
                        ],
                    }
                ]
            },
        ]

        for payload in malformed_payloads:
            with self.subTest(payload=payload), self.assertRaises(MODULE.CoverageReportError):
                MODULE.build_summary(payload, repo_root=REPO_ROOT, threshold=75.0, top_files=5)


if __name__ == "__main__":
    unittest.main()
