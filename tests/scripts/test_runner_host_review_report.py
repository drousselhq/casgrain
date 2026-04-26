from __future__ import annotations

import copy
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
RUNNER_IMAGE_SOURCE_FIXTURES_DIR = FIXTURES_DIR / "runner-image-source"
JAVA_SOURCE_FIXTURES_DIR = FIXTURES_DIR / "java-source"
GRADLE_SOURCE_FIXTURES_DIR = FIXTURES_DIR / "gradle-source"
EMULATOR_SOURCE_FIXTURES_DIR = FIXTURES_DIR / "emulator-source"

JAVA_SOURCE_METADATA = {
    "distribution": "temurin",
    "vendor": "eclipse",
    "release_catalog_url": "https://api.adoptium.net/v3/info/available_releases",
    "version_lookup_url_template": "https://api.adoptium.net/v3/assets/version/{version}?architecture=x64&heap_size=normal&image_type=jdk&jvm_impl=hotspot&os=linux&page=0&page_size=1&project=jdk&release_type=ga&vendor=eclipse",
    "supported_major_policy": "available_lts_plus_latest_feature",
}


def load_case(name: str) -> tuple[dict[str, object], dict[str, object]]:
    case_dir = FIXTURES_DIR / name
    baseline = json.loads((case_dir / "baseline.json").read_text(encoding="utf-8"))
    fixture_input = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    return baseline, fixture_input


