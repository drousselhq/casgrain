#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUCCESS_REQUIRED = (
    "trace.json",
    "plan.json",
    "emulator.json",
    "host-environment.json",
    "ui-before-tap.xml",
    "ui-after-tap.xml",
    "android-tap-counter-1.png",
)
FAILURE_OPTIONAL = (
    "foreground-window.txt",
    "foreground-activity.txt",
    "ui-last.xml",
)
SUMMARY_NAME = "evidence-summary.json"
ARTIFACT_CONTRACT_BREACH = "artifact-contract-breach"
BOOT_READINESS_FAILURE = "boot-readiness-failure"
APP_FOREGROUND_FAILURE = "app-foreground-failure"
SELECTOR_TIMEOUT = "selector-timeout"
TEXT_TIMEOUT = "text-timeout"
UI_DUMP_FAILURE = "ui-dump-failure"
RUNNER_FAILURE_CLASSES = {
    BOOT_READINESS_FAILURE,
    APP_FOREGROUND_FAILURE,
    SELECTOR_TIMEOUT,
    TEXT_TIMEOUT,
    UI_DUMP_FAILURE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Android smoke artifact contract and emit a machine-readable summary."
    )
    parser.add_argument("--artifact-dir", required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256_for(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise SystemExit(f"missing {label} at {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {label} at {path}: {error}") from error


def build_artifact_summary(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_for(path),
    }


def summarize_directory(artifact_dir: Path) -> list[dict[str, Any]]:
    return [
        build_artifact_summary(path)
        for path in sorted(path for path in artifact_dir.iterdir() if path.is_file() and path.name != SUMMARY_NAME)
    ]


def validate_success_contract(artifact_dir: Path) -> dict[str, Any]:
    for name in SUCCESS_REQUIRED:
        expect((artifact_dir / name).is_file(), f"success artifact contract missing {name}")

    trace = load_json(artifact_dir / "trace.json", "trace")
    expect(trace.get("status") == "passed", "trace.json must report a passed Android smoke run")

    artifacts = trace.get("artifacts")
    expect(isinstance(artifacts, list) and artifacts, "trace.json must expose artifact metadata")

    artifact_ids = {entry.get("artifact_id") for entry in artifacts if isinstance(entry, dict)}
    expected_ids = {
        "android-tap-counter-1",
        "android-smoke-emulator",
        "android-host-environment",
        "android-ui-before-tap",
        "android-ui-after-tap",
    }
    missing_ids = sorted(expected_ids - artifact_ids)
    expect(not missing_ids, f"trace.json is missing expected artifact ids: {', '.join(missing_ids)}")

    host_environment = load_json(artifact_dir / "host-environment.json", "host environment")
    for group_name, required_fields in {
        "runner": ("label", "image_name", "image_version", "os_version"),
        "java": ("configured_major", "resolved_version"),
        "gradle": ("configured_version", "resolved_version"),
        "emulator": ("api_level", "device_name", "os_version"),
    }.items():
        group = host_environment.get(group_name)
        expect(isinstance(group, dict), f"host-environment.json must include object {group_name!r}")
        for field_name in required_fields:
            value = group.get(field_name)
            expect(
                isinstance(value, (str, int, float)) and str(value).strip(),
                f"host-environment.json must include non-empty {group_name}.{field_name}",
            )

    return {
        "status": "passed",
        "failure_class": None,
        "trace_run_id": trace.get("run_id"),
        "trace_plan_id": trace.get("plan_id"),
        "artifact_ids": sorted(artifact_ids),
        "diagnostics": trace.get("diagnostics", []),
        "host_environment": host_environment,
    }


def validate_failure_contract(artifact_dir: Path) -> dict[str, Any]:
    failure = load_json(artifact_dir / "failure.json", "failure diagnostics")
    reason = failure.get("reason")
    expect(isinstance(reason, str) and reason.strip(), "failure.json must include a non-empty reason")
    failure_class = failure.get("failure_class")
    expect(
        isinstance(failure_class, str) and failure_class.strip(),
        "failure.json must include a non-empty failure_class",
    )
    expect(
        failure_class in RUNNER_FAILURE_CLASSES,
        f"unknown failure_class {failure_class!r}; expected one of {sorted(RUNNER_FAILURE_CLASSES)}",
    )

    referenced = failure.get("artifacts")
    expect(isinstance(referenced, dict), "failure.json must include an artifacts object")
    requires_preserved_diagnostics = failure_class != BOOT_READINESS_FAILURE

    validated_refs: dict[str, str | None] = {}
    for key in ("foreground_window", "foreground_activity", "last_ui_dump"):
        value = referenced.get(key)
        expect(value is None or isinstance(value, str), f"failure.json artifacts.{key} must be a string or null")
        if value is not None:
            expect((artifact_dir / value).is_file(), f"failure.json references missing artifact {value}")
        validated_refs[key] = value

    if requires_preserved_diagnostics:
        expect(
            any(value is not None for value in validated_refs.values()),
            "failure.json must reference at least one preserved diagnostic artifact",
        )
    if failure_class == UI_DUMP_FAILURE:
        expect(
            validated_refs["last_ui_dump"] is not None,
            "ui-dump-failure must reference last_ui_dump so the captured UI dump remains reviewable",
        )

    expect(not (artifact_dir / "trace.json").exists(), "failure artifact sets must not also contain trace.json")

    optional_present = [name for name in FAILURE_OPTIONAL if (artifact_dir / name).is_file()]
    if requires_preserved_diagnostics:
        expect(optional_present, "failure artifact contract must preserve at least one concrete diagnostic artifact")

    return {
        "status": "failed",
        "reason": reason,
        "failure_class": failure_class,
        "referenced_artifacts": validated_refs,
        "present_diagnostics": optional_present,
    }


def resolve_contract(artifact_dir: Path) -> dict[str, Any]:
    has_trace = (artifact_dir / "trace.json").is_file()
    has_failure = (artifact_dir / "failure.json").is_file()
    expect(has_trace or has_failure, "artifact directory must contain either trace.json or failure.json")
    expect(not (has_trace and has_failure), "artifact directory must not contain both trace.json and failure.json")
    return validate_success_contract(artifact_dir) if has_trace else validate_failure_contract(artifact_dir)


def contract_breach(reason: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "failure_class": ARTIFACT_CONTRACT_BREACH,
        "reason": reason,
    }


def resolve_summary_dir(artifact_dir: Path) -> tuple[Path, str | None]:
    if artifact_dir.exists() and not artifact_dir.is_dir():
        return artifact_dir.parent / f"{artifact_dir.name}-artifacts", str(artifact_dir)
    return artifact_dir, None


def main() -> int:
    args = parse_args()
    requested_artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir, requested_file_path = resolve_summary_dir(requested_artifact_dir)

    exit_code = 0
    try:
        expect(requested_artifact_dir.is_dir(), f"artifact directory does not exist: {requested_artifact_dir}")
        contract = resolve_contract(requested_artifact_dir)
    except SystemExit as error:
        exit_code = 1
        contract = contract_breach(str(error))
        artifact_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": utc_now(),
        "artifact_dir": str(artifact_dir),
        "contract": contract,
        "files": summarize_directory(artifact_dir),
    }
    if requested_file_path is not None:
        summary["requested_artifact_dir"] = requested_file_path

    summary_path = artifact_dir / SUMMARY_NAME
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "summary": str(summary_path),
                "status": contract["status"],
                "failure_class": contract.get("failure_class"),
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
