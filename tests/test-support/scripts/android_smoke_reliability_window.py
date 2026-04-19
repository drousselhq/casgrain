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

ARTIFACT_CONTRACT_BREACH = "artifact-contract-breach"
DEFAULT_TOTAL_THRESHOLD = 10
DEFAULT_SCHEDULE_MAIN_THRESHOLD = 3
DEFAULT_PULL_REQUEST_THRESHOLD = 3
MAX_LIVE_RUN_LIMIT = 1000


class ReliabilityWindowError(Exception):
    """Raised when reliability-window input cannot be parsed safely."""


RunRecord = dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether the Android smoke workflow has reached its reliability window."
    )
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name form")
    parser.add_argument("--workflow", required=True, help="Workflow file name or workflow identifier")
    parser.add_argument("--artifact-name", required=True, help="Workflow artifact name to inspect")
    parser.add_argument("--summary-out", required=True, help="Path to write machine-readable JSON output")
    parser.add_argument("--markdown-out", required=True, help="Path to write markdown summary output")
    parser.add_argument(
        "--input",
        default="",
        help="Optional normalized fixture input JSON; when set, skip live GitHub collection",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum workflow runs to fetch when collecting live GitHub state",
    )
    parser.add_argument(
        "--generated-at",
        default="",
        help="Optional ISO-8601 UTC timestamp override for deterministic output",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def object_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
    required: bool = True,
) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if value is ...:
        if required:
            raise ReliabilityWindowError(f"{error_context} field '{field_name}' must be an object")
        return {}
    if not isinstance(value, dict):
        raise ReliabilityWindowError(f"{error_context} field '{field_name}' must be an object")
    return value


def list_field(container: dict[str, Any], field_name: str, *, error_context: str) -> list[Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, list):
        raise ReliabilityWindowError(f"{error_context} field '{field_name}' must be a list")
    return value


def scalar_field(container: dict[str, Any], field_name: str, *, error_context: str) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, "") or isinstance(value, (dict, list, tuple, set, bool)):
        raise ReliabilityWindowError(
            f"{error_context} field '{field_name}' must be a non-empty scalar value"
        )
    return str(value)


def int_field(container: dict[str, Any], field_name: str, *, error_context: str) -> int:
    value = container.get(field_name, ...)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReliabilityWindowError(f"{error_context} field '{field_name}' must be an integer")
    return value


def normalize_run(run: dict[str, Any], *, error_context: str) -> RunRecord:
    if not isinstance(run, dict):
        raise ReliabilityWindowError(f"{error_context} must be an object")
    normalized: RunRecord = {
        "id": int_field(run, "id", error_context=error_context),
        "url": scalar_field(run, "url", error_context=error_context),
        "event": scalar_field(run, "event", error_context=error_context),
        "head_branch": scalar_field(run, "head_branch", error_context=error_context),
        "status": scalar_field(run, "status", error_context=error_context),
        "conclusion": scalar_field(run, "conclusion", error_context=error_context),
    }
    if "title" in run and run["title"] not in (None, ""):
        normalized["title"] = scalar_field(run, "title", error_context=error_context)
    if "created_at" in run and run["created_at"] not in (None, ""):
        normalized["created_at"] = scalar_field(run, "created_at", error_context=error_context)
    if "updated_at" in run and run["updated_at"] not in (None, ""):
        normalized["updated_at"] = scalar_field(run, "updated_at", error_context=error_context)

    artifact_summary = run.get("artifact_summary")
    if artifact_summary is None:
        normalized["artifact_summary"] = {
            "available": False,
            "error": "artifact summary missing from normalized run",
        }
        return normalized

    if not isinstance(artifact_summary, dict):
        raise ReliabilityWindowError(f"{error_context} field 'artifact_summary' must be an object")

    available = artifact_summary.get("available")
    if not isinstance(available, bool):
        raise ReliabilityWindowError(
            f"{error_context} field 'artifact_summary.available' must be a boolean"
        )

    if available:
        summary_payload = artifact_summary.get("summary")
        if not isinstance(summary_payload, dict):
            raise ReliabilityWindowError(
                f"{error_context} field 'artifact_summary.summary' must be an object when available"
            )
        normalized["artifact_summary"] = {"available": True, "summary": summary_payload}
    else:
        error_text = artifact_summary.get("error", "artifact summary unavailable")
        if not isinstance(error_text, str) or not error_text.strip():
            raise ReliabilityWindowError(
                f"{error_context} field 'artifact_summary.error' must be a non-empty string when unavailable"
            )
        normalized["artifact_summary"] = {"available": False, "error": error_text}
    return normalized