def load_source_rules_case(name: str) -> dict[str, object]:
    return json.loads((SOURCE_RULES_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def load_runner_image_source_case(name: str) -> dict[str, object]:
    return json.loads((RUNNER_IMAGE_SOURCE_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def load_java_source_case(name: str) -> dict[str, object]:
    return json.loads((JAVA_SOURCE_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def load_gradle_source_case(name: str) -> object:
    return json.loads((GRADLE_SOURCE_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def load_emulator_source_text(case_name: str, file_name: str) -> str:
    return (EMULATOR_SOURCE_FIXTURES_DIR / case_name / file_name).read_text(encoding="utf-8")


def emulator_source_side_effect(case_name: str, source_rules: dict[str, object]):
    emulator_group = next(group for group in source_rules["groups"] if group["key"] == "android-emulator-runtime")
    source_catalogs = emulator_group["source_catalogs"]

    def fake_fetch_text_url(url: str) -> str:
        if url == source_catalogs["platform_catalog_url"]:
            return load_emulator_source_text(case_name, "platforms.xml")
        if url == source_catalogs["system_image_catalog_url"]:
            return load_emulator_source_text(case_name, "system-images.xml")
        if url == source_catalogs["version_mapping_url"]:
            return load_emulator_source_text(case_name, "version-map.html")
        raise AssertionError(f"unexpected emulator source URL: {url}")

    return fake_fetch_text_url


def load_repo_source_rules() -> dict[str, object]:
    return json.loads((REPO_ROOT / ".github" / "runner-host-advisory-sources.json").read_text(encoding="utf-8"))


def build_android_java_promoted_source_rules() -> dict[str, object]:
    source_rules = load_source_rules_case("runner-images-promoted")
    android_java = next(group for group in source_rules["groups"] if group["key"] == "android-java")
    android_java["rule_kind"] = "java-release-support"
    android_java["rationale"] = (
        "Current main compares emitted Android Java facts against authoritative Eclipse Temurin release/support metadata."
    )
    android_java["managed_issue_behavior"] = "Actionable Android Java findings must reuse the existing managed issue title."
    android_java["candidate_source"] = "Eclipse Temurin available releases and version metadata"
    android_java["source_metadata"] = copy.deepcopy(JAVA_SOURCE_METADATA)
    return source_rules


def patch_java_source_case(name: str):
    source_case = load_java_source_case(name)

    def fake_fetch_json_url(url: str) -> object:
        for fixture_url, error_message in source_case.get("errors", {}).items():
            if url == fixture_url:
                raise MODULE.RunnerHostWatchError(str(error_message))
        for fixture_url, response in source_case.get("responses", {}).items():
            if url == fixture_url:
                return response
        raise AssertionError(f"unexpected Java source URL: {url}")

    return patch.object(MODULE, "fetch_json_url", side_effect=fake_fetch_json_url)


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
        self.assertEqual(key_map["ios-xcode-simulator"]["follow_up_issues"], [164, 165])
        self.assertNotIn("follow_up_issue", key_map["ios-xcode-simulator"])

        markdown = MODULE.render_markdown(summary)
        self.assertIn("<!-- cve-watch-report -->", markdown)
        self.assertIn("Verdict: **no review-needed**", markdown)
        self.assertIn("baseline drift/missing-evidence checks are clean", markdown)
        self.assertIn("Source-rule status", markdown)
        self.assertIn("runner-images", markdown)
        self.assertIn("android-java", markdown)
        self.assertIn("android-gradle", markdown)
        self.assertIn("android-emulator-runtime", markdown)
        self.assertIn("#154", markdown)
        self.assertIn("#155", markdown)
        self.assertIn("#156", markdown)
        self.assertIn("via #164, #165", markdown)
        self.assertNotIn("via #144", markdown)

    def test_build_summary_accepts_checked_in_source_rules_manifest(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_repo_source_rules()

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("clean", source_rules),
        ):
            with patch_java_source_case("supported"):
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
        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        self.assertEqual(summary["reason"], "baseline-match")
        self.assertEqual(source_rule_groups["runner-images"]["rule_kind"], "runner-image-release-metadata")
        self.assertEqual(source_rule_groups["runner-images"]["status"], "no review-needed")
        self.assertEqual(source_rule_groups["runner-images"]["outcome"], "source-match")

        android_java = source_rule_groups["android-java"]
        self.assertEqual(android_java["follow_up_issue"], 154)
        self.assertEqual(android_java["rule_kind"], "java-release-support")
        self.assertEqual(android_java["status"], "no review-needed")
        self.assertEqual(android_java["outcome"], "source-match")
        self.assertEqual(android_java["source_metadata"], JAVA_SOURCE_METADATA)
        self.assertEqual(len(android_java["platform_results"]), 1)
        self.assertEqual(android_java["platform_results"][0]["platform"], "android")
        self.assertEqual(android_java["platform_results"][0]["outcome"], "source-match")
        self.assertEqual(android_java["platform_results"][0]["findings"], [])
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
        self.assertEqual(android_gradle["rule_kind"], "gradle-release-catalog")
        self.assertEqual(android_gradle["status"], "no review-needed")
        self.assertEqual(android_gradle["outcome"], "source-match")
        gradle_platform_result = android_gradle["platform_results"][0]
        self.assertEqual(gradle_platform_result["platform"], "android")
        self.assertEqual(gradle_platform_result["status"], "no review-needed")
        self.assertEqual(gradle_platform_result["outcome"], "source-match")
        self.assertEqual(
            gradle_platform_result["observed"],
            {
                "gradle.configured_version": "8.7",
                "gradle.resolved_version": "8.7",
            },
        )
        self.assertEqual(
            gradle_platform_result["source"],
            {
                "gradle.configured_version": "8.7",
                "gradle.resolved_version": "8.7",
            },
        )
        self.assertEqual(gradle_platform_result["review_needed_findings"], [])
        self.assertEqual(gradle_platform_result["informational_findings"], [])

        android_emulator = source_rule_groups["android-emulator-runtime"]
        self.assertEqual(android_emulator["follow_up_issue"], 156)
        self.assertEqual(android_emulator["rule_kind"], "android-system-image-catalog")
        self.assertEqual(android_emulator["status"], "no review-needed")
        self.assertEqual(android_emulator["outcome"], "source-match")
        self.assertEqual(
            android_emulator["observed"],
            {
                "emulator.api_level": "34",
                "emulator.os_version": "14",
                "emulator.target": "google_apis",
                "emulator.arch": "x86_64",
                "emulator.profile": "pixel_7",
            },
        )
        self.assertEqual(
            android_emulator["source"]["platform_package_path"],
            "platforms;android-34",
        )
        self.assertEqual(
            android_emulator["source"]["system_image_package_path"],
            "system-images;android-34;google_apis;x86_64",
        )
        self.assertEqual(android_emulator["source"]["mapped_os_version"], "14")
        self.assertEqual(android_emulator["source"]["system_image_revision"], "12")
        ios_placeholder = source_rule_groups["ios-xcode-simulator"]
        self.assertEqual(ios_placeholder["follow_up_issues"], [164, 165])
        self.assertNotIn("follow_up_issue", ios_placeholder)
        self.assertNotIn("source_advisory_count", summary)

    def test_build_summary_reports_android_java_source_review_needed_for_unsupported_major(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = build_android_java_promoted_source_rules()
        fixture_input["platforms"]["android"]["host_environment"]["java"]["configured_major"] = "15"
        fixture_input["platforms"]["android"]["host_environment"]["java"]["resolved_version"] = "15.0.9+9"
        for watched in baseline["platforms"]["android"]["watched_facts"]:
            if watched["path"] == "java.configured_major":
                watched["baseline"] = "15"
            if watched["path"] == "java.resolved_version":
                watched["baseline"] = "15.0.9+9"

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("unsupported-major"):
                summary = MODULE.build_summary(
                    repo=str(fixture_input["repo"]),
                    baseline=baseline,
                    source_rules=source_rules,
                    observed_platforms=fixture_input["platforms"],
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        android_java = {group["key"]: group for group in summary["source_rule_groups"]}["android-java"]
        self.assertEqual(android_java["status"], "manual-review-required")
        self.assertEqual(android_java["outcome"], "source-review-needed")
        android_result = android_java["platform_results"][0]
        self.assertEqual(android_result["outcome"], "unsupported-release")
        self.assertEqual(android_result["findings"][0]["code"], "unsupported-configured-major")
        self.assertEqual(android_result["findings"][0]["observed"], "15")

    def test_build_summary_reports_android_java_source_review_needed_for_unrecognized_version(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = build_android_java_promoted_source_rules()
        fixture_input["platforms"]["android"]["host_environment"]["java"]["resolved_version"] = "17.0.18+999"
        for watched in baseline["platforms"]["android"]["watched_facts"]:
            if watched["path"] == "java.resolved_version":
                watched["baseline"] = "17.0.18+999"

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("unrecognized-version"):
                summary = MODULE.build_summary(
                    repo=str(fixture_input["repo"]),
                    baseline=baseline,
                    source_rules=source_rules,
                    observed_platforms=fixture_input["platforms"],
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "source-review-needed")
        android_java = {group["key"]: group for group in summary["source_rule_groups"]}["android-java"]
        android_result = android_java["platform_results"][0]
        self.assertEqual(android_result["outcome"], "unrecognized-version")
        self.assertEqual(android_result["findings"][0]["code"], "unrecognized-resolved-version")
        self.assertEqual(android_result["findings"][0]["observed"], "17.0.18+999")

    def test_build_summary_fails_closed_when_android_java_source_metadata_is_unavailable(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = build_android_java_promoted_source_rules()

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("source-error"):
                summary = MODULE.build_summary(
                    repo=str(fixture_input["repo"]),
                    baseline=baseline,
                    source_rules=source_rules,
                    observed_platforms=fixture_input["platforms"],
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        android_java = {group["key"]: group for group in summary["source_rule_groups"]}["android-java"]
        self.assertEqual(android_java["status"], "manual-review-required")
        self.assertEqual(android_java["outcome"], "source-error")
        android_result = android_java["platform_results"][0]
        self.assertEqual(android_result["status"], "manual-review-required")
        self.assertEqual(android_result["outcome"], "source-error")
        self.assertIn("metadata unavailable", android_result["source_error"])

    def test_build_summary_fails_closed_when_android_java_version_lookup_payload_is_malformed(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = build_android_java_promoted_source_rules()

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("malformed-version-payload"):
                summary = MODULE.build_summary(
                    repo=str(fixture_input["repo"]),
                    baseline=baseline,
                    source_rules=source_rules,
                    observed_platforms=fixture_input["platforms"],
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        android_java = {group["key"]: group for group in summary["source_rule_groups"]}["android-java"]
        self.assertEqual(android_java["status"], "manual-review-required")
        self.assertEqual(android_java["outcome"], "source-error")
        android_result = android_java["platform_results"][0]
        self.assertEqual(android_result["status"], "manual-review-required")
        self.assertEqual(android_result["outcome"], "source-error")
        self.assertIn("java version lookup payload must be a list", android_result["source_error"])

    def test_build_summary_does_not_add_new_android_java_advisories_when_android_evidence_is_missing(self) -> None:
        baseline, _ = load_case("baseline-match")
        runner_images_only = load_source_rules_case("runner-images-promoted")
        java_promoted = build_android_java_promoted_source_rules()
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

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            runner_images_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=runner_images_only,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("supported"):
                java_summary = MODULE.build_summary(
                    repo="drousselhq/casgrain",
                    baseline=baseline,
                    source_rules=java_promoted,
                    observed_platforms=json.loads(json.dumps(observed_platforms)),
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertEqual(runner_images_summary["reason"], "missing-evidence")
        self.assertEqual(java_summary["reason"], "missing-evidence")
        self.assertEqual(java_summary["advisory_count"], runner_images_summary["advisory_count"])
        android_java = {group["key"]: group for group in java_summary["source_rule_groups"]}["android-java"]
        self.assertEqual(android_java["status"], "no review-needed")
        self.assertEqual(android_java["outcome"], "source-skipped")
        platform_result = android_java["platform_results"][0]
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-skipped")
        self.assertEqual(platform_result["skip_reason"], "no successful android-emulator-smoke.yml run found on main")
        self.assertEqual(platform_result["findings"], [])
        self.assertNotIn("source_error", platform_result)

    def test_build_summary_keeps_android_java_skipped_when_android_evidence_is_missing_and_fetch_fails(self) -> None:
        baseline, _ = load_case("baseline-match")
        runner_images_only = load_source_rules_case("runner-images-promoted")
        java_promoted = build_android_java_promoted_source_rules()
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

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            runner_images_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=runner_images_only,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            with patch_java_source_case("source-error"):
                java_summary = MODULE.build_summary(
                    repo="drousselhq/casgrain",
                    baseline=baseline,
                    source_rules=java_promoted,
                    observed_platforms=json.loads(json.dumps(observed_platforms)),
                    generated_at="2026-04-19T09:00:00Z",
                )

        self.assertEqual(runner_images_summary["reason"], "missing-evidence")
        self.assertEqual(java_summary["reason"], "missing-evidence")
        self.assertEqual(java_summary["advisory_count"], runner_images_summary["advisory_count"])
        android_java = {group["key"]: group for group in java_summary["source_rule_groups"]}["android-java"]
        self.assertEqual(android_java["status"], "no review-needed")
        self.assertEqual(android_java["outcome"], "source-skipped")
        platform_result = android_java["platform_results"][0]
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-skipped")
        self.assertEqual(platform_result["skip_reason"], "no successful android-emulator-smoke.yml run found on main")
        self.assertEqual(platform_result["findings"], [])
        self.assertNotIn("source_error", platform_result)

    def test_build_summary_does_not_add_new_gradle_advisories_when_android_evidence_is_missing(self) -> None:
        baseline, _ = load_case("baseline-match")
        runner_images_only = load_source_rules_case("runner-images-promoted")
        gradle_promoted = load_source_rules_case("android-gradle-promoted")
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

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("clean"),
            create=True,
        ):
            runner_images_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=runner_images_only,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )
            gradle_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=gradle_promoted,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertEqual(runner_images_summary["reason"], "missing-evidence")
        self.assertEqual(gradle_summary["reason"], "missing-evidence")
        self.assertEqual(gradle_summary["advisory_count"], runner_images_summary["advisory_count"])
        android_gradle = {group["key"]: group for group in gradle_summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "no review-needed")
        self.assertEqual(android_gradle["outcome"], "source-skipped")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-skipped")
        self.assertEqual(platform_result["skip_reason"], "no successful android-emulator-smoke.yml run found on main")
        self.assertEqual(platform_result["review_needed_findings"], [])
        self.assertNotIn("source_error", platform_result)

    def test_build_summary_keeps_gradle_skipped_when_android_evidence_is_missing_and_fetch_fails(self) -> None:
        baseline, _ = load_case("baseline-match")
        runner_images_only = load_source_rules_case("runner-images-promoted")
        gradle_promoted = load_source_rules_case("android-gradle-promoted")
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

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ):
            runner_images_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=runner_images_only,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            side_effect=MODULE.RunnerHostWatchError("synthetic gradle fetch failure"),
            create=True,
        ):
            gradle_summary = MODULE.build_summary(
                repo="drousselhq/casgrain",
                baseline=baseline,
                source_rules=gradle_promoted,
                observed_platforms=json.loads(json.dumps(observed_platforms)),
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertEqual(runner_images_summary["reason"], "missing-evidence")
        self.assertEqual(gradle_summary["reason"], "missing-evidence")
        self.assertEqual(gradle_summary["advisory_count"], runner_images_summary["advisory_count"])
        android_gradle = {group["key"]: group for group in gradle_summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "no review-needed")
        self.assertEqual(android_gradle["outcome"], "source-skipped")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-skipped")
        self.assertEqual(platform_result["skip_reason"], "no successful android-emulator-smoke.yml run found on main")
        self.assertEqual(platform_result["review_needed_findings"], [])
        self.assertNotIn("source_error", platform_result)

    def test_normalize_source_rules_rejects_non_official_android_gradle_catalog_url(self) -> None:
        baseline, _ = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")
        source_rules = json.loads(json.dumps(source_rules))
        for group in source_rules["groups"]:
            if group["key"] == "android-gradle":
                group["source_catalog_url"] = "https://example.invalid/not-gradle"
                break
        else:
            self.fail("android-gradle source rule fixture missing")

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.normalize_source_rules(
                source_rules,
                normalized_baseline=MODULE.normalize_baseline(baseline),
            )

        self.assertIn("source_catalog_url must be", str(error.exception))
        self.assertIn("https://services.gradle.org/versions/all", str(error.exception))

    def test_build_summary_promotes_android_gradle_with_recognized_stable_versions(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("clean"),
            create=True,
        ):
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
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["rule_kind"], "gradle-release-catalog")
        self.assertEqual(android_gradle["status"], "no review-needed")
        self.assertEqual(android_gradle["outcome"], "source-match")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["platform"], "android")
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-match")
        self.assertEqual(platform_result["review_needed_findings"], [])
        self.assertNotIn("source_advisory_count", summary)

    def test_build_summary_flags_android_gradle_source_review_needed_for_unrecognized_versions(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")
        fixture_input["platforms"]["android"]["host_environment"]["gradle"]["configured_version"] = "8.7-local"

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("clean"),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "baseline-drift")
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["advisory_count"], 2)
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-review-needed")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-review-needed")
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "unrecognized-configured-version")
        self.assertEqual(platform_result["review_needed_findings"][0]["observed"], "8.7-local")

    def test_build_summary_flags_android_gradle_source_review_needed_for_broken_versions(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("broken"),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["advisory_count"], 1)
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-review-needed")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "broken-resolved-version")
        self.assertEqual(platform_result["review_needed_findings"][0]["observed"], "8.7")

    def test_build_summary_keeps_newer_gradle_release_informational_only(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("newer-release-available"),
            create=True,
        ):
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
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "no review-needed")
        self.assertEqual(platform_result["outcome"], "source-match")
        self.assertEqual(platform_result["review_needed_findings"], [])
        self.assertEqual(platform_result["informational_findings"][0]["kind"], "newer-stable-release-available")
        self.assertEqual(platform_result["informational_findings"][0]["latest_stable_version"], "8.8")

    def test_build_summary_fails_closed_when_android_gradle_source_is_contradictory(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("contradictory-current"),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["advisory_count"], 1)
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-error")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-error")
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "source-unavailable")
        self.assertIn("multiple current stable releases", platform_result["source_error"])

    def test_build_summary_fails_closed_when_gradle_current_stable_is_not_latest_stable(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("current-not-latest"),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        self.assertEqual(summary["advisory_count"], 1)
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-error")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-error")
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "source-unavailable")
        self.assertIn("current stable release 8.7", platform_result["source_error"])
        self.assertIn("latest stable release 8.8", platform_result["source_error"])

    def test_build_summary_fails_closed_when_android_gradle_source_uses_conflicting_duplicate_stable_records(self) -> None:
        payload = [
            {
                "version": "8.7",
                "current": True,
                "snapshot": False,
                "nightly": False,
                "releaseNightly": False,
                "broken": False,
                "activeRc": False,
                "rcFor": None,
                "milestoneFor": None,
            },
            {
                "version": "8.7",
                "current": False,
                "snapshot": False,
                "nightly": False,
                "releaseNightly": False,
                "broken": True,
                "activeRc": False,
                "rcFor": None,
                "milestoneFor": None,
            },
        ]

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.normalize_gradle_release_catalog_payload(
                payload,
                error_context="Gradle release catalog",
            )

        self.assertIn("conflicting stable release records for 8.7", str(error.exception))

    def test_build_summary_fails_closed_when_android_gradle_source_is_unavailable(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")
        error_payload = load_gradle_source_case("source-error")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            side_effect=MODULE.RunnerHostWatchError(str(error_payload["error"])),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-error")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-error")
        self.assertEqual(platform_result["source_error"], str(error_payload["error"]))
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "source-unavailable")

    def test_build_summary_fails_closed_when_android_gradle_source_payload_is_malformed(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE,
            "fetch_gradle_release_catalog_for_group",
            return_value=load_gradle_source_case("malformed"),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-error")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-error")
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "source-unavailable")

    def test_build_summary_fails_closed_when_android_gradle_source_response_bytes_are_not_utf8(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("android-gradle-promoted")

        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload

            def read(self) -> bytes:
                return self.payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=load_runner_image_source_case("clean"),
            create=True,
        ), patch.object(
            MODULE.urllib.request,
            "urlopen",
            return_value=FakeResponse(b"\xff\xfe\xfa"),
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "source-review-needed")
        self.assertEqual(summary["verdict"], "manual-review-required")
        android_gradle = {group["key"]: group for group in summary["source_rule_groups"]}["android-gradle"]
        self.assertEqual(android_gradle["status"], "manual-review-required")
        self.assertEqual(android_gradle["outcome"], "source-error")
        platform_result = android_gradle["platform_results"][0]
        self.assertEqual(platform_result["status"], "manual-review-required")
        self.assertEqual(platform_result["outcome"], "source-error")
        self.assertEqual(platform_result["review_needed_findings"][0]["kind"], "source-unavailable")
        self.assertIn("did not return valid UTF-8 JSON", platform_result["source_error"])

    def test_build_summary_promotes_runner_images_with_clean_source_match(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")
        runner_image_source = load_runner_image_source_case("clean")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=runner_image_source,
            create=True,
        ):
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

        runner_images = {group["key"]: group for group in summary["source_rule_groups"]}["runner-images"]
        self.assertEqual(runner_images["rule_kind"], "runner-image-release-metadata")
        self.assertEqual(runner_images["status"], "no review-needed")
        self.assertEqual(runner_images["outcome"], "source-match")
        self.assertEqual(
            [result["platform"] for result in runner_images["platform_results"]],
            ["android", "ios"],
        )
        self.assertEqual(
            runner_images["platform_results"][0]["observed"],
            {
                "runner.image_version": "20260413.86.1",
                "runner.os_version": "24.04.4",
            },
        )
        self.assertEqual(
            runner_images["platform_results"][1]["source"],
            {
                "runner.image_version": "20260414.0270.1",
                "runner.os_version": "15.7.4",
                "runner.os_build": "24G517",
            },
        )

        markdown = MODULE.render_markdown(summary)
        self.assertIn("source-match", markdown)
        self.assertIn("runner-images", markdown)

    def test_build_summary_promotes_android_emulator_runtime_with_clean_source_match(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("emulator-promoted")

        with patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("clean", source_rules),
        ):
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
        emulator_group = {group["key"]: group for group in summary["source_rule_groups"]}["android-emulator-runtime"]
        self.assertEqual(emulator_group["rule_kind"], "android-system-image-catalog")
        self.assertEqual(emulator_group["status"], "no review-needed")
        self.assertEqual(emulator_group["outcome"], "source-match")
        self.assertEqual(emulator_group["source"]["mapped_os_version"], "14")
        self.assertNotIn("source_advisory_count", summary)
        markdown = MODULE.render_markdown(summary)
        self.assertIn("android-system-image-catalog", markdown)

    def test_build_summary_flags_android_emulator_runtime_when_system_image_package_is_missing(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("emulator-promoted")

        with patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("missing-package", source_rules),
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "android-emulator-runtime-source-review-needed")
        emulator_group = {group["key"]: group for group in summary["source_rule_groups"]}["android-emulator-runtime"]
        self.assertEqual(emulator_group["status"], "manual-review-required")
        self.assertEqual(emulator_group["outcome"], "source-review-needed")
        self.assertEqual(emulator_group["findings"][0]["code"], "system-image-package-missing")

    def test_build_summary_flags_android_emulator_runtime_when_api_version_mapping_mismatches(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("emulator-promoted")

        with patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("api-runtime-mismatch", source_rules),
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "android-emulator-runtime-source-review-needed")
        emulator_group = {group["key"]: group for group in summary["source_rule_groups"]}["android-emulator-runtime"]
        self.assertEqual(emulator_group["status"], "manual-review-required")
        self.assertEqual(emulator_group["outcome"], "source-review-needed")
        self.assertEqual(emulator_group["findings"][0]["code"], "android-version-mismatch")

    def test_build_summary_keeps_android_emulator_runtime_clean_when_only_newer_upstream_revision_exists(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("emulator-promoted")

        with patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("newer-revision-only", source_rules),
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["reason"], "baseline-match")
        emulator_group = {group["key"]: group for group in summary["source_rule_groups"]}["android-emulator-runtime"]
        self.assertEqual(emulator_group["status"], "no review-needed")
        self.assertEqual(emulator_group["outcome"], "source-match")

    def test_build_summary_fails_closed_when_android_emulator_source_payload_is_malformed(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("emulator-promoted")

        with patch.object(
            MODULE,
            "fetch_text_url",
            side_effect=emulator_source_side_effect("malformed", source_rules),
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        self.assertEqual(summary["reason"], "android-emulator-runtime-source-review-needed")
        emulator_group = {group["key"]: group for group in summary["source_rule_groups"]}["android-emulator-runtime"]
        self.assertEqual(emulator_group["status"], "manual-review-required")
        self.assertEqual(emulator_group["outcome"], "source-error")
        self.assertIn("system image catalog", emulator_group["source_error"].lower())

    def test_build_summary_uses_latest_runner_image_release_stream_for_source_drift(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")

        release_list_url = "https://api.github.com/repos/actions/runner-images/releases?per_page=100"
        android_release_url = "https://api.github.com/repos/actions/runner-images/releases/tags/ubuntu24%2F20260420.95"
        ios_release_url = "https://api.github.com/repos/actions/runner-images/releases/tags/macos-15-arm64%2F20260421.0007"
        android_asset_url = "https://example.invalid/internal.ubuntu24.json"
        ios_asset_url = "https://example.invalid/internal.macos-15-arm64.json"

        def fake_fetch_json_url(url: str) -> object:
            if url == release_list_url:
                return [
                    {"tag_name": "ubuntu24/20260420.95"},
                    {"tag_name": "macos-15-arm64/20260421.0007"},
                    {"tag_name": "ubuntu24/20260413.86"},
                    {"tag_name": "macos-15-arm64/20260414.0270"},
                ]
            if url == android_release_url:
                return {
                    "assets": [
                        {
                            "name": "internal.ubuntu24.json",
                            "browser_download_url": android_asset_url,
                        }
                    ]
                }
            if url == ios_release_url:
                return {
                    "assets": [
                        {
                            "name": "internal.macos-15-arm64.json",
                            "browser_download_url": ios_asset_url,
                        }
                    ]
                }
            if url == android_asset_url:
                return {
                    "Children": [
                        {"NodeType": "ToolVersionNode", "ToolName": "Image Version:", "Version": "20260420.95.1"},
                        {"NodeType": "ToolVersionNode", "ToolName": "OS Version:", "Version": "Ubuntu 24.04.5 LTS"},
                    ]
                }
            if url == ios_asset_url:
                return {
                    "Children": [
                        {"NodeType": "ToolVersionNode", "ToolName": "Image Version:", "Version": "20260421.0007.1"},
                        {"NodeType": "ToolVersionNode", "ToolName": "OS Version:", "Version": "macOS 15.7.5 (24G520)"},
                    ]
                }
            raise AssertionError(f"unexpected runner-image source URL: {url}")

        with patch.object(MODULE, "fetch_json_url", side_effect=fake_fetch_json_url):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "runner-images-source-drift")
        runner_images = {group["key"]: group for group in summary["source_rule_groups"]}["runner-images"]
        android_result = next(result for result in runner_images["platform_results"] if result["platform"] == "android")
        ios_result = next(result for result in runner_images["platform_results"] if result["platform"] == "ios")
        self.assertEqual(android_result["source"]["runner.image_version"], "20260420.95.1")
        self.assertEqual(android_result["source"]["runner.os_version"], "24.04.5")
        self.assertEqual(ios_result["source"]["runner.image_version"], "20260421.0007.1")
        self.assertEqual(ios_result["source"]["runner.os_version"], "15.7.5")
        self.assertEqual(ios_result["source"]["runner.os_build"], "24G520")

    def test_build_summary_flags_runner_images_android_source_drift(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")
        runner_image_source = load_runner_image_source_case("android-actionable")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=runner_image_source,
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "runner-images-source-drift")
        self.assertEqual(summary["verdict"], "manual-review-required")
        runner_images = {group["key"]: group for group in summary["source_rule_groups"]}["runner-images"]
        self.assertEqual(runner_images["status"], "manual-review-required")
        self.assertEqual(runner_images["outcome"], "source-drift")
        android_result = next(result for result in runner_images["platform_results"] if result["platform"] == "android")
        self.assertEqual(android_result["status"], "manual-review-required")
        self.assertEqual(android_result["outcome"], "source-drift")
        self.assertEqual(
            android_result["changed_facts"],
            [
                {
                    "path": "runner.image_version",
                    "observed": "20260413.86.1",
                    "source": "20260420.95.1",
                },
                {
                    "path": "runner.os_version",
                    "observed": "24.04.4",
                    "source": "24.04.5",
                },
            ],
        )

    def test_build_summary_flags_runner_images_ios_source_drift(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")
        runner_image_source = load_runner_image_source_case("ios-actionable")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            return_value=runner_image_source,
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "runner-images-source-drift")
        self.assertEqual(summary["verdict"], "manual-review-required")
        runner_images = {group["key"]: group for group in summary["source_rule_groups"]}["runner-images"]
        ios_result = next(result for result in runner_images["platform_results"] if result["platform"] == "ios")
        self.assertEqual(ios_result["status"], "manual-review-required")
        self.assertEqual(ios_result["outcome"], "source-drift")
        self.assertEqual(
            ios_result["changed_facts"],
            [
                {
                    "path": "runner.image_version",
                    "observed": "20260414.0270.1",
                    "source": "20260421.0007.1",
                },
                {
                    "path": "runner.os_version",
                    "observed": "15.7.4",
                    "source": "15.7.5",
                },
                {
                    "path": "runner.os_build",
                    "observed": "24G517",
                    "source": "24G520",
                },
            ],
        )

    def test_build_summary_fails_closed_when_runner_image_source_errors(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")
        error_payload = load_runner_image_source_case("source-error")

        with patch.object(
            MODULE,
            "fetch_runner_image_source_for_group",
            side_effect=MODULE.RunnerHostWatchError(str(error_payload["error"])),
            create=True,
        ):
            summary = MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["reason"], "runner-images-source-error")
        self.assertEqual(summary["verdict"], "manual-review-required")
        runner_images = {group["key"]: group for group in summary["source_rule_groups"]}["runner-images"]
        self.assertEqual(runner_images["status"], "manual-review-required")
        self.assertEqual(runner_images["outcome"], "source-error")
        for result in runner_images["platform_results"]:
            self.assertEqual(result["status"], "manual-review-required")
            self.assertEqual(result["outcome"], "source-error")
            self.assertEqual(result["source_error"], str(error_payload["error"]))
            self.assertEqual(result["changed_facts"], [])

    def test_build_summary_fails_closed_when_promoted_runner_images_source_streams_drift(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("runner-images-promoted")
        source_rules["groups"][0]["source_streams"]["android"]["runner_label"] = "ubuntu-22.04"

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("source_streams", str(error.exception))
        self.assertIn("runner-images", str(error.exception))

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

    def test_build_summary_fails_closed_when_split_android_group_uses_wrong_platforms(self) -> None:
        baseline, fixture_input = load_case("baseline-match")
        source_rules = load_source_rules_case("valid")
        key_map = {group["key"]: group for group in source_rules["groups"]}
        key_map["android-java"]["platforms"] = ["android", "ios"]

        with self.assertRaises(MODULE.RunnerHostWatchError) as error:
            MODULE.build_summary(
                repo=str(fixture_input["repo"]),
                baseline=baseline,
                source_rules=source_rules,
                observed_platforms=fixture_input["platforms"],
                generated_at="2026-04-19T09:00:00Z",
            )

        self.assertIn("android-java", str(error.exception))
        self.assertIn("platforms", str(error.exception))

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
