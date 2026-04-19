#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_MARKER = "<!-- cve-watch-report -->"
MAX_RUN_LIMIT = 50


class RunnerHostWatchError(Exception):
    """Raised when runner-host watch inputs cannot be parsed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a runner-image / host-toolchain drift report from mobile smoke artifacts."
    )
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name form")
    parser.add_argument("--baseline", required=True, help="Path to .github/runner-host-watch.json")
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


def validate_host_environment_contract(host_environment: dict[str, Any], *, error_context: str) -> dict[str, Any]:
    required_scalar_field(host_environment, "generated_at", error_context=error_context)
    workflow_run = required_object_field(host_environment, "workflow_run", error_context=error_context)
    for field_name in ("repository", "workflow", "run_id", "run_attempt", "run_url"):
        required_scalar_field(workflow_run, field_name, error_context=f"{error_context} workflow_run")
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


def read_host_environment_from_downloaded_artifact(run_id: int, repo: str, artifact_name: str) -> dict[str, Any]:
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
        return validate_host_environment_contract(payload, error_context="host-environment.json")


def collect_live_platform(repo: str, workflow: str, artifact: str, branch: str) -> dict[str, Any]:
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
        host_environment = read_host_environment_from_downloaded_artifact(run["id"], repo, artifact)
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


def build_summary(
    *,
    repo: str,
    baseline: dict[str, Any],
    observed_platforms: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    normalized_baseline = normalize_baseline(baseline)
    if not isinstance(observed_platforms, dict):
        raise RunnerHostWatchError("observed platforms payload must be an object")

    platforms_summary: dict[str, Any] = {}
    advisory_count = 0
    for platform_name in ("android", "ios"):
        observed_platform = normalize_fixture_platform(
            platform_name,
            required_object_field(observed_platforms, platform_name, error_context="observed platforms"),
        )
        platform_summary, platform_count = build_platform_summary(
            platform_name,
            normalized_baseline["platforms"][platform_name],
            observed_platform,
        )
        platforms_summary[platform_name] = platform_summary
        advisory_count += platform_count

    return {
        "generated_at": generated_at,
        "repo": repo,
        "issue_title": normalized_baseline["issue_title"],
        "scope": normalized_baseline["scope"],
        "alert": advisory_count > 0,
        "advisory_count": advisory_count,
        "verdict": "manual-review-required" if advisory_count > 0 else "no review-needed",
        "platforms": platforms_summary,
    }


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(summary: dict[str, Any]) -> str:
    display_names = {"android": "Android", "ios": "iOS"}
    lines = [
        REPORT_MARKER,
        f"# {summary['issue_title']}",
        "",
        f"Verdict: **{summary['verdict']}** — drift-triggered manual review only; this slice does not perform direct advisory evaluation.",
        f"- Scope: {summary['scope']}",
        f"- Repo: `{summary['repo']}`",
        f"- Generated at: `{summary['generated_at']}`",
        "",
    ]
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
        baseline = load_json_file(args.baseline)
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
                ),
                "ios": collect_live_platform(
                    repo=repo,
                    workflow=args.ios_workflow,
                    artifact=args.ios_artifact,
                    branch=normalized_baseline["platforms"]["ios"]["branch"],
                ),
            }

        summary = build_summary(
            repo=repo,
            baseline=baseline,
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