def summarize_artifact_contract(run: RunRecord, *, error_context: str) -> tuple[str | None, str | None]:
    artifact_summary = run["artifact_summary"]
    if not artifact_summary["available"]:
        return None, None
    summary_payload = object_field(
        artifact_summary,
        "summary",
        error_context=f"{error_context}.artifact_summary",
    )
    contract = object_field(summary_payload, "contract", error_context=f"{error_context}.artifact_summary.summary")
    status = scalar_field(contract, "status", error_context=f"{error_context}.artifact_summary.summary.contract")
    if status not in {"passed", "failed"}:
        raise ReliabilityWindowError(
            f"{error_context}.artifact_summary.summary.contract field 'status' must be 'passed' or 'failed'"
        )
    failure_class = contract.get("failure_class")
    if status == "passed":
        if failure_class is not None:
            raise ReliabilityWindowError(
                f"{error_context}.artifact_summary.summary.contract field 'failure_class' must be null when status is 'passed'"
            )
        return status, None
    if not isinstance(failure_class, str) or not failure_class.strip():
        raise ReliabilityWindowError(
            f"{error_context}.artifact_summary.summary.contract field 'failure_class' must be a non-empty string when status is 'failed'"
        )
    return status, failure_class


def build_summary(payload: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReliabilityWindowError("reliability window payload root must be an object")

    repo = scalar_field(payload, "repo", error_context="reliability window payload")
    workflow = scalar_field(payload, "workflow", error_context="reliability window payload")
    artifact_name = scalar_field(payload, "artifact_name", error_context="reliability window payload")
    raw_runs = list_field(payload, "runs", error_context="reliability window payload")
    runs = [normalize_run(run, error_context=f"reliability window run[{index}]") for index, run in enumerate(raw_runs)]

    ignored_non_completed_run_ids: list[int] = []
    evaluation_index = 0
    while evaluation_index < len(runs) and runs[evaluation_index]["status"] != "completed":
        ignored_non_completed_run_ids.append(runs[evaluation_index]["id"])
        evaluation_index += 1

    streak_runs: list[RunRecord] = []
    blocker_run: RunRecord | None = None
    for run in runs[evaluation_index:]:
        if run["status"] == "completed" and run["conclusion"] == "success":
            streak_runs.append(run)
            continue
        blocker_run = run
        break

    schedule_main_success_count = sum(
        1 for run in streak_runs if run["event"] == "schedule" and run["head_branch"] == "main"
    )
    pull_request_success_count = sum(1 for run in streak_runs if run["event"] == "pull_request")

    missing_summary_run_ids: list[int] = []
    non_passing_summary_run_ids: list[int] = []
    streak_run_summaries: list[dict[str, Any]] = []
    for index, run in enumerate(streak_runs):
        artifact_summary = run["artifact_summary"]
        if not artifact_summary["available"]:
            missing_summary_run_ids.append(run["id"])
            summary_status = None
            failure_class = None
        else:
            try:
                summary_status, failure_class = summarize_artifact_contract(
                    run, error_context=f"reliability window streak[{index}]"
                )
            except ReliabilityWindowError:
                missing_summary_run_ids.append(run["id"])
                summary_status = None
                failure_class = ARTIFACT_CONTRACT_BREACH
            else:
                if summary_status != "passed":
                    non_passing_summary_run_ids.append(run["id"])
        streak_run_summaries.append(
            {
                "run_id": run["id"],
                "url": run["url"],
                "event": run["event"],
                "head_branch": run["head_branch"],
                "summary_available": artifact_summary["available"],
                "summary_status": summary_status if artifact_summary["available"] else None,
                "failure_class": failure_class if artifact_summary["available"] else None,
            }
        )

    reasons: list[str] = []
    if len(streak_runs) < DEFAULT_TOTAL_THRESHOLD:
        reasons.append("total_runs_below_threshold")
    if schedule_main_success_count < DEFAULT_SCHEDULE_MAIN_THRESHOLD:
        reasons.append("schedule_main_runs_below_threshold")
    if pull_request_success_count < DEFAULT_PULL_REQUEST_THRESHOLD:
        reasons.append("pull_request_runs_below_threshold")
    if missing_summary_run_ids:
        reasons.append("streak_summary_missing")
    if non_passing_summary_run_ids:
        reasons.append("streak_summary_not_passed")

    blocker: dict[str, Any] | None = None
    if blocker_run is not None:
        blocker_artifact_summary = blocker_run["artifact_summary"]
        blocker_failure_class: str | None = None
        blocker_summary_status: str | None = None
        blocker_summary_error: str | None = blocker_artifact_summary.get("error")
        blocker_summary_problem: str | None = None
        if blocker_artifact_summary["available"]:
            try:
                blocker_summary_status, blocker_failure_class = summarize_artifact_contract(
                    blocker_run,
                    error_context="reliability window blocker",
                )
            except ReliabilityWindowError as exc:
                blocker_failure_class = ARTIFACT_CONTRACT_BREACH
                blocker_summary_error = str(exc)
                blocker_summary_problem = "blocker_summary_missing"
            else:
                if blocker_run["conclusion"] != "success" and blocker_summary_status == "passed":
                    blocker_failure_class = ARTIFACT_CONTRACT_BREACH
                    blocker_summary_problem = "blocker_summary_inconsistent"
                    blocker_summary_error = (
                        "failed workflow run reported a passing artifact contract; treating blocker as artifact-contract-breach"
                    )
        else:
            blocker_failure_class = ARTIFACT_CONTRACT_BREACH
            blocker_summary_problem = "blocker_summary_missing"
        blocker = {
            "run_id": blocker_run["id"],
            "url": blocker_run["url"],
            "event": blocker_run["event"],
            "head_branch": blocker_run["head_branch"],
            "status": blocker_run["status"],
            "conclusion": blocker_run["conclusion"],
            "summary_available": blocker_artifact_summary["available"],
            "summary_status": blocker_summary_status,
            "failure_class": blocker_failure_class,
            "summary_error": blocker_summary_error,
            "summary_problem": blocker_summary_problem,
        }

    summary = {
        "repo": repo,
        "workflow": workflow,
        "artifact_name": artifact_name,
        "generated_at": generated_at,
        "thresholds": {
            "successful_run_count": DEFAULT_TOTAL_THRESHOLD,
            "schedule_main_success_count": DEFAULT_SCHEDULE_MAIN_THRESHOLD,
            "pull_request_success_count": DEFAULT_PULL_REQUEST_THRESHOLD,
        },
        "verdict": "qualified" if not reasons else "not_qualified",
        "reasons": reasons,
        "streak": {
            "successful_run_count": len(streak_runs),
            "schedule_main_success_count": schedule_main_success_count,
            "pull_request_success_count": pull_request_success_count,
            "run_ids": [run["id"] for run in streak_runs],
            "runs": streak_run_summaries,
            "missing_summary_run_ids": missing_summary_run_ids,
            "non_passing_summary_run_ids": non_passing_summary_run_ids,
            "ignored_non_completed_run_ids": ignored_non_completed_run_ids,
        },
        "blocker": blocker,
    }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    verdict_text = "QUALIFIED" if summary["verdict"] == "qualified" else "NOT QUALIFIED"
    streak = summary["streak"]
    thresholds = summary["thresholds"]
    lines = [
        f"# Android smoke reliability window: {verdict_text}",
        "",
        (
            "- Threshold: "
            f"`>={thresholds['successful_run_count']}` successful runs including "
            f"`>={thresholds['schedule_main_success_count']}` `schedule` runs on `main` and "
            f"`>={thresholds['pull_request_success_count']}` `pull_request` runs"
        ),
        (
            "- Current streak: "
            f"`total={streak['successful_run_count']}`, "
            f"`schedule on main={streak['schedule_main_success_count']}`, "
            f"`pull_request={streak['pull_request_success_count']}`"
        ),
        "- Evaluated streak run IDs: " + (", ".join(str(run_id) for run_id in streak["run_ids"]) or "none"),
    ]

    if summary["reasons"]:
        lines.append("- Reason codes: `" + "`, `".join(summary["reasons"]) + "`")

    blocker = summary.get("blocker")
    if blocker and summary["verdict"] != "qualified":
        blocker_line = (
            f"- Blocker run: `{blocker['run_id']}` "
            f"(`conclusion={blocker['conclusion']}`, `failure_class={blocker['failure_class'] or 'unknown'}`)"
        )
        lines.append(blocker_line)
        if blocker.get("summary_error"):
            lines.append(f"- Blocker summary issue: `{blocker['summary_error']}`")

    return "\n".join(lines) + "\n"


def write_outputs(*, summary: dict[str, Any], summary_out: Path, markdown_out: Path) -> None:
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(summary), encoding="utf-8")


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReliabilityWindowError(f"input JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReliabilityWindowError(f"input JSON is not valid JSON: {path}") from exc


def run_gh_json(arguments: list[str]) -> Any:
    completed = subprocess.run(
        ["gh", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
        raise ReliabilityWindowError(stderr)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReliabilityWindowError("gh command did not return valid JSON") from exc


def normalize_live_run(raw_run: dict[str, Any]) -> RunRecord:
    if not isinstance(raw_run, dict):
        raise ReliabilityWindowError("gh run list returned a non-object run entry")
    status = scalar_field(raw_run, "status", error_context="gh run list result")
    raw_conclusion = raw_run.get("conclusion", ...)
    if raw_conclusion in (None, ""):
        conclusion = "pending" if status != "completed" else "unknown"
    elif isinstance(raw_conclusion, (dict, list, tuple, set, bool)):
        raise ReliabilityWindowError("gh run list result field 'conclusion' must be a scalar value")
    else:
        conclusion = str(raw_conclusion)
    return {
        "id": int_field(raw_run, "databaseId", error_context="gh run list result"),
        "url": scalar_field(raw_run, "url", error_context="gh run list result"),
        "event": scalar_field(raw_run, "event", error_context="gh run list result"),
        "head_branch": scalar_field(raw_run, "headBranch", error_context="gh run list result"),
        "status": status,
        "conclusion": conclusion,
        "title": scalar_field(raw_run, "displayTitle", error_context="gh run list result"),
        "created_at": scalar_field(raw_run, "createdAt", error_context="gh run list result"),
        "updated_at": scalar_field(raw_run, "updatedAt", error_context="gh run list result"),
    }


def completed_history_has_blocker(runs: list[dict[str, Any]]) -> bool:
    evaluation_index = 0
    while evaluation_index < len(runs) and runs[evaluation_index].get("status") != "completed":
        evaluation_index += 1
    return any(
        run.get("status") == "completed" and run.get("conclusion") != "success"
        for run in runs[evaluation_index:]
    )


def load_artifact_summary_file(summary_path: Path) -> dict[str, Any]:
    try:
        summary_text = summary_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return {"available": False, "error": f"evidence-summary.json is not valid UTF-8: {exc}"}
    except OSError as exc:
        return {"available": False, "error": f"unable to read evidence-summary.json: {exc}"}

    try:
        summary_payload = json.loads(summary_text)
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "error": f"evidence-summary.json is not valid JSON: {exc}",
        }
    if not isinstance(summary_payload, dict):
        return {
            "available": False,
            "error": "evidence-summary.json root must be an object",
        }
    return {"available": True, "summary": summary_payload}


def list_live_runs(*, repo: str, workflow: str, limit: int) -> list[RunRecord]:
    current_limit = max(1, limit)
    while True:
        raw_runs = run_gh_json(
            [
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                workflow,
                "--limit",
                str(current_limit),
                "--json",
                "databaseId,displayTitle,status,conclusion,event,headBranch,url,createdAt,updatedAt",
            ]
        )
        if not isinstance(raw_runs, list):
            raise ReliabilityWindowError("gh run list did not return a JSON list")
        normalized_runs = [normalize_live_run(raw_run) for raw_run in raw_runs]
        if len(normalized_runs) < current_limit:
            return normalized_runs
        if completed_history_has_blocker(normalized_runs):
            return normalized_runs
        if current_limit >= MAX_LIVE_RUN_LIMIT:
            return normalized_runs
        next_limit = min(MAX_LIVE_RUN_LIMIT, current_limit + max(1, limit))
        if next_limit == current_limit:
            return normalized_runs
        current_limit = next_limit


def collect_artifact_summary(*, repo: str, run_id: int, artifact_name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"android-smoke-{run_id}-") as tmp_dir:
        completed = subprocess.run(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "--repo",
                repo,
                "--name",
                artifact_name,
                "--dir",
                tmp_dir,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            error_text = completed.stderr.strip() or completed.stdout.strip() or "gh run download failed"
            return {"available": False, "error": error_text}

        summary_path = next(Path(tmp_dir).rglob("evidence-summary.json"), None)
        if summary_path is None:
            return {
                "available": False,
                "error": "evidence-summary.json missing from downloaded artifact",
            }
        return load_artifact_summary_file(summary_path)


def collect_live_payload(*, repo: str, workflow: str, artifact_name: str, limit: int) -> dict[str, Any]:
    runs = list_live_runs(repo=repo, workflow=workflow, limit=limit)

    needed_run_indices: list[int] = []
    started_completed_history = False
    for index, run in enumerate(runs):
        if run["status"] != "completed" and not started_completed_history:
            continue
        started_completed_history = True
        needed_run_indices.append(index)
        if run["status"] == "completed" and run["conclusion"] == "success":
            continue
        break

    for index in needed_run_indices:
        runs[index]["artifact_summary"] = collect_artifact_summary(
            repo=repo,
            run_id=runs[index]["id"],
            artifact_name=artifact_name,
        )

    return {
        "repo": repo,
        "workflow": workflow,
        "artifact_name": artifact_name,
        "runs": runs,
    }


def main() -> int:
    args = parse_args()
    generated_at = args.generated_at or utc_now()

    try:
        if args.input:
            payload = load_json_file(Path(args.input))
        else:
            payload = collect_live_payload(
                repo=args.repo,
                workflow=args.workflow,
                artifact_name=args.artifact_name,
                limit=args.limit,
            )
        summary = build_summary(payload, generated_at=generated_at)
        write_outputs(
            summary=summary,
            summary_out=Path(args.summary_out),
            markdown_out=Path(args.markdown_out),
        )
    except ReliabilityWindowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
