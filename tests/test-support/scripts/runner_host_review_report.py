#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_MARKER = "<!-- cve-watch-report -->"
MAX_RUN_LIMIT = 50
EXPECTED_SOURCE_RULE_GROUPS = {
    "runner-images": 143,
    "android-java": 154,
    "android-gradle": 155,
    "android-emulator-runtime": 156,
    "ios-xcode-simulator": [164, 165],
}
EXPECTED_SOURCE_RULE_PLATFORMS = {
    "runner-images": ["android", "ios"],
    "android-java": ["android"],
    "android-gradle": ["android"],
    "android-emulator-runtime": ["android"],
    "ios-xcode-simulator": ["ios"],
}
EXPECTED_SOURCE_RULE_FACT_PATHS = {
    "runner-images": {
        ("android", "runner.label"),
        ("android", "runner.image_name"),
        ("android", "runner.image_version"),
        ("android", "runner.os_version"),
        ("ios", "runner.label"),
        ("ios", "runner.image_name"),
        ("ios", "runner.image_version"),
        ("ios", "runner.os_version"),
        ("ios", "runner.os_build"),
    },
    "android-java": {
        ("android", "java.configured_major"),
        ("android", "java.resolved_version"),
    },
    "android-gradle": {
        ("android", "gradle.configured_version"),
        ("android", "gradle.resolved_version"),
    },
    "android-emulator-runtime": {
        ("android", "emulator.api_level"),
        ("android", "emulator.device_name"),
        ("android", "emulator.os_version"),
    },
    "ios-xcode-simulator": {
        ("ios", "xcode.app_path"),
        ("ios", "xcode.version"),
        ("ios", "xcode.simulator_sdk_version"),
        ("ios", "simulator.runtime_identifier"),
        ("ios", "simulator.runtime_name"),
        ("ios", "simulator.device_name"),
    },
}
EXPECTED_RUNNER_IMAGE_SOURCE_STREAMS = {
    "android": {
        "runner_label": "ubuntu-latest",
        "image_name": "ubuntu-24.04",
        "compared_facts": ["runner.image_version", "runner.os_version"],
    },
    "ios": {
        "runner_label": "macos-15",
        "image_name": "macos-15-arm64",
        "compared_facts": ["runner.image_version", "runner.os_version", "runner.os_build"],
    },
}
RUNNER_IMAGE_RELEASE_REPO = "actions/runner-images"
RUNNER_IMAGE_RELEASES_URL = f"https://api.github.com/repos/{RUNNER_IMAGE_RELEASE_REPO}/releases?per_page=100"
RUNNER_IMAGE_RELEASE_TAG_PREFIXES = {
    "ubuntu-24.04": "ubuntu24",
    "macos-15-arm64": "macos-15-arm64",
}
JAVA_RELEASE_CATALOG_URL = "https://api.adoptium.net/v3/info/available_releases"
JAVA_VERSION_LOOKUP_URL_TEMPLATE = (
    "https://api.adoptium.net/v3/assets/version/{version}?architecture=x64&heap_size=normal"
    "&image_type=jdk&jvm_impl=hotspot&os=linux&page=0&page_size=1&project=jdk"
    "&release_type=ga&vendor=eclipse"
)
JAVA_SUPPORTED_MAJOR_POLICY = "available_lts_plus_latest_feature"
JAVA_SOURCE_DISTRIBUTION = "temurin"
JAVA_SOURCE_VENDOR = "eclipse"
ALLOWED_SOURCE_RULE_KINDS = {
    "manual-review-required",
    "runner-image-release-metadata",
    "java-release-support",
    "android-system-image-catalog",
}
ANDROID_VERSION_MAPPING_ROW_RE = re.compile(
    r"Android[^<]*</td>\s*<td>(?P<version>\d+(?:\.\d+)?)</td>\s*<td>API level (?P<api>\d+)</td>",
    re.IGNORECASE,
)


