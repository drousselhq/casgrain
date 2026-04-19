from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "runner_host_review_report.py"
SPEC = importlib.util.spec_from_file_location("runner_host_review_report", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

FIXTURES_DIR = REPO_ROOT / "tests" / "test-support" / "fixtures" / "runner-host-watch"


def load_case(name: str) -> tuple[dict[str, object], dict[str, object]]:
    case_dir = FIXTURES_DIR / name
    baseline = json.loads((case_dir / "baseline.json").read_text(encoding="utf-8"))
    fixture_input = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    return baseline, fixture_input


class RunnerHostReviewReportTests(unittest.TestCase):
    def test_collect_live_platform_reports_missing_successful_run_as_missing_evidence(self) -> None:
        with patch.object(
            MODULE,
            "select_latest_successful_run",
            side_effect=MODULE.RunnerHostWatchError("no successful android-emulator-smoke.yml run found on main"),
        ):
            observed = MODULE.collect_live_platform(
                repo="drousselhq/casgrain",
                workflow="android-emulator-smoke.yml",
                artifact="casgrain-android-smoke",
                branch="main",
            )

        self.assertEqual(observed["run"], {"id": None, "url": None})
        self.assertEqual(
            observed["host_environment_error"],
            "no successful android-emulator-smoke.yml run found on main",
        )

    def test_collect_live_platform_reraises_non_missing_run_errors(self) -> None:
        with patch.object(
            MODULE,
            "select_latest_successful_run",
            side_effect=MODULE.RunnerHostWatchError("gh auth token expired"),
        ):
            with self.assertRaises(MODULE.RunnerHostWatchError) as error:
                MODULE.collect_live_platform(
                    repo="drousselhq/casgrain",
                    workflow="android-emulator-smoke.yml",
                    artifact="casgrain-android-smoke",
                    branch="main",
                )

        self.assertEqual(str(error.exception), "gh auth token expired")

    def test_build_summary_handles_missing_successful_run_without_aborting(self) -> None:
        baseline, _ = load_case("baseline-match")
        android_watched_count = len(baseline["platforms"]["android"]["watched_facts"])
        observed_platforms = {
            "android": {
                "run": {"id": None, "url": None},
                "host_environment_error": "no successful android-emulator-smoke.yml run found on main",
            },
            "ios": {
                "run": {"id": 24600433713, "url": "https://github.com/drousselhq/casgrain/actions/runs/24600433713"},
                "host_environment": {
                    "generated_at": "2026-04-19T08:00:00Z",
                    "workflow_run": {
                        "repository": "drousselhq/casgrain",
                        "workflow": "ios-simulator-smoke",
                        "run_id": "24600433713",
                        "run_attempt": "1",
                        "run_url": "https://github.com/drousselhq/casgrain/actions/runs/24600433713",
                    },
                    "runner": {
                        "label": "macos-15",
                        "image_name": "macos-15-arm64",
                        "image_version": "20260414.0270.1",
                        "os_version": "15.7.4",
                        "os_build": "24G517",
                    },
                    "xcode": {
                        "app_path": "/Applications/Xcode_16.4.app",
                        "version": "16.4",
                        "simulator_sdk_version": "18.5",
                    },
                    "simulator": {
                        "runtime_identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-2",
                        "runtime_name": "iOS 26.2",
                        "device_name": "iPhone 16",
                    },
                },
            },
        }

        summary = MODULE.build_summary(
            repo="drousselhq/casgrain",
            baseline=baseline,
            observed_platforms=observed_platforms,
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], android_watched_count)
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["platforms"]["android"]["run_id"], None)
        self.assertEqual(
            summary["platforms"]["android"]["missing_evidence"][0]["reason"],
            "no successful android-emulator-smoke.yml run found on main",
        )
        self.assertEqual(len(summary["platforms"]["android"]["missing_facts"]), android_watched_count)

    def test_build_summary_reports_no_review_needed_when_observed_facts_match_baseline(self) -> None:
        baseline, fixture_input = load_case("baseline-match")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        self.assertEqual(summary["verdict"], "no review-needed")
        self.assertEqual(summary["platforms"]["android"]["status"], "no review-needed")
        self.assertEqual(summary["platforms"]["ios"]["status"], "no review-needed")

        markdown = MODULE.render_markdown(summary)
        self.assertIn("<!-- cve-watch-report -->", markdown)
        self.assertIn("Verdict: **no review-needed**", markdown)
        self.assertIn("drift-triggered manual review", markdown)

    def test_build_summary_flags_android_drift_as_manual_review_required(self) -> None:
        baseline, fixture_input = load_case("android-drift")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["platforms"]["android"]["status"], "manual-review-required")
        self.assertEqual(
            summary["platforms"]["android"]["changed_facts"][0]["path"],
            "runner.image_version",
        )
        self.assertEqual(summary["platforms"]["android"]["changed_facts"][0]["observed"], "20260420.01.1")

        markdown = MODULE.render_markdown(summary)
        self.assertIn("runner.image_version", markdown)
        self.assertIn("20260420.01.1", markdown)

    def test_build_summary_flags_ios_drift_as_manual_review_required(self) -> None:
        baseline, fixture_input = load_case("ios-drift")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["platforms"]["ios"]["status"], "manual-review-required")
        self.assertEqual(summary["platforms"]["ios"]["changed_facts"][0]["path"], "xcode.version")
        self.assertEqual(summary["platforms"]["ios"]["changed_facts"][0]["observed"], "16.5")

    def test_build_summary_fails_closed_when_required_host_summary_is_missing(self) -> None:
        baseline, fixture_input = load_case("missing-evidence")
        ios_watched_count = len(baseline["platforms"]["ios"]["watched_facts"])

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], ios_watched_count)
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["platforms"]["ios"]["status"], "manual-review-required")
        self.assertEqual(summary["platforms"]["ios"]["missing_evidence"][0]["reason"], "host-environment.json missing")
        self.assertEqual(len(summary["platforms"]["ios"]["missing_facts"]), ios_watched_count)

        markdown = MODULE.render_markdown(summary)
        self.assertIn("host-environment.json missing", markdown)
        self.assertIn("manual-review-required", markdown)

    def test_normalize_fixture_platform_requires_host_environment_metadata(self) -> None:
        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.normalize_fixture_platform(
                "android",
                {
                    "run": {
                        "id": 24624943594,
                        "url": "https://github.com/drousselhq/casgrain/actions/runs/24624943594",
                    },
                    "host_environment": {
                        "runner": {
                            "label": "ubuntu-latest",
                            "image_name": "ubuntu-24.04",
                            "image_version": "20260413.86.1",
                            "os_version": "24.04.4",
                        }
                    },
                },
            )

        self.assertIn("generated_at", str(error.exception))


if __name__ == "__main__":
    unittest.main()
