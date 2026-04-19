from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "android_smoke_reliability_window.py"
SPEC = importlib.util.spec_from_file_location("android_smoke_reliability_window", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

FIXTURE_DIR = REPO_ROOT / "tests" / "test-support" / "fixtures" / "android-smoke" / "reliability-window"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class AndroidSmokeReliabilityWindowTests(unittest.TestCase):
    def test_build_summary_reports_not_qualified_fixture(self) -> None:
        summary = MODULE.build_summary(
            load_fixture("not-qualified.json"),
            generated_at="2026-04-19T04:00:00+00:00",
        )

        self.assertEqual(summary["verdict"], "not_qualified")
        self.assertEqual(summary["streak"]["successful_run_count"], 15)
        self.assertEqual(summary["streak"]["schedule_main_success_count"], 0)
        self.assertEqual(summary["streak"]["pull_request_success_count"], 15)
        self.assertEqual(summary["blocker"]["run_id"], 24611423606)
        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertIn("schedule_main_runs_below_threshold", summary["reasons"])
        markdown = MODULE.render_markdown(summary)
        self.assertIn("Android smoke reliability window: NOT QUALIFIED", markdown)
        self.assertIn("24611423606", markdown)
        self.assertIn("artifact-contract-breach", markdown)

    def test_build_summary_reports_qualified_fixture(self) -> None:
        summary = MODULE.build_summary(
            load_fixture("qualified.json"),
            generated_at="2026-04-19T04:00:00+00:00",
        )

        self.assertEqual(summary["verdict"], "qualified")
        self.assertEqual(summary["streak"]["successful_run_count"], 10)
        self.assertEqual(summary["streak"]["schedule_main_success_count"], 3)
        self.assertEqual(summary["streak"]["pull_request_success_count"], 5)
        self.assertEqual(summary["reasons"], [])
        markdown = MODULE.render_markdown(summary)
        self.assertIn("Android smoke reliability window: QUALIFIED", markdown)
        self.assertIn("total=10", markdown)
        self.assertIn("schedule on main=3", markdown)
        self.assertIn("pull_request=5", markdown)

    def test_build_summary_marks_missing_blocker_summary_as_contract_breach(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 2003,
                    "url": "https://example.test/runs/2003",
                    "event": "pull_request",
                    "head_branch": "feature/more-reporting",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 2002,
                    "url": "https://example.test/runs/2002",
                    "event": "schedule",
                    "head_branch": "main",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 2001,
                    "url": "https://example.test/runs/2001",
                    "event": "pull_request",
                    "head_branch": "feature/broken",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": False,
                        "error": "evidence-summary.json missing from downloaded artifact",
                    },
                },
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["verdict"], "not_qualified")
        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertEqual(summary["blocker"]["summary_problem"], "blocker_summary_missing")

    def test_build_summary_marks_missing_streak_summary_as_not_qualified(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 3003,
                    "url": "https://example.test/runs/3003",
                    "event": "pull_request",
                    "head_branch": "feature/current",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 3002,
                    "url": "https://example.test/runs/3002",
                    "event": "schedule",
                    "head_branch": "main",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": False,
                        "error": "artifact unavailable",
                    },
                },
                {
                    "id": 3001,
                    "url": "https://example.test/runs/3001",
                    "event": "pull_request",
                    "head_branch": "feature/older",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "failed", "failure_class": "selector-timeout"}},
                    },
                },
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["verdict"], "not_qualified")
        self.assertIn("streak_summary_missing", summary["reasons"])
        self.assertEqual(summary["streak"]["missing_summary_run_ids"], [3002])

    def test_build_summary_treats_malformed_blocker_summary_as_contract_breach(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 4002,
                    "url": "https://example.test/runs/4002",
                    "event": "pull_request",
                    "head_branch": "feature/current",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 4001,
                    "url": "https://example.test/runs/4001",
                    "event": "pull_request",
                    "head_branch": "feature/broken",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": True,
                        "summary": {},
                    },
                },
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["verdict"], "not_qualified")
        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertEqual(summary["blocker"]["summary_problem"], "blocker_summary_missing")

    def test_build_summary_treats_invalid_blocker_contract_status_as_contract_breach(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 4102,
                    "url": "https://example.test/runs/4102",
                    "event": "pull_request",
                    "head_branch": "feature/current",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 4101,
                    "url": "https://example.test/runs/4101",
                    "event": "pull_request",
                    "head_branch": "feature/broken",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "weird", "failure_class": None}},
                    },
                },
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertEqual(summary["blocker"]["summary_problem"], "blocker_summary_missing")

    def test_build_summary_treats_failed_blocker_with_passing_contract_as_contract_breach(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 4202,
                    "url": "https://example.test/runs/4202",
                    "event": "pull_request",
                    "head_branch": "feature/current",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
                {
                    "id": 4201,
                    "url": "https://example.test/runs/4201",
                    "event": "pull_request",
                    "head_branch": "feature/broken",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                },
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertEqual(summary["blocker"]["summary_problem"], "blocker_summary_inconsistent")

    def test_normalize_live_run_accepts_in_progress_null_conclusion(self) -> None:
        normalized = MODULE.normalize_live_run(
            {
                "databaseId": 5001,
                "displayTitle": "nightly android smoke",
                "status": "in_progress",
                "conclusion": None,
                "event": "schedule",
                "headBranch": "main",
                "url": "https://example.test/runs/5001",
                "createdAt": "2026-04-19T04:00:00Z",
                "updatedAt": "2026-04-19T04:01:00Z",
            }
        )

        self.assertEqual(normalized["conclusion"], "pending")

    def test_build_summary_keeps_qualified_verdict_when_only_blocker_summary_is_missing(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 6100 - index,
                    "url": f"https://example.test/runs/{6100 - index}",
                    "event": "schedule" if index in {1, 4, 7} else "pull_request",
                    "head_branch": "main" if index in {1, 4, 7} else f"feature/pr-{index}",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                }
                for index in range(10)
            ]
            + [
                {
                    "id": 6090,
                    "url": "https://example.test/runs/6090",
                    "event": "pull_request",
                    "head_branch": "feature/older-failure",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": False,
                        "error": "evidence-summary.json missing from downloaded artifact",
                    },
                }
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["verdict"], "qualified")
        self.assertEqual(summary["streak"]["schedule_main_success_count"], 3)
        self.assertEqual(summary["streak"]["pull_request_success_count"], 7)
        self.assertEqual(summary["blocker"]["failure_class"], "artifact-contract-breach")
        self.assertNotIn("blocker_summary_missing", summary["reasons"])

    def test_build_summary_ignores_leading_in_progress_run(self) -> None:
        payload = {
            "repo": "drousselhq/casgrain",
            "workflow": "android-emulator-smoke.yml",
            "artifact_name": "casgrain-android-smoke",
            "runs": [
                {
                    "id": 6201,
                    "url": "https://example.test/runs/6201",
                    "event": "schedule",
                    "head_branch": "main",
                    "status": "in_progress",
                    "conclusion": "pending",
                    "artifact_summary": {
                        "available": False,
                        "error": "still running",
                    },
                }
            ]
            + [
                {
                    "id": 6200 - index,
                    "url": f"https://example.test/runs/{6200 - index}",
                    "event": "schedule" if index in {1, 4, 7} else "pull_request",
                    "head_branch": "main" if index in {1, 4, 7} else f"feature/pr-{index}",
                    "status": "completed",
                    "conclusion": "success",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "passed", "failure_class": None}},
                    },
                }
                for index in range(10)
            ]
            + [
                {
                    "id": 6180,
                    "url": "https://example.test/runs/6180",
                    "event": "pull_request",
                    "head_branch": "feature/older-failure",
                    "status": "completed",
                    "conclusion": "failure",
                    "artifact_summary": {
                        "available": True,
                        "summary": {"contract": {"status": "failed", "failure_class": "selector-timeout"}},
                    },
                }
            ],
        }

        summary = MODULE.build_summary(payload, generated_at="2026-04-19T04:00:00+00:00")

        self.assertEqual(summary["verdict"], "qualified")
        self.assertEqual(summary["streak"]["successful_run_count"], 10)
        self.assertEqual(summary["streak"]["schedule_main_success_count"], 3)
        self.assertEqual(summary["streak"]["pull_request_success_count"], 7)

    def test_completed_history_has_blocker_ignores_leading_in_progress_runs(self) -> None:
        runs = [
            {"id": 7003, "status": "in_progress", "conclusion": "pending"},
            {"id": 7002, "status": "completed", "conclusion": "success"},
            {"id": 7001, "status": "completed", "conclusion": "failure"},
        ]

        self.assertTrue(MODULE.completed_history_has_blocker(runs))
        self.assertFalse(
            MODULE.completed_history_has_blocker(
                [
                    {"id": 7012, "status": "in_progress", "conclusion": "pending"},
                    {"id": 7011, "status": "completed", "conclusion": "success"},
                    {"id": 7010, "status": "completed", "conclusion": "success"},
                ]
            )
        )

    def test_load_artifact_summary_file_handles_non_utf8_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            summary_path = Path(tmp_dir) / "evidence-summary.json"
            summary_path.write_bytes(b"\xff\xfe\xff")

            result = MODULE.load_artifact_summary_file(summary_path)

        self.assertFalse(result["available"])
        self.assertIn("not valid UTF-8", result["error"])

    def test_build_summary_rejects_malformed_run_shape(self) -> None:
        with self.assertRaises(MODULE.ReliabilityWindowError):
            MODULE.build_summary(
                {
                    "repo": "drousselhq/casgrain",
                    "workflow": "android-emulator-smoke.yml",
                    "artifact_name": "casgrain-android-smoke",
                    "runs": [{"id": 1, "event": "pull_request"}],
                },
                generated_at="2026-04-19T04:00:00+00:00",
            )

    def test_build_summary_rejects_non_object_run_entry(self) -> None:
        with self.assertRaises(MODULE.ReliabilityWindowError):
            MODULE.build_summary(
                {
                    "repo": "drousselhq/casgrain",
                    "workflow": "android-emulator-smoke.yml",
                    "artifact_name": "casgrain-android-smoke",
                    "runs": ["oops"],
                },
                generated_at="2026-04-19T04:00:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