class RunnerHostWatchError(Exception):
    """Raised when runner-host watch inputs cannot be parsed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a runner-image / host-toolchain drift report from mobile smoke artifacts."
    )
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name form")
    parser.add_argument("--baseline", required=True, help="Path to .github/runner-host-watch.json")
    parser.add_argument(
        "--source-rules",
        default="",
        help="Optional path to .github/runner-host-advisory-sources.json; defaults next to --baseline",
    )
    parser.add_argument("--android-workflow", required=True, help="Android smoke workflow file name")
    parser.add_argument("--android-artifact", required=True, help="Android smoke artifact name")
    parser.add_argument("--ios-workflow", required=True, help="iOS smoke workflow file name")
    parser.add_argument("--ios-artifact", required=True, help="iOS smoke artifact name")
    parser.add_argument("--summary-out", required=True, help="Path to write machine-readable JSON summary")
    parser.add_argument("--markdown-out", required=True, help="Path to write markdown summary")
    parser.add_argument(
        "--input",
        default="",
        help="Optional fixture input JSON; when set, skip live GitHub collection",
    )
    parser.add_argument(
        "--generated-at",
        default="",
        help="Optional ISO-8601 UTC timestamp override",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_file(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerHostWatchError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerHostWatchError(f"JSON file is not valid JSON: {path}") from exc


def required_object_field(container: dict[str, Any], field_name: str, *, error_context: str) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, dict):
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be an object")
    return value


def required_list_field(container: dict[str, Any], field_name: str, *, error_context: str) -> list[Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, list):
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be a list")
    return value


def required_scalar_field(container: dict[str, Any], field_name: str, *, error_context: str) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, ""):
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be present and non-empty")
    if isinstance(value, (dict, list, tuple, set, bool)):
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be a scalar value")
    return str(value)


def required_string_field(container: dict[str, Any], field_name: str, *, error_context: str) -> str:
    value = container.get(field_name, ...)
    if not isinstance(value, str) or value == "":
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be a non-empty string")
    return value


def required_int_field(container: dict[str, Any], field_name: str, *, error_context: str) -> int:
    value = container.get(field_name, ...)
    if type(value) is not int:
        raise RunnerHostWatchError(f"{error_context} field '{field_name}' must be an integer")
    return value


def validate_host_environment_contract(
    host_environment: dict[str, Any], *, error_context: str, platform_name: str
) -> dict[str, Any]:
    required_scalar_field(host_environment, "generated_at", error_context=error_context)
    workflow_run = required_object_field(host_environment, "workflow_run", error_context=error_context)
    for field_name in ("repository", "workflow", "run_id", "run_attempt", "run_url"):
        required_scalar_field(workflow_run, field_name, error_context=f"{error_context} workflow_run")
    runner = required_object_field(host_environment, "runner", error_context=error_context)
    for field_name in ("label", "image_name", "image_version", "os_name", "os_version"):
        required_scalar_field(runner, field_name, error_context=f"{error_context} runner")
    if platform_name == "ios":
        required_scalar_field(runner, "os_build", error_context=f"{error_context} runner")
        xcode = required_object_field(host_environment, "xcode", error_context=error_context)
        for field_name in ("app_path", "version", "simulator_sdk_version"):
            required_scalar_field(xcode, field_name, error_context=f"{error_context} xcode")
        simulator = required_object_field(host_environment, "simulator", error_context=error_context)
        for field_name in ("runtime_identifier", "runtime_name", "device_name"):
            required_scalar_field(simulator, field_name, error_context=f"{error_context} simulator")
        return host_environment
    if platform_name != "android":
        raise RunnerHostWatchError(f"unsupported runner-host platform '{platform_name}'")
    for group_name, required_fields in {
        "java": ("distribution", "configured_major", "resolved_version"),
        "gradle": ("configured_version", "resolved_version"),
        "emulator": ("api_level", "device_name", "os_version"),
    }.items():
        group = required_object_field(host_environment, group_name, error_context=error_context)
        for field_name in required_fields:
            required_scalar_field(group, field_name, error_context=f"{error_context} {group_name}")
    return host_environment


def optional_scalar_field(container: dict[str, Any], field_name: str, *, default: str = "") -> str:
    value = container.get(field_name, default)
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list, tuple, set, bool)):
        return default
    return str(value)


def normalize_baseline(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RunnerHostWatchError("runner-host baseline JSON root must be an object")
    platforms = required_object_field(data, "platforms", error_context="runner-host baseline")
    normalized_platforms: dict[str, Any] = {}
    for platform_name in ("android", "ios"):
        platform = required_object_field(platforms, platform_name, error_context="runner-host baseline platforms")
        watched = required_list_field(platform, "watched_facts", error_context=f"runner-host baseline {platform_name}")
        if not watched:
            raise RunnerHostWatchError(f"runner-host baseline {platform_name} must define at least one watched fact")
        normalized_watched: list[dict[str, str]] = []
        for index, entry in enumerate(watched):
            if not isinstance(entry, dict):
                raise RunnerHostWatchError(
                    f"runner-host baseline {platform_name} watched_facts[{index}] must be an object"
                )
            normalized_watched.append(
                {
                    "path": required_scalar_field(
                        entry,
                        "path",
                        error_context=f"runner-host baseline {platform_name} watched_facts[{index}]",
                    ),
                    "label": required_scalar_field(
                        entry,
                        "label",
                        error_context=f"runner-host baseline {platform_name} watched_facts[{index}]",
                    ),
                    "baseline": required_scalar_field(
                        entry,
                        "baseline",
                        error_context=f"runner-host baseline {platform_name} watched_facts[{index}]",
                    ),
                }
            )
        normalized_platforms[platform_name] = {
            "workflow": required_scalar_field(
                platform,
                "workflow",
                error_context=f"runner-host baseline {platform_name}",
            ),
            "artifact": required_scalar_field(
                platform,
                "artifact",
                error_context=f"runner-host baseline {platform_name}",
            ),
            "branch": required_scalar_field(
                platform,
                "branch",
                error_context=f"runner-host baseline {platform_name}",
            ),
            "watched_facts": normalized_watched,
        }
    return {
        "issue_title": required_scalar_field(data, "issue_title", error_context="runner-host baseline"),
        "scope": required_scalar_field(data, "scope", error_context="runner-host baseline"),
        "platforms": normalized_platforms,
    }


def build_baseline_fact_index(normalized_baseline: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    fact_index: dict[tuple[str, str], dict[str, str]] = {}
    for platform_name, platform in normalized_baseline["platforms"].items():
        for watched in platform["watched_facts"]:
            fact_index[(platform_name, watched["path"])] = watched
    return fact_index


def normalize_runner_image_source_streams(entry: dict[str, Any], *, error_context: str) -> dict[str, Any]:
    raw_source_streams = required_object_field(entry, "source_streams", error_context=error_context)
    normalized_streams: dict[str, Any] = {}
    seen_platforms: set[str] = set()
    for platform_name, expected in EXPECTED_RUNNER_IMAGE_SOURCE_STREAMS.items():
        stream = required_object_field(raw_source_streams, platform_name, error_context=f"{error_context} source_streams")
        seen_platforms.add(platform_name)
        runner_label = required_string_field(
            stream,
            "runner_label",
            error_context=f"{error_context} source_streams.{platform_name}",
        )
        image_name = required_string_field(
            stream,
            "image_name",
            error_context=f"{error_context} source_streams.{platform_name}",
        )
        compared_facts_raw = required_list_field(
            stream,
            "compared_facts",
            error_context=f"{error_context} source_streams.{platform_name}",
        )
        compared_facts: list[str] = []
        for index, fact in enumerate(compared_facts_raw):
            if not isinstance(fact, str) or not fact:
                raise RunnerHostWatchError(
                    f"{error_context} source_streams.{platform_name} compared_facts[{index}] must be a non-empty string"
                )
            compared_facts.append(fact)
        if runner_label != expected["runner_label"]:
            raise RunnerHostWatchError(
                f"{error_context} source_streams.{platform_name}.runner_label must be {expected['runner_label']!r}"
            )
        if image_name != expected["image_name"]:
            raise RunnerHostWatchError(
                f"{error_context} source_streams.{platform_name}.image_name must be {expected['image_name']!r}"
            )
        if compared_facts != expected["compared_facts"]:
            raise RunnerHostWatchError(
                f"{error_context} source_streams.{platform_name}.compared_facts must be {expected['compared_facts']!r}"
            )
        normalized_streams[platform_name] = {
            "runner_label": runner_label,
            "image_name": image_name,
            "compared_facts": compared_facts,
        }
    extra_platforms = sorted(set(raw_source_streams) - seen_platforms)
    if extra_platforms:
        raise RunnerHostWatchError(
            f"{error_context} source_streams must not define extra platforms: {extra_platforms}"
        )
    return normalized_streams


def normalize_android_system_image_catalogs(entry: dict[str, Any], *, error_context: str) -> dict[str, str]:
    source_catalogs = required_object_field(entry, "source_catalogs", error_context=error_context)
    return {
        "platform_catalog_url": required_string_field(
            source_catalogs,
            "platform_catalog_url",
            error_context=f"{error_context} source_catalogs",
        ),
        "system_image_catalog_url": required_string_field(
            source_catalogs,
            "system_image_catalog_url",
            error_context=f"{error_context} source_catalogs",
        ),
        "version_mapping_url": required_string_field(
            source_catalogs,
            "version_mapping_url",
            error_context=f"{error_context} source_catalogs",
        ),
    }


def normalize_source_rules(data: Any, *, normalized_baseline: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RunnerHostWatchError("runner-host source rules JSON root must be an object")
    groups = required_list_field(data, "groups", error_context="runner-host source rules")
    fact_index = build_baseline_fact_index(normalized_baseline)
    normalized_groups: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_fact_paths: set[tuple[str, str]] = set()

    for index, entry in enumerate(groups):
        if not isinstance(entry, dict):
            raise RunnerHostWatchError(f"runner-host source rules groups[{index}] must be an object")
        error_context = f"runner-host source rules groups[{index}]"
        key = required_string_field(entry, "key", error_context=error_context)
        if key not in EXPECTED_SOURCE_RULE_GROUPS:
            raise RunnerHostWatchError(f"{error_context} field 'key' must be one of {sorted(EXPECTED_SOURCE_RULE_GROUPS)}")
        if key in seen_keys:
            raise RunnerHostWatchError(f"duplicate source-rule group key '{key}'")
        seen_keys.add(key)

        platforms_raw = required_list_field(entry, "platforms", error_context=error_context)
        if not platforms_raw:
            raise RunnerHostWatchError(f"{error_context} field 'platforms' must list at least one platform")
        platforms: list[str] = []
        for platform_index, platform_name in enumerate(platforms_raw):
            if not isinstance(platform_name, str) or platform_name not in normalized_baseline["platforms"]:
                raise RunnerHostWatchError(
                    f"{error_context} platforms[{platform_index}] must be one of {sorted(normalized_baseline['platforms'])}"
                )
            platforms.append(platform_name)
        expected_platforms = EXPECTED_SOURCE_RULE_PLATFORMS[key]
        if platforms != expected_platforms:
            raise RunnerHostWatchError(
                f"{error_context} field 'platforms' must match expected platforms for source-rule group '{key}'; "
                f"expected={expected_platforms} actual={platforms}"
            )

        rule_kind = required_string_field(entry, "rule_kind", error_context=error_context)
        if rule_kind not in ALLOWED_SOURCE_RULE_KINDS:
            raise RunnerHostWatchError(
                f"{error_context} field 'rule_kind' must be one of {sorted(ALLOWED_SOURCE_RULE_KINDS)}"
            )
        if key == "runner-images":
            allowed_rule_kinds = {"manual-review-required", "runner-image-release-metadata"}
        elif key == "android-java":
            allowed_rule_kinds = {"manual-review-required", "java-release-support"}
        elif key == "android-emulator-runtime":
            allowed_rule_kinds = {"manual-review-required", "android-system-image-catalog"}
        else:
            allowed_rule_kinds = {"manual-review-required"}
        if rule_kind not in allowed_rule_kinds:
            raise RunnerHostWatchError(
                f"{error_context} source-rule group '{key}' must use one of {sorted(allowed_rule_kinds)} on current main"
            )
        rationale = required_string_field(entry, "rationale", error_context=error_context)
        expected_issue = EXPECTED_SOURCE_RULE_GROUPS[key]
        if isinstance(expected_issue, list):
            follow_up_issues = required_list_field(entry, "follow_up_issues", error_context=error_context)
            if follow_up_issues != expected_issue or not all(isinstance(value, int) for value in follow_up_issues):
                raise RunnerHostWatchError(
                    f"{error_context} field 'follow_up_issues' must be {expected_issue} for source-rule group '{key}'"
                )
            follow_up_issue = None
            live_follow_up_issues = follow_up_issues
        else:
            follow_up_issue = required_int_field(entry, "follow_up_issue", error_context=error_context)
            if follow_up_issue != expected_issue:
                raise RunnerHostWatchError(
                    f"{error_context} field 'follow_up_issue' must be {expected_issue} for source-rule group '{key}'"
                )
            live_follow_up_issues = [follow_up_issue]

        watched_fact_paths = required_list_field(entry, "watched_fact_paths", error_context=error_context)
        if not watched_fact_paths:
            raise RunnerHostWatchError(f"{error_context} field 'watched_fact_paths' must include at least one path")
        normalized_paths: list[dict[str, str]] = []
        group_fact_paths: set[tuple[str, str]] = set()
        for path_index, path_entry in enumerate(watched_fact_paths):
            if not isinstance(path_entry, dict):
                raise RunnerHostWatchError(f"{error_context} watched_fact_paths[{path_index}] must be an object")
            path_context = f"{error_context} watched_fact_paths[{path_index}]"
            platform_name = required_string_field(path_entry, "platform", error_context=path_context)
            if platform_name not in platforms:
                raise RunnerHostWatchError(
                    f"{path_context} platform '{platform_name}' must be declared in group platforms {platforms}"
                )
            path = required_string_field(path_entry, "path", error_context=path_context)
            fact_key = (platform_name, path)
            if fact_key not in fact_index:
                raise RunnerHostWatchError(
                    f"{path_context} watched fact path '{platform_name}.{path}' is not defined in .github/runner-host-watch.json"
                )
            if fact_key in seen_fact_paths:
                raise RunnerHostWatchError(
                    f"{path_context} watched fact path '{platform_name}.{path}' is owned by more than one source-rule group"
                )
            seen_fact_paths.add(fact_key)
            group_fact_paths.add(fact_key)
            normalized_paths.append(
                {
                    "platform": platform_name,
                    "path": path,
                    "label": fact_index[fact_key]["label"],
                    "baseline": fact_index[fact_key]["baseline"],
                }
            )

        expected_fact_paths = EXPECTED_SOURCE_RULE_FACT_PATHS[key]
        if group_fact_paths != expected_fact_paths:
            missing = sorted(f"{platform}.{path}" for (platform, path) in expected_fact_paths - group_fact_paths)
            unexpected = sorted(f"{platform}.{path}" for (platform, path) in group_fact_paths - expected_fact_paths)
            raise RunnerHostWatchError(
                f"{error_context} field 'watched_fact_paths' must match expected paths for source-rule group '{key}'; "
                f"missing={missing} unexpected={unexpected}"
            )

        normalized_group = {
            "key": key,
            "surface": required_string_field(entry, "surface", error_context=error_context),
            "platforms": platforms,
            "watched_fact_paths": normalized_paths,
            "rule_kind": rule_kind,
            "rationale": rationale,
            "managed_issue_behavior": required_string_field(
                entry,
                "managed_issue_behavior",
                error_context=error_context,
            ),
            "candidate_source": required_string_field(entry, "candidate_source", error_context=error_context),
            "follow_up_issues": live_follow_up_issues,
        }
        if len(live_follow_up_issues) == 1 and follow_up_issue is not None:
            normalized_group["follow_up_issue"] = follow_up_issue
        if rule_kind == "runner-image-release-metadata":
            normalized_group["source_streams"] = normalize_runner_image_source_streams(
                entry,
                error_context=f"{error_context} source-rule group '{key}'",
            )
        elif rule_kind == "java-release-support":
            normalized_group["source_metadata"] = normalize_java_release_support_metadata(
                entry,
                error_context=f"{error_context} source-rule group '{key}'",
            )
        elif rule_kind == "android-system-image-catalog":
            normalized_group["source_catalogs"] = normalize_android_system_image_catalogs(
                entry,
                error_context=f"{error_context} source-rule group '{key}'",
            )
        normalized_groups.append(normalized_group)

    if seen_keys != set(EXPECTED_SOURCE_RULE_GROUPS):
        missing = sorted(set(EXPECTED_SOURCE_RULE_GROUPS) - seen_keys)
        extra = sorted(seen_keys - set(EXPECTED_SOURCE_RULE_GROUPS))
        raise RunnerHostWatchError(
            f"runner-host source rules groups must define exactly {sorted(EXPECTED_SOURCE_RULE_GROUPS)}; missing={missing} extra={extra}"
        )

    uncovered_fact_paths = sorted(
        f"{platform}.{path}" for (platform, path) in fact_index.keys() - seen_fact_paths
    )
    if uncovered_fact_paths:
        raise RunnerHostWatchError(
            "runner-host source rules must assign every watched fact path from .github/runner-host-watch.json; "
            f"uncovered={uncovered_fact_paths}"
        )

    managed_issue_title = required_string_field(
        data,
        "managed_issue_title",
        error_context="runner-host source rules",
    )
    if managed_issue_title != normalized_baseline["issue_title"]:
        raise RunnerHostWatchError(
            "runner-host source rules field 'managed_issue_title' must match the baseline issue_title "
            f"{normalized_baseline['issue_title']!r}"
        )

    return {
        "managed_issue_title": managed_issue_title,
        "groups": normalized_groups,
    }


def get_nested_value(container: dict[str, Any], dotted_path: str) -> tuple[str | None, bool]:
    current: Any = container
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None, False
        current = current[segment]
    if current in (None, ""):
        return None, False
    if isinstance(current, (dict, list, tuple, set, bool)):
        return json.dumps(current, sort_keys=True), True
    return str(current), True


def fetch_json_url(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Hermes-Agent",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RunnerHostWatchError(f"source fetch failed for {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RunnerHostWatchError(f"source fetch failed for {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerHostWatchError(f"source fetch did not return valid JSON for {url}") from exc


def normalize_java_release_support_metadata(entry: dict[str, Any], *, error_context: str) -> dict[str, str]:
    metadata = required_object_field(entry, "source_metadata", error_context=error_context)
    required_fields = {
        "distribution",
        "vendor",
        "release_catalog_url",
        "version_lookup_url_template",
        "supported_major_policy",
    }
    extra_fields = sorted(set(metadata) - required_fields)
    if extra_fields:
        raise RunnerHostWatchError(
            f"{error_context} source_metadata must not define extra fields: {extra_fields}"
        )
    normalized = {
        "distribution": required_string_field(metadata, "distribution", error_context=f"{error_context} source_metadata"),
        "vendor": required_string_field(metadata, "vendor", error_context=f"{error_context} source_metadata"),
        "release_catalog_url": required_string_field(
            metadata, "release_catalog_url", error_context=f"{error_context} source_metadata"
        ),
        "version_lookup_url_template": required_string_field(
            metadata, "version_lookup_url_template", error_context=f"{error_context} source_metadata"
        ),
        "supported_major_policy": required_string_field(
            metadata, "supported_major_policy", error_context=f"{error_context} source_metadata"
        ),
    }
    expected_values = {
        "distribution": JAVA_SOURCE_DISTRIBUTION,
        "vendor": JAVA_SOURCE_VENDOR,
        "release_catalog_url": JAVA_RELEASE_CATALOG_URL,
        "version_lookup_url_template": JAVA_VERSION_LOOKUP_URL_TEMPLATE,
        "supported_major_policy": JAVA_SUPPORTED_MAJOR_POLICY,
    }
    for field_name, expected in expected_values.items():
        if normalized[field_name] != expected:
            raise RunnerHostWatchError(
                f"{error_context} source_metadata.{field_name} must be {expected!r}"
            )
    return normalized


def fetch_text_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain, text/html, application/xml, text/xml;q=0.9, */*;q=0.8",
            "User-Agent": "Hermes-Agent",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")
    except urllib.error.HTTPError as exc:
        raise RunnerHostWatchError(f"source fetch failed for {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RunnerHostWatchError(f"source fetch failed for {url}: {exc.reason}") from exc


def parse_remote_package_index(xml_text: str, *, error_context: str) -> dict[str, dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RunnerHostWatchError(f"{error_context} did not return valid XML") from exc
    packages: dict[str, dict[str, str]] = {}
    for remote_package in root.findall('.//{*}remotePackage'):
        path = remote_package.attrib.get("path")
        if not isinstance(path, str) or not path:
            continue
        package_info: dict[str, str] = {}
        display_name = remote_package.findtext('{*}display-name', default='').strip()
        if display_name:
            package_info["display_name"] = display_name
        revision = remote_package.find('{*}revision')
        if revision is not None:
            revision_parts = []
            for segment_name in ("major", "minor", "micro"):
                segment_value = revision.findtext(f'{{*}}{segment_name}', default='').strip()
                if segment_value:
                    revision_parts.append(segment_value)
            if revision_parts:
                package_info["revision"] = ".".join(revision_parts)
        packages[path] = package_info
    if not packages:
        raise RunnerHostWatchError(f"{error_context} did not contain any remotePackage entries")
    return packages


def parse_android_version_mapping(html_text: str, *, error_context: str) -> dict[str, str]:
    api_to_version: dict[str, str] = {}
    for match in ANDROID_VERSION_MAPPING_ROW_RE.finditer(html_text):
        api_to_version[match.group("api")] = match.group("version")
    if not api_to_version:
        raise RunnerHostWatchError(f"{error_context} did not expose any Android version/API mappings")
    return api_to_version


def fetch_android_emulator_source_catalogs(group: dict[str, Any]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, str]]:
    source_catalogs = required_object_field(group, "source_catalogs", error_context="android-emulator-runtime source rule")
    try:
        platform_catalog_text = fetch_text_url(source_catalogs["platform_catalog_url"])
        system_image_catalog_text = fetch_text_url(source_catalogs["system_image_catalog_url"])
        version_mapping_text = fetch_text_url(source_catalogs["version_mapping_url"])
        return (
            parse_remote_package_index(platform_catalog_text, error_context="Android platform catalog"),
            parse_remote_package_index(system_image_catalog_text, error_context="Android system image catalog"),
            parse_android_version_mapping(version_mapping_text, error_context="Android version mapping catalog"),
        )
    except RunnerHostWatchError:
        raise


def fetch_latest_runner_image_release_tag(tag_prefix: str) -> str:
    releases = fetch_json_url(RUNNER_IMAGE_RELEASES_URL)
    if not isinstance(releases, list):
        raise RunnerHostWatchError("runner-image releases listing must be a list")
    for index, release in enumerate(releases):
        if not isinstance(release, dict):
            continue
        tag_name = release.get("tag_name")
        if isinstance(tag_name, str) and tag_name.startswith(f"{tag_prefix}/"):
            return tag_name
    raise RunnerHostWatchError(f"runner-image releases listing is missing a release for tag prefix {tag_prefix!r}")



def fetch_runner_image_release_payload(
    platform_name: str,
    stream: dict[str, Any],
    observed_runner: dict[str, Any],
) -> dict[str, Any]:
    image_name = required_scalar_field(observed_runner, "image_name", error_context=f"observed {platform_name} runner")
    tag_prefix = RUNNER_IMAGE_RELEASE_TAG_PREFIXES.get(image_name)
    if tag_prefix is None:
        raise RunnerHostWatchError(f"no runner-image release tag prefix is known for image_name={image_name!r}")
    tag_name = fetch_latest_runner_image_release_tag(tag_prefix)
    release_url = (
        f"https://api.github.com/repos/{RUNNER_IMAGE_RELEASE_REPO}/releases/tags/"
        f"{urllib.parse.quote(tag_name, safe='')}"
    )
    release = fetch_json_url(release_url)
    if not isinstance(release, dict):
        raise RunnerHostWatchError(f"runner-image release payload for {platform_name} must be an object")
    assets = required_list_field(release, "assets", error_context=f"runner-image release {platform_name}")
    asset_name = f"internal.{tag_prefix}.json"
    asset_url = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == asset_name:
            asset_url = required_string_field(
                asset,
                "browser_download_url",
                error_context=f"runner-image release {platform_name} asset {asset_name}",
            )
            break
    if not asset_url:
        raise RunnerHostWatchError(f"runner-image release {platform_name} is missing asset {asset_name!r}")
    return {
        "release": release,
        "asset": fetch_json_url(asset_url),
        "tag_name": tag_name,
        "runner_label": stream["runner_label"],
        "image_name": stream["image_name"],
    }


def normalize_runner_image_os_values(platform_name: str, raw_os_version: str) -> dict[str, str]:
    if platform_name == "android":
        match = re.search(r"(\d+(?:\.\d+)+)", raw_os_version)
        if match is None:
            raise RunnerHostWatchError(
                f"runner-image source {platform_name} OS Version could not be normalized from {raw_os_version!r}"
            )
        return {"os_version": match.group(1)}
    if platform_name == "ios":
        match = re.search(r"macOS\s+(\d+(?:\.\d+)+)\s*\(([^)]+)\)", raw_os_version)
        if match is None:
            raise RunnerHostWatchError(
                f"runner-image source {platform_name} OS Version could not be normalized from {raw_os_version!r}"
            )
        return {"os_version": match.group(1), "os_build": match.group(2)}
    raise RunnerHostWatchError(f"unsupported runner-image source platform {platform_name!r}")


def normalize_runner_image_source_payload(platform_name: str, payload: dict[str, Any]) -> dict[str, str]:
    asset = required_object_field(payload, "asset", error_context=f"runner-image source payload {platform_name}")
    children = required_list_field(asset, "Children", error_context=f"runner-image source payload {platform_name} asset")
    tool_versions: dict[str, str] = {}
    for index, child in enumerate(children):
        if not isinstance(child, dict) or child.get("NodeType") != "ToolVersionNode":
            continue
        tool_name = required_string_field(
            child,
            "ToolName",
            error_context=f"runner-image source payload {platform_name} asset Children[{index}]",
        )
        tool_versions[tool_name] = required_string_field(
            child,
            "Version",
            error_context=f"runner-image source payload {platform_name} asset Children[{index}]",
        )
    image_version = tool_versions.get("Image Version:")
    raw_os_version = tool_versions.get("OS Version:")
    if not image_version:
        raise RunnerHostWatchError(f"runner-image source payload {platform_name} is missing Image Version")
    if not raw_os_version:
        raise RunnerHostWatchError(f"runner-image source payload {platform_name} is missing OS Version")
    normalized = {"image_version": image_version}
    normalized.update(normalize_runner_image_os_values(platform_name, raw_os_version))
    return normalized


def fetch_runner_image_source_for_group(group: dict[str, Any], observed_platforms: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    source_by_platform: dict[str, dict[str, str]] = {}
    source_streams = required_object_field(group, "source_streams", error_context="runner-images source rule")
    for platform_name in group["platforms"]:
        stream = required_object_field(source_streams, platform_name, error_context="runner-images source rule source_streams")
        observed_platform = required_object_field(
            observed_platforms,
            platform_name,
            error_context="observed platforms",
        )
        if "host_environment_error" in observed_platform:
            raise RunnerHostWatchError(
                required_scalar_field(
                    observed_platform,
                    "host_environment_error",
                    error_context=f"observed platform {platform_name}",
                )
            )
        host_environment = required_object_field(
            observed_platform,
            "host_environment",
            error_context=f"observed platform {platform_name}",
        )
        observed_runner = required_object_field(
            host_environment,
            "runner",
            error_context=f"observed platform {platform_name} host_environment",
        )
        runner_label = required_scalar_field(observed_runner, "label", error_context=f"observed {platform_name} runner")
        image_name = required_scalar_field(observed_runner, "image_name", error_context=f"observed {platform_name} runner")
        if runner_label != stream["runner_label"]:
            raise RunnerHostWatchError(
                f"runner-images source stream selector mismatch for {platform_name}: expected runner label "
                f"{stream['runner_label']!r} observed {runner_label!r}"
            )
        if image_name != stream["image_name"]:
            raise RunnerHostWatchError(
                f"runner-images source stream selector mismatch for {platform_name}: expected image name "
                f"{stream['image_name']!r} observed {image_name!r}"
            )
        payload = fetch_runner_image_release_payload(platform_name, stream, observed_runner)
        source_by_platform[platform_name] = normalize_runner_image_source_payload(platform_name, payload)
    return source_by_platform


def normalize_java_supported_releases(payload: Any) -> list[int]:
    if not isinstance(payload, dict):
        raise RunnerHostWatchError("java release catalog must be an object")
    available_lts = required_list_field(payload, "available_lts_releases", error_context="java release catalog")
    supported_releases: set[int] = set()
    for index, value in enumerate(available_lts):
        if type(value) is not int:
            raise RunnerHostWatchError(
                f"java release catalog available_lts_releases[{index}] must be an integer"
            )
        supported_releases.add(value)
    supported_releases.add(required_int_field(payload, "most_recent_feature_release", error_context="java release catalog"))
    return sorted(supported_releases)


def normalize_java_version_match(payload: Any, *, configured_major: int, resolved_version: str) -> str | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        raise RunnerHostWatchError("java version lookup payload must be a list")
    if not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        raise RunnerHostWatchError("java version lookup payload entries must be objects")
    version_data = required_object_field(first, "version_data", error_context="java version lookup payload[0]")
    major = required_int_field(version_data, "major", error_context="java version lookup payload[0] version_data")
    semver = required_string_field(version_data, "semver", error_context="java version lookup payload[0] version_data")
    openjdk_version = required_string_field(
        version_data,
        "openjdk_version",
        error_context="java version lookup payload[0] version_data",
    )
    if major != configured_major:
        return None
    if resolved_version in {semver, openjdk_version}:
        return semver
    return None


def build_java_release_platform_result(
    platform_name: str,
    group: dict[str, Any],
    observed_platforms: dict[str, Any],
    *,
    supported_releases: list[int] | None = None,
    fetch_error: str = "",
) -> tuple[dict[str, Any], int]:
    result = {
        "platform": platform_name,
        "status": "no review-needed",
        "outcome": "source-match",
        "observed": {},
        "source": {},
        "findings": [],
        "source_error": "",
    }
    if fetch_error:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = fetch_error
        result["findings"].append({"code": "source-error", "message": fetch_error})
        return result, 1

    observed_platform = required_object_field(
        observed_platforms,
        platform_name,
        error_context="observed platforms",
    )
    if "host_environment_error" in observed_platform:
        reason = required_scalar_field(
            observed_platform,
            "host_environment_error",
            error_context=f"observed platform {platform_name}",
        )
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = reason
        result["findings"].append({"code": "source-error", "message": reason})
        return result, 1

    host_environment = required_object_field(
        observed_platform,
        "host_environment",
        error_context=f"observed platform {platform_name}",
    )
    observed_java = required_object_field(
        host_environment,
        "java",
        error_context=f"observed platform {platform_name} host_environment",
    )
    configured_major_raw = required_scalar_field(
        observed_java,
        "configured_major",
        error_context=f"observed platform {platform_name} java",
    )
    resolved_version = required_scalar_field(
        observed_java,
        "resolved_version",
        error_context=f"observed platform {platform_name} java",
    )
    result["observed"] = {
        "java.configured_major": configured_major_raw,
        "java.resolved_version": resolved_version,
    }
    if supported_releases:
        result["source"]["supported_feature_releases"] = ", ".join(str(value) for value in supported_releases)

    try:
        configured_major = int(configured_major_raw)
    except ValueError:
        configured_major = -1

    if configured_major not in (supported_releases or []):
        result["status"] = "manual-review-required"
        result["outcome"] = "unsupported-release"
        result["findings"].append(
            {
                "code": "unsupported-configured-major",
                "message": "configured Java major is outside the supported release set",
                "observed": configured_major_raw,
                "supported_feature_releases": result["source"].get("supported_feature_releases", ""),
            }
        )
        return result, 1

    metadata = required_object_field(group, "source_metadata", error_context="android-java source rule")
    version_url = required_string_field(
        metadata,
        "version_lookup_url_template",
        error_context="android-java source rule source_metadata",
    ).format(version=urllib.parse.quote(resolved_version, safe=""))
    try:
        version_payload = fetch_json_url(version_url)
    except RunnerHostWatchError as exc:
        if "HTTP 404" in str(exc):
            version_payload = None
        else:
            result["status"] = "manual-review-required"
            result["outcome"] = "source-error"
            result["source_error"] = str(exc)
            result["findings"].append({"code": "source-error", "message": str(exc)})
            return result, 1

    matched_version = normalize_java_version_match(
        version_payload,
        configured_major=configured_major,
        resolved_version=resolved_version,
    )
    if matched_version is None:
        result["status"] = "manual-review-required"
        result["outcome"] = "unrecognized-version"
        result["findings"].append(
            {
                "code": "unrecognized-resolved-version",
                "message": "resolved Java version could not be matched to authoritative metadata",
                "observed": resolved_version,
            }
        )
        return result, 1

    result["source"]["matched_release"] = matched_version
    return result, 0


def run_gh_json(arguments: list[str]) -> Any:
    completed = subprocess.run(
        ["gh", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
        raise RunnerHostWatchError(stderr)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RunnerHostWatchError("gh command did not return valid JSON") from exc


def run_gh(arguments: list[str]) -> None:
    completed = subprocess.run(
        ["gh", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
        raise RunnerHostWatchError(stderr)


def workflow_matches(configured: str, requested: str) -> bool:
    return Path(configured).name == Path(requested).name


def is_missing_successful_run_error(message: str, branch: str) -> bool:
    return message.startswith("no successful ") and message.endswith(f" run found on {branch}")


def select_latest_successful_run(repo: str, workflow: str, branch: str) -> dict[str, Any]:
    runs = run_gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--branch",
            branch,
            "--limit",
            str(MAX_RUN_LIMIT),
            "--json",
            "databaseId,url,status,conclusion,headBranch,event,createdAt,updatedAt",
        ]
    )
    if not isinstance(runs, list):
        raise RunnerHostWatchError("gh run list did not return a list")
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("status") == "completed" and run.get("conclusion") == "success" and run.get("headBranch") == branch:
            run_id = run.get("databaseId")
            run_url = run.get("url")
            if not isinstance(run_id, int) or not isinstance(run_url, str) or not run_url:
                raise RunnerHostWatchError("selected workflow run is missing id/url metadata")
            return {"id": run_id, "url": run_url}
    raise RunnerHostWatchError(f"no successful {workflow} run found on {branch}")


def read_host_environment_from_downloaded_artifact(
    run_id: int, repo: str, artifact_name: str, platform_name: str
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"runner-host-{run_id}-") as tempdir:
        download_dir = Path(tempdir)
        run_gh(
            [
                "run",
                "download",
                str(run_id),
                "--repo",
                repo,
                "--name",
                artifact_name,
                "--dir",
                str(download_dir),
            ]
        )
        host_summary = next(download_dir.rglob("host-environment.json"), None)
        if host_summary is None:
            raise RunnerHostWatchError("host-environment.json missing")
        payload = load_json_file(host_summary)
        if not isinstance(payload, dict):
            raise RunnerHostWatchError("host-environment.json root must be an object")
        return validate_host_environment_contract(
            payload,
            error_context="host-environment.json",
            platform_name=platform_name,
        )


def collect_live_platform(repo: str, workflow: str, artifact: str, branch: str, platform_name: str) -> dict[str, Any]:
    try:
        run = select_latest_successful_run(repo=repo, workflow=workflow, branch=branch)
    except RunnerHostWatchError as exc:
        if not is_missing_successful_run_error(str(exc), branch):
            raise
        return {
            "run": {"id": None, "url": None},
            "host_environment_error": str(exc),
        }
    try:
        host_environment = read_host_environment_from_downloaded_artifact(
            run["id"],
            repo,
            artifact,
            platform_name,
        )
    except RunnerHostWatchError as exc:
        return {
            "run": run,
            "host_environment_error": str(exc),
        }
    return {
        "run": run,
        "host_environment": host_environment,
    }


def normalize_fixture_platform(platform_name: str, data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RunnerHostWatchError(f"fixture platform '{platform_name}' must be an object")
    run = required_object_field(data, "run", error_context=f"fixture platform {platform_name}")
    run_id = run.get("id")
    run_url = run.get("url")
    normalized_run = {
        "id": run_id if isinstance(run_id, int) else None,
        "url": run_url if isinstance(run_url, str) and run_url else None,
    }
    if "host_environment" in data:
        if normalized_run["id"] is None or normalized_run["url"] is None:
            raise RunnerHostWatchError(f"fixture platform {platform_name} run must include numeric id and non-empty url")
        host_environment = required_object_field(data, "host_environment", error_context=f"fixture platform {platform_name}")
        return {
            "run": normalized_run,
            "host_environment": validate_host_environment_contract(
                host_environment,
                error_context=f"fixture platform {platform_name} host_environment",
                platform_name=platform_name,
            ),
        }
    reason = required_scalar_field(data, "host_environment_error", error_context=f"fixture platform {platform_name}")
    return {"run": normalized_run, "host_environment_error": reason}


def build_platform_summary(platform_name: str, baseline_platform: dict[str, Any], observed_platform: dict[str, Any]) -> tuple[dict[str, Any], int]:
    run = required_object_field(observed_platform, "run", error_context=f"observed platform {platform_name}")
    run_id = run.get("id")
    run_url = run.get("url")
    if (run_id is not None and not isinstance(run_id, int)) or (run_url is not None and not isinstance(run_url, str)):
        raise RunnerHostWatchError(f"observed platform {platform_name} run must include id/url when present")

    summary = {
        "workflow": baseline_platform["workflow"],
        "artifact": baseline_platform["artifact"],
        "run_id": run_id,
        "run_url": run_url,
        "status": "no review-needed",
        "observed": None,
        "changed_facts": [],
        "missing_facts": [],
        "missing_evidence": [],
    }

    if "host_environment_error" in observed_platform:
        reason = required_scalar_field(
            observed_platform,
            "host_environment_error",
            error_context=f"observed platform {platform_name}",
        )
        summary["status"] = "manual-review-required"
        summary["missing_evidence"].append({"reason": reason})
        for watched in baseline_platform["watched_facts"]:
            summary["missing_facts"].append(
                {
                    "path": watched["path"],
                    "label": watched["label"],
                    "expected": watched["baseline"],
                    "reason": reason,
                }
            )
        return summary, len(baseline_platform["watched_facts"])

    if not isinstance(run_id, int) or not isinstance(run_url, str) or not run_url:
        raise RunnerHostWatchError(f"observed platform {platform_name} run must include id/url")

    observed = required_object_field(observed_platform, "host_environment", error_context=f"observed platform {platform_name}")
    summary["observed"] = observed
    advisory_count = 0
    for watched in baseline_platform["watched_facts"]:
        observed_value, present = get_nested_value(observed, watched["path"])
        if not present:
            summary["status"] = "manual-review-required"
            summary["missing_facts"].append(
                {
                    "path": watched["path"],
                    "label": watched["label"],
                    "expected": watched["baseline"],
                    "reason": "observed fact missing",
                }
            )
            advisory_count += 1
            continue
        if observed_value != watched["baseline"]:
            summary["status"] = "manual-review-required"
            summary["changed_facts"].append(
                {
                    "path": watched["path"],
                    "label": watched["label"],
                    "expected": watched["baseline"],
                    "observed": observed_value,
                }
            )
            advisory_count += 1
    return summary, advisory_count


def build_runner_image_platform_result(
    platform_name: str,
    stream: dict[str, Any],
    observed_platforms: dict[str, Any],
    source_by_platform: dict[str, dict[str, str]],
    *,
    fetch_error: str = "",
) -> tuple[dict[str, Any], int]:
    result = {
        "platform": platform_name,
        "status": "no review-needed",
        "outcome": "source-match",
        "observed": {},
        "source": {},
        "changed_facts": [],
        "source_error": "",
    }
    if fetch_error:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = fetch_error
        return result, 1

    observed_platform = required_object_field(
        observed_platforms,
        platform_name,
        error_context="observed platforms",
    )
    if "host_environment_error" in observed_platform:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = required_scalar_field(
            observed_platform,
            "host_environment_error",
            error_context=f"observed platform {platform_name}",
        )
        return result, 1

    host_environment = required_object_field(
        observed_platform,
        "host_environment",
        error_context=f"observed platform {platform_name}",
    )
    source_record = source_by_platform.get(platform_name)
    if source_record is None:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = f"runner-image source record missing for {platform_name}"
        return result, 1

    for fact_path in stream["compared_facts"]:
        observed_value, present = get_nested_value(host_environment, fact_path)
        if not present:
            result["status"] = "manual-review-required"
            result["outcome"] = "source-error"
            result["source_error"] = f"observed fact missing for {fact_path}"
            return result, 1
        source_key = fact_path.split(".")[-1]
        source_value = source_record.get(source_key)
        if not source_value:
            result["status"] = "manual-review-required"
            result["outcome"] = "source-error"
            result["source_error"] = f"runner-image source fact missing for {platform_name}:{source_key}"
            return result, 1
        result["observed"][fact_path] = observed_value
        result["source"][fact_path] = str(source_value)
        if observed_value != str(source_value):
            result["status"] = "manual-review-required"
            result["outcome"] = "source-drift"
            result["changed_facts"].append(
                {
                    "path": fact_path,
                    "observed": observed_value,
                    "source": str(source_value),
                }
            )

    return result, (len(result["changed_facts"]) if result["changed_facts"] else 0)


def build_android_emulator_runtime_group_result(
    group: dict[str, Any],
    observed_platforms: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    result = {
        "status": "no review-needed",
        "outcome": "source-match",
        "observed": {},
        "source": {},
        "findings": [],
        "source_error": "",
    }
    observed_platform = required_object_field(
        observed_platforms,
        "android",
        error_context="observed platforms",
    )
    if "host_environment_error" in observed_platform:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = required_scalar_field(
            observed_platform,
            "host_environment_error",
            error_context="observed platform android",
        )
        return result, 1

    host_environment = required_object_field(
        observed_platform,
        "host_environment",
        error_context="observed platform android",
    )
    emulator = required_object_field(host_environment, "emulator", error_context="observed platform android host_environment")
    observed_api_level = required_scalar_field(emulator, "api_level", error_context="observed android emulator")
    observed_os_version = required_scalar_field(emulator, "os_version", error_context="observed android emulator")
    observed_target = optional_scalar_field(emulator, "target")
    observed_arch = optional_scalar_field(emulator, "arch")
    observed_profile = optional_scalar_field(emulator, "profile")
    result["observed"] = {
        "emulator.api_level": observed_api_level,
        "emulator.os_version": observed_os_version,
        "emulator.target": observed_target,
        "emulator.arch": observed_arch,
    }
    if observed_profile:
        result["observed"]["emulator.profile"] = observed_profile
    if not observed_target or not observed_arch:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = "observed Android emulator support fields target/arch are missing"
        return result, 1

    try:
        platform_catalog, system_image_catalog, version_mapping = fetch_android_emulator_source_catalogs(group)
    except RunnerHostWatchError as exc:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-error"
        result["source_error"] = str(exc)
        return result, 1

    platform_package_path = f"platforms;android-{observed_api_level}"
    system_image_package_path = f"system-images;android-{observed_api_level};{observed_target};{observed_arch}"
    mapped_os_version = version_mapping.get(observed_api_level, "")
    result["source"] = {
        "platform_package_path": platform_package_path,
        "system_image_package_path": system_image_package_path,
        "mapped_os_version": mapped_os_version,
    }
    platform_revision = platform_catalog.get(platform_package_path, {}).get("revision", "")
    if platform_revision:
        result["source"]["platform_revision"] = platform_revision
    system_image_revision = system_image_catalog.get(system_image_package_path, {}).get("revision", "")
    if system_image_revision:
        result["source"]["system_image_revision"] = system_image_revision

    if platform_package_path not in platform_catalog:
        result["findings"].append(
            {
                "code": "platform-package-missing",
                "message": f"Android platform catalog is missing {platform_package_path}",
            }
        )
    if not mapped_os_version or mapped_os_version != observed_os_version:
        result["findings"].append(
            {
                "code": "android-version-mismatch",
                "message": (
                    f"Android version mapping disagrees with observed API level/runtime pair: "
                    f"api_level={observed_api_level} observed_os_version={observed_os_version} mapped_os_version={mapped_os_version or 'missing'}"
                ),
            }
        )
    if system_image_package_path not in system_image_catalog:
        result["findings"].append(
            {
                "code": "system-image-package-missing",
                "message": f"Android system image catalog is missing {system_image_package_path}",
            }
        )

    if result["findings"]:
        result["status"] = "manual-review-required"
        result["outcome"] = "source-review-needed"
        return result, 1
    return result, 0


def enrich_source_rule_groups(
    normalized_source_rules: dict[str, Any],
    observed_platforms: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, str | None]:
    enriched_groups: list[dict[str, Any]] = []
    source_advisory_count = 0
    source_reason: str | None = None

    for group in normalized_source_rules["groups"]:
        if group["rule_kind"] == "runner-image-release-metadata":
            fetch_error = ""
            source_by_platform: dict[str, dict[str, str]] = {}
            try:
                source_by_platform = fetch_runner_image_source_for_group(group, observed_platforms)
            except RunnerHostWatchError as exc:
                fetch_error = str(exc)

            platform_results: list[dict[str, Any]] = []
            group_outcome = "source-match"
            group_status = "no review-needed"
            group_advisory_count = 0
            for platform_name in group["platforms"]:
                platform_result, advisory_count = build_runner_image_platform_result(
                    platform_name,
                    group["source_streams"][platform_name],
                    observed_platforms,
                    source_by_platform,
                    fetch_error=fetch_error,
                )
                platform_results.append(platform_result)
                group_advisory_count += advisory_count
                if platform_result["outcome"] == "source-error":
                    group_outcome = "source-error"
                    group_status = "manual-review-required"
                elif platform_result["outcome"] == "source-drift" and group_outcome != "source-error":
                    group_outcome = "source-drift"
                    group_status = "manual-review-required"

            if group_outcome == "source-error":
                source_reason = "runner-images-source-error"
            elif group_outcome == "source-drift" and source_reason != "runner-images-source-error":
                source_reason = "runner-images-source-drift"

            enriched_groups.append(
                {
                    **group,
                    "status": group_status,
                    "outcome": group_outcome,
                    "platform_results": platform_results,
                }
            )
            source_advisory_count += group_advisory_count
            continue

        if group["rule_kind"] == "java-release-support":
            fetch_error = ""
            supported_releases: list[int] | None = None
            try:
                metadata = required_object_field(group, "source_metadata", error_context="android-java source rule")
                supported_releases = normalize_java_supported_releases(
                    fetch_json_url(
                        required_string_field(
                            metadata,
                            "release_catalog_url",
                            error_context="android-java source rule source_metadata",
                        )
                    )
                )
            except RunnerHostWatchError as exc:
                fetch_error = str(exc)

            platform_results: list[dict[str, Any]] = []
            group_outcome = "source-match"
            group_status = "no review-needed"
            group_advisory_count = 0
            for platform_name in group["platforms"]:
                platform_result, advisory_count = build_java_release_platform_result(
                    platform_name,
                    group,
                    observed_platforms,
                    supported_releases=supported_releases,
                    fetch_error=fetch_error,
                )
                platform_results.append(platform_result)
                group_advisory_count += advisory_count
                if platform_result["outcome"] == "source-error":
                    group_outcome = "source-error"
                    group_status = "manual-review-required"
                elif platform_result["outcome"] != "source-match" and group_outcome != "source-error":
                    group_outcome = "source-review-needed"
                    group_status = "manual-review-required"

            if group_advisory_count > 0 and source_reason is None:
                source_reason = "source-review-needed"

            enriched_groups.append(
                {
                    **group,
                    "status": group_status,
                    "outcome": group_outcome,
                    "platform_results": platform_results,
                }
            )
            source_advisory_count += group_advisory_count
            continue

        if group["rule_kind"] == "android-system-image-catalog":
            emulator_result, group_advisory_count = build_android_emulator_runtime_group_result(group, observed_platforms)
            enriched_groups.append(
                {
                    **group,
                    **emulator_result,
                }
            )
            source_advisory_count += group_advisory_count
            if group_advisory_count > 0 and source_reason is None:
                source_reason = "android-emulator-runtime-source-review-needed"
            continue

        enriched_groups.append(group)

    return enriched_groups, source_advisory_count, source_reason


def build_summary(
    *,
    repo: str,
    baseline: dict[str, Any],
    source_rules: dict[str, Any],
    observed_platforms: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    normalized_baseline = normalize_baseline(baseline)
    normalized_source_rules = normalize_source_rules(source_rules, normalized_baseline=normalized_baseline)
    if not isinstance(observed_platforms, dict):
        raise RunnerHostWatchError("observed platforms payload must be an object")

    platforms_summary: dict[str, Any] = {}
    baseline_advisory_count = 0
    for platform_name in ("android", "ios"):
        observed_platform = normalize_fixture_platform(
            platform_name,
            required_object_field(observed_platforms, platform_name, error_context="observed platforms"),
        )
        platforms_summary[platform_name], platform_count = build_platform_summary(
            platform_name,
            normalized_baseline["platforms"][platform_name],
            observed_platform,
        )
        baseline_advisory_count += platform_count
        observed_platforms[platform_name] = observed_platform

    if baseline_advisory_count == 0:
        baseline_reason = "baseline-match"
    elif any(
        platform["missing_evidence"] or platform["missing_facts"]
        for platform in platforms_summary.values()
    ):
        baseline_reason = "missing-evidence"
    else:
        baseline_reason = "baseline-drift"

    source_rule_groups, source_advisory_count, source_reason = enrich_source_rule_groups(
        normalized_source_rules,
        observed_platforms,
    )
    total_advisory_count = baseline_advisory_count + source_advisory_count
    if baseline_advisory_count > 0:
        reason = baseline_reason
    elif source_reason is not None:
        reason = source_reason
    else:
        reason = baseline_reason

    return {
        "generated_at": generated_at,
        "repo": repo,
        "issue_title": normalized_baseline["issue_title"],
        "scope": normalized_baseline["scope"],
        "alert": total_advisory_count > 0,
        "advisory_count": total_advisory_count,
        "reason": reason,
        "verdict": "manual-review-required" if total_advisory_count > 0 else "no review-needed",
        "platforms": platforms_summary,
        "source_rule_managed_issue_title": normalized_source_rules["managed_issue_title"],
        "source_rule_groups": source_rule_groups,
    }


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(summary: dict[str, Any]) -> str:
    display_names = {"android": "Android", "ios": "iOS"}
    verdict_reason = {
        "baseline-match": "baseline drift/missing-evidence checks are clean for the watched runner-host inventory.",
        "baseline-drift": "watched runner-host facts drifted from the checked-in baseline.",
        "missing-evidence": "required runner-host evidence is missing or unreadable.",
        "runner-images-source-drift": "source-backed runner-images metadata disagrees with the observed watched facts.",
        "runner-images-source-error": "runner-images source-backed evaluation could not be trusted and failed closed.",
        "source-review-needed": "source-backed runner-host evaluation found Java release/support findings that need review.",
        "android-emulator-runtime-source-review-needed": "Android emulator-runtime source-backed evaluation requires review.",
    }.get(summary["reason"], summary["reason"])
    lines = [
        REPORT_MARKER,
        f"# {summary['issue_title']}",
        "",
        f"Verdict: **{summary['verdict']}** — {verdict_reason}",
        f"- Scope: {summary['scope']}",
        f"- Repo: `{summary['repo']}`",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Source-rule status",
        f"- Managed issue path for future actionable findings: `{summary['source_rule_managed_issue_title']}`",
    ]
    for group in summary["source_rule_groups"]:
        watched_fact_list = ", ".join(
            f"{entry['platform']}:{entry['path']}" for entry in group["watched_fact_paths"]
        )
        follow_up_numbers = group.get("follow_up_issues") or [group["follow_up_issue"]]
        follow_up_display = ", ".join(f"#{number}" for number in follow_up_numbers)
        lines.extend(
            [
                f"- `{group['key']}` — `{group['rule_kind']}` via {follow_up_display}",
                f"  - Surface: {group['surface']}",
                f"  - Candidate source: {group['candidate_source']}",
                f"  - Rationale: {group['rationale']}",
                f"  - Watched facts: {watched_fact_list}",
            ]
        )
        if "platform_results" in group:
            lines.extend(
                [
                    f"  - Status: `{group['status']}`",
                    f"  - Outcome: `{group['outcome']}`",
                ]
            )
            for platform_result in group["platform_results"]:
                lines.append(
                    f"  - {display_names[platform_result['platform']]}: `{platform_result['status']}` / `{platform_result['outcome']}`"
                )
                if platform_result["observed"]:
                    observed_text = ", ".join(
                        f"{path}={sanitize_cell(value)}" for path, value in platform_result["observed"].items()
                    )
                    lines.append(f"    - Observed: {observed_text}")
                if platform_result["source"]:
                    source_text = ", ".join(
                        f"{path}={sanitize_cell(value)}" for path, value in platform_result["source"].items()
                    )
                    lines.append(f"    - Source: {source_text}")
                if platform_result.get("changed_facts"):
                    lines.append("    - Changed facts:")
                    for change in platform_result["changed_facts"]:
                        lines.append(
                            f"      - `{change['path']}` observed `{sanitize_cell(change['observed'])}` source `{sanitize_cell(change['source'])}`"
                        )
                if platform_result.get("findings"):
                    lines.append("    - Findings:")
                    for finding in platform_result["findings"]:
                        message = sanitize_cell(finding.get("message", finding.get("code", "finding")))
                        code = sanitize_cell(finding.get("code", "finding"))
                        lines.append(f"      - `{code}`: {message}")
                if platform_result.get("source_error"):
                    lines.append(f"    - Source error: {sanitize_cell(platform_result['source_error'])}")
        elif group["rule_kind"] == "android-system-image-catalog":
            lines.extend(
                [
                    f"  - Status: `{group['status']}`",
                    f"  - Outcome: `{group['outcome']}`",
                ]
            )
            if group["observed"]:
                observed_text = ", ".join(
                    f"{path}={sanitize_cell(value)}" for path, value in group["observed"].items()
                )
                lines.append(f"  - Observed: {observed_text}")
            if group["source"]:
                source_text = ", ".join(
                    f"{path}={sanitize_cell(value)}" for path, value in group["source"].items()
                )
                lines.append(f"  - Source: {source_text}")
            if group["findings"]:
                lines.append("  - Findings:")
                for finding in group["findings"]:
                    lines.append(f"    - `{finding['code']}` {sanitize_cell(finding['message'])}")
            if group["source_error"]:
                lines.append(f"  - Source error: {sanitize_cell(group['source_error'])}")
    lines.append("")
    for platform_name in ("android", "ios"):
        platform = summary["platforms"][platform_name]
        lines.append(f"## {display_names[platform_name]}")
        run_id = sanitize_cell(platform["run_id"])
        if platform["run_url"]:
            lines.append(f"- Run: `{run_id}` ({platform['run_url']})")
        else:
            lines.append(f"- Run: `{run_id}` (no successful main run found)")
        lines.append(f"- Status: `{platform['status']}`")
        if platform["changed_facts"]:
            lines.append("- Drift:")
            for change in platform["changed_facts"]:
                lines.append(
                    f"  - `{change['path']}` expected `{sanitize_cell(change['expected'])}` observed `{sanitize_cell(change['observed'])}`"
                )
        if platform["missing_facts"]:
            lines.append("- Missing facts:")
            for missing in platform["missing_facts"]:
                lines.append(
                    f"  - `{missing['path']}` expected `{sanitize_cell(missing['expected'])}` ({sanitize_cell(missing['reason'])})"
                )
        if platform["missing_evidence"]:
            lines.append("- Missing evidence:")
            for missing in platform["missing_evidence"]:
                lines.append(f"  - {sanitize_cell(missing['reason'])}")
        if not platform["changed_facts"] and not platform["missing_facts"] and not platform["missing_evidence"]:
            lines.append("- Watched facts match the checked-in baseline.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(*, summary: dict[str, Any], summary_out: Path, markdown_out: Path) -> None:
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(summary), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        baseline_path = Path(args.baseline)
        source_rules_path = Path(args.source_rules) if args.source_rules else baseline_path.with_name("runner-host-advisory-sources.json")
        baseline = load_json_file(baseline_path)
        source_rules = load_json_file(source_rules_path)
        generated_at = args.generated_at or utc_now()
        if args.input:
            payload = load_json_file(args.input)
            if not isinstance(payload, dict):
                raise RunnerHostWatchError("fixture input JSON root must be an object")
            repo = required_scalar_field(payload, "repo", error_context="fixture input")
            observed_platforms = required_object_field(payload, "platforms", error_context="fixture input")
        else:
            normalized_baseline = normalize_baseline(baseline)
            if not workflow_matches(normalized_baseline["platforms"]["android"]["workflow"], args.android_workflow):
                raise RunnerHostWatchError("android workflow does not match checked-in baseline")
            if not workflow_matches(normalized_baseline["platforms"]["ios"]["workflow"], args.ios_workflow):
                raise RunnerHostWatchError("iOS workflow does not match checked-in baseline")
            if normalized_baseline["platforms"]["android"]["artifact"] != args.android_artifact:
                raise RunnerHostWatchError("android artifact does not match checked-in baseline")
            if normalized_baseline["platforms"]["ios"]["artifact"] != args.ios_artifact:
                raise RunnerHostWatchError("iOS artifact does not match checked-in baseline")
            repo = args.repo
            observed_platforms = {
                "android": collect_live_platform(
                    repo=repo,
                    workflow=args.android_workflow,
                    artifact=args.android_artifact,
                    branch=normalized_baseline["platforms"]["android"]["branch"],
                    platform_name="android",
                ),
                "ios": collect_live_platform(
                    repo=repo,
                    workflow=args.ios_workflow,
                    artifact=args.ios_artifact,
                    branch=normalized_baseline["platforms"]["ios"]["branch"],
                    platform_name="ios",
                ),
            }

        summary = build_summary(
            repo=repo,
            baseline=baseline,
            source_rules=source_rules,
            observed_platforms=observed_platforms,
            generated_at=generated_at,
        )
        write_outputs(
            summary=summary,
            summary_out=Path(args.summary_out),
            markdown_out=Path(args.markdown_out),
        )
    except (OSError, subprocess.SubprocessError, RunnerHostWatchError) as exc:
        print(f"runner_host_review_report: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
