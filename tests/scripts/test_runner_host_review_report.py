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
SOURCE_RULES_FIXTURES_DIR = FIXTURES_DIR / "source-rules"


def load_case(name: str) -> tuple[dict[str, object], dict[str, object]]:
    case_dir = FIXTURES_DIR / name
    baseline = json.loads((case_dir / "baseline.json").read_text(encoding="utf-8"))
    fixture_input = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    return baseline, fixture_input


def load_source_rules_case(name: str) -> dict[str, object]:
    return json.loads((SOURCE_RULES_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def load_repo_source_rules() -> dict[str, object]:
    return json.loads((REPO_ROOT / ".github" / "runner-host-advisory-sources.json").read_text(encoding="utf-8"))


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
                platform_name="android",
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
                    platform_name="android",
                )

        self.assertEqual(str(error.exception), "gh auth token expired")

    def test_build_summary_handles_missing_successful_run_without_aborting(self) -> None:
        baseline, _ = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
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
                        "os_name": "macOS",
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
            source_rules=source_rules,
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
        source_rules = load_source_rules_case("valid")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        self.assertEqual(summary["reason"], "baseline-match")
        self.assertEqual(summary["verdict"], "no review-needed")
        self.assertEqual(summary["platforms"]["android"]["status"], "no review-needed")
        self.assertEqual(summary["platforms"]["ios"]["status"], "no review-needed")
        key_map = {group["key"]: group for group in summary["source_rule_groups"]}
        self.assertEqual(
            set(key_map),
            {"runner-images", "android-java", "android-gradle", "android-emulator-runtime", "ios-xcode-simulator"},
        )
        self.assertEqual(key_map["runner-images"]["rule_kind"], "manual-review-required")
        self.assertEqual(key_map["runner-images"]["follow_up_issue"], 143)
        self.assertEqual(key_map["android-java"]["follow_up_issue"], 154)
        self.assertEqual(key_map["android-gradle"]["follow_up_issue"], 155)
        self.assertEqual(key_map["android-emulator-runtime"]["follow_up_issue"], 156)

        markdown = MODULE.render_markdown(summary)
        self.assertIn("<!-- cve-watch-report -->", markdown)
        self.assertIn("Verdict: **no review-needed**", markdown)
        self.assertIn("drift-triggered manual review", markdown)
        self.assertIn("Source-rule status", markdown)
        self.assertIn("runner-images", markdown)
        self.assertIn("android-java", markdown)
        self.assertIn("android-gradle", markdown)
        self.assertIn("android-emulator-runtime", markdown)
        self.assertIn("#154", markdown)
        self.assertIn("#155", markdown)
        self.assertIn("#156", markdown)

    def test_build_summary_accepts_checked_in_source_rules_manifest(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_repo_source_rules()

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        source_rule_groups = {group["key"]: group for group in summary["source_rule_groups"]}
        self.assertEqual(
            set(source_rule_groups),
            {"runner-images", "android-java", "android-gradle", "android-emulator-runtime", "ios-xcode-simulator"},
        )

        android_java = source_rule_groups["android-java"]
        self.assertEqual(android_java["follow_up_issue"], 154)
        self.assertEqual(
            android_java["watched_fact_paths"],
            [
                {
                    "platform": "android",
                    "path": "java.configured_major",
                    "label": "configured Java major",
                    "baseline": "17",
                },
                {
                    "platform": "android",
                    "path": "java.resolved_version",
                    "label": "resolved Java version",
                    "baseline": "17.0.18+8",
                },
            ],
        )

        android_gradle = source_rule_groups["android-gradle"]
        self.assertEqual(android_gradle["follow_up_issue"], 155)
        self.assertEqual(
            android_gradle["watched_fact_paths"],
            [
                {
                    "platform": "android",
                    "path": "gradle.configured_version",
                    "label": "configured Gradle version",
                    "baseline": "8.7",
                },
                {
                    "platform": "android",
                    "path": "gradle.resolved_version",
                    "label": "resolved Gradle version",
                    "baseline": "8.7",
                },
            ],
        )

        android_emulator = source_rule_groups["android-emulator-runtime"]
        self.assertEqual(android_emulator["follow_up_issue"], 156)
        self.assertEqual(
            android_emulator["watched_fact_paths"],
            [
                {
                    "platform": "android",
                    "path": "emulator.api_level",
                    "label": "Android API level",
                    "baseline": "34",
                },
                {
                    "platform": "android",
                    "path": "emulator.device_name",
                    "label": "emulator device",
                    "baseline": "sdk_gphone64_x86_64",
                },
                {
                    "platform": "android",
                    "path": "emulator.os_version",
                    "label": "Android runtime",
                    "baseline": "14",
                },
            ],
        )

    def test_build_summary_fails_closed_when_source_rules_reference_unknown_watched_fact_path(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("unknown-path")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("watched fact path", str(error.exception))

    def test_build_summary_fails_closed_when_source_rules_leave_watched_facts_unowned(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("incomplete-coverage")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("watched_fact_paths", str(error.exception))
        self.assertIn("android-emulator-runtime", str(error.exception))
        self.assertIn("android.emulator.device_name", str(error.exception))
        self.assertIn("android.emulator.os_version", str(error.exception))

    def test_build_summary_fails_closed_when_source_rule_uses_unsupported_rule_kind(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("invalid-rule-kind")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("rule_kind", str(error.exception))
        self.assertIn("manual-review-required", str(error.exception))

    def test_build_summary_fails_closed_when_source_rule_omits_follow_up_issue(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("missing-follow-up")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("follow_up_issue", str(error.exception))

    def test_build_summary_fails_closed_when_split_android_group_uses_wrong_follow_up_issue(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        for group in source_rules["groups"]:
            if group["key"] == "android-java":
                group["follow_up_issue"] = 999
                break
        else:
            self.fail("android-java source rule missing from valid fixture")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("follow_up_issue", str(error.exception))
        self.assertIn("must be 154", str(error.exception))

    def test_build_summary_fails_closed_when_split_android_group_owns_wrong_watched_fact_paths(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        key_map = {group["key"]: group for group in source_rules["groups"]}
        key_map["android-java"]["watched_fact_paths"] = [
            {"platform": "android", "path": "java.configured_major"},
            {"platform": "android", "path": "emulator.api_level"},
        ]
        key_map["android-emulator-runtime"]["watched_fact_paths"] = [
            {"platform": "android", "path": "java.resolved_version"},
            {"platform": "android", "path": "emulator.device_name"},
            {"platform": "android", "path": "emulator.os_version"},
        ]

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("android-java", str(error.exception))
        self.assertIn("watched_fact_paths", str(error.exception))

    def test_build_summary_fails_closed_when_source_rule_follow_up_issue_is_string(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        source_rules["groups"][0]["follow_up_issue"] = "143"

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("follow_up_issue", str(error.exception))
        self.assertIn("must be an integer", str(error.exception))

    def test_build_summary_fails_closed_when_source_rule_follow_up_issue_is_float(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        source_rules["groups"][0]["follow_up_issue"] = 143.9

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("follow_up_issue", str(error.exception))
        self.assertIn("must be an integer", str(error.exception))

    def test_build_summary_fails_closed_when_source_rules_managed_issue_title_drifts(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        source_rules["managed_issue_title"] = "security: some other issue"

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("managed_issue_title", str(error.exception))
        self.assertIn("baseline issue_title", str(error.exception))

    def test_build_summary_fails_closed_when_source_rule_text_metadata_is_not_a_string(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        for field_name in ("surface", "rationale", "managed_issue_behavior", "candidate_source"):
            with self.subTest(field_name=field_name):
                source_rules = load_source_rules_case("valid")
                source_rules["groups"][0][field_name] = 123

                with self.assertRaises(MODULE.RunnerHostWatchError) as error:
                    MODULE.build_summary(
                        repo=str(fixture_input["repo"]),
                        baseline=baseline,
                        source_rules=source_rules,
                        observed_platforms=fixture_input["platforms"],
                        generated_at="2026-04-19T09:00:00Z",
                    )

                self.assertIn(field_name, str(error.exception))
                self.assertIn("must be a non-empty string", str(error.exception))

    def test_build_summary_fails_closed_when_manual_review_source_rule_omits_rationale(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("missing-rationale")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("rationale", str(error.exception))

    def test_build_summary_flags_android_drift_as_manual_review_required(self) -> None:
        baseline, fixture_input = load_case("android-drift")
        source_rules = load_source_rules_case("valid")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "baseline-drift")
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
        source_rules = load_source_rules_case("valid")

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "baseline-drift")
        self.assertEqual(summary["platforms"]["ios"]["status"], "manual-review-required")
        self.assertEqual(summary["platforms"]["ios"]["changed_facts"][0]["path"], "xcode.version")
        self.assertEqual(summary["platforms"]["ios"]["changed_facts"][0]["observed"], "16.5")

    def test_build_summary_fails_closed_when_required_host_summary_is_missing(self) -> None:
        baseline, fixture_input = load_case("missing-evidence")
        source_rules = load_source_rules_case("valid")
        ios_watched_count = len(baseline["platforms"]["ios"]["watched_facts"])

        summary = MODULE.build_summary(
            repo=str(fixture_input["repo"]),
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=fixture_input["platforms"],
            generated_at="2026-04-19T09:00:00Z",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], ios_watched_count)
        self.assertEqual(summary["reason"], "missing-evidence")
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

    def test_normalize_fixture_platform_reports_missing_ios_sections_as_ios_contract_gap(self) -> None:
        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.normalize_fixture_platform(
                "ios",
                {
                    "run": {
                        "id": 24600433713,
                        "url": "https://github.com/drousselhq/casgrain/actions/runs/24600433713",
                    },
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
                            "os_name": "macOS",
                            "os_version": "15.7.4",
                            "os_build": "24G517",
                        },
                    },
                },
            )

        self.assertIn("xcode", str(error.exception))


if __name__ == "__main__":
    unittest.main()
