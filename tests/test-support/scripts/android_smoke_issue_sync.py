#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TRACKER_MARKER = "<!-- android-smoke-reliability-tracker -->"
BLOCKER_MARKER_PREFIX = "<!-- android-smoke-reliability-blocker:"
MANAGED_BLOCKER_LABELS = ["enhancement", "devops"]
SCHEDULE_SHORTFALL_REASON = "schedule_main_runs_below_threshold"
THRESHOLD_SHORTFALL_REASONS = {
    "total_runs_below_threshold",
    SCHEDULE_SHORTFALL_REASON,
    "pull_request_runs_below_threshold",
}
TRACKER_SCRIPT_PATH = "tests/test-support/scripts/android_smoke_issue_sync.py"


class IssueSyncError(Exception):
    """Raised when Android smoke reliability issue synchronization cannot proceed safely."""


class IssueClientProtocol:
    def create_issue(self, *, repo: str, title: str, body: str, labels: list[str]) -> int:  # pragma: no cover - protocol only
        raise NotImplementedError

    def edit_issue(
        self,
        *,
        repo: str,
        number: int,
        body: str,
        add_labels: list[str] | None = None,
    ) -> None:  # pragma: no cover - protocol only
        raise NotImplementedError

    def reopen_issue(self, *, repo: str, number: int) -> None:  # pragma: no cover - protocol only
        raise NotImplementedError

    def close_issue(self, *, repo: str, number: int, reason: str) -> None:  # pragma: no cover - protocol only
        raise NotImplementedError


class GhIssueClient(IssueClientProtocol):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
            raise IssueSyncError(stderr)
        return completed

    def _write_temp_body(self, body: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        try:
            handle.write(body)
            handle.flush()
            return handle.name
        finally:
            handle.close()

    def create_issue(self, *, repo: str, title: str, body: str, labels: list[str]) -> int:
        body_path = self._write_temp_body(body)
        try:
            completed = self._run(
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body-file",
                body_path,
                "--label",
                ",".join(labels),
            )
        finally:
            Path(body_path).unlink(missing_ok=True)
        return parse_issue_number_from_output(completed.stdout)

    def edit_issue(
        self,
        *,
        repo: str,
        number: int,
        body: str,
        add_labels: list[str] | None = None,
    ) -> None:
        body_path = self._write_temp_body(body)
        try:
            command = [
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--body-file",
                body_path,
            ]
            if add_labels:
                command.extend(["--add-label", ",".join(add_labels)])
            self._run(*command)
        finally:
            Path(body_path).unlink(missing_ok=True)

    def reopen_issue(self, *, repo: str, number: int) -> None:
        self._run("issue", "reopen", str(number), "--repo", repo)

    def close_issue(self, *, repo: str, number: int, reason: str) -> None:
        self._run("issue", "close", str(number), "--repo", repo, "--reason", reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize Android smoke reliability tracker and blocker issues from the reporter summary."
    )
    parser.add_argument("--repo", required=True, help="owner/repo for gh issue operations")
    parser.add_argument("--tracker-issue", type=int, required=True, help="Tracker issue number to synchronize")
    parser.add_argument("--summary-json", required=True, help="Path to reporter summary JSON")
    parser.add_argument("--markdown-file", required=True, help="Path to reporter markdown output")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned action without mutating GitHub")
    return parser.parse_args()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def blocker_marker(failure_class: str) -> str:
    return f"{BLOCKER_MARKER_PREFIX}{failure_class} -->"


def parse_issue_number_from_output(output: str) -> int:
    match = re.search(r"/issues/(\d+)", output)
    if match is None:
        raise IssueSyncError("gh issue create did not return an issue URL")
    return int(match.group(1))


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    number = issue.get("number")
    title = issue.get("title")
    body = issue.get("body") or ""
    state = str(issue.get("state", "")).upper()
    if not isinstance(number, int) or number <= 0:
        raise IssueSyncError("GitHub issue search result is missing a valid numeric issue number")
    if not isinstance(title, str) or not title.strip():
        raise IssueSyncError(f"GitHub issue #{number} is missing a valid title")
    if state not in {"OPEN", "CLOSED"}:
        raise IssueSyncError(f"GitHub issue #{number} has unsupported state '{state}'")
    return {"number": number, "title": title, "body": body, "state": state}


def select_managed_issue(
    issues: list[dict[str, Any]], *, expected_title: str, marker: str
) -> dict[str, Any] | None:
    normalized = [normalize_issue(issue) for issue in issues if issue.get("title") == expected_title]
    marker_matches = [issue for issue in normalized if marker in issue.get("body", "")]
    if not marker_matches:
        return None
    marker_matches.sort(key=lambda issue: (issue["state"] != "OPEN", issue["number"]))
    return marker_matches[0]


def find_issue_by_number(issues: list[dict[str, Any]], *, issue_number: int) -> dict[str, Any]:
    for issue in issues:
        normalized = normalize_issue(issue)
        if normalized["number"] == issue_number:
            return normalized
    raise IssueSyncError(f"GitHub issue #{issue_number} was not found in repository search results")


def scalar_field(container: dict[str, Any], field_name: str, *, error_context: str) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, "") or isinstance(value, (dict, list, tuple, set, bool)):
        raise IssueSyncError(f"{error_context} field '{field_name}' must be a non-empty scalar value")
    return str(value)


def int_field(container: dict[str, Any], field_name: str, *, error_context: str) -> int:
    value = container.get(field_name, ...)
    if isinstance(value, bool) or not isinstance(value, int):
        raise IssueSyncError(f"{error_context} field '{field_name}' must be an integer")
    return value


def list_field(container: dict[str, Any], field_name: str, *, error_context: str) -> list[Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, list):
        raise IssueSyncError(f"{error_context} field '{field_name}' must be a list")
    return value


def object_field(container: dict[str, Any], field_name: str, *, error_context: str) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, dict):
        raise IssueSyncError(f"{error_context} field '{field_name}' must be an object")
    return value


def normalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise IssueSyncError("Android smoke reliability summary JSON root must be an object")
    verdict = scalar_field(summary, "verdict", error_context="summary")
    if verdict not in {"qualified", "not_qualified"}:
        raise IssueSyncError("summary field 'verdict' must be 'qualified' or 'not_qualified'")
    reasons = list_field(summary, "reasons", error_context="summary")
    if not all(isinstance(reason, str) and reason.strip() for reason in reasons):
        raise IssueSyncError("summary field 'reasons' must contain only non-empty strings")
    streak = object_field(summary, "streak", error_context="summary")
    thresholds = object_field(summary, "thresholds", error_context="summary")
    normalized = {
        "repo": scalar_field(summary, "repo", error_context="summary"),
        "workflow": scalar_field(summary, "workflow", error_context="summary"),
        "artifact_name": scalar_field(summary, "artifact_name", error_context="summary"),
        "generated_at": scalar_field(summary, "generated_at", error_context="summary"),
        "verdict": verdict,
        "reasons": reasons,
        "thresholds": {
            "successful_run_count": int_field(thresholds, "successful_run_count", error_context="summary.thresholds"),
            "schedule_main_success_count": int_field(
                thresholds,
                "schedule_main_success_count",
                error_context="summary.thresholds",
            ),
            "pull_request_success_count": int_field(
                thresholds,
                "pull_request_success_count",
                error_context="summary.thresholds",
            ),
        },
        "streak": {
            "successful_run_count": int_field(streak, "successful_run_count", error_context="summary.streak"),
            "schedule_main_success_count": int_field(
                streak,
                "schedule_main_success_count",
                error_context="summary.streak",
            ),
            "pull_request_success_count": int_field(
                streak,
                "pull_request_success_count",
                error_context="summary.streak",
            ),
            "run_ids": [
                int(run_id) if not isinstance(run_id, bool) else (_ for _ in ()).throw(IssueSyncError("summary.streak field 'run_ids' must contain integers"))
                for run_id in list_field(streak, "run_ids", error_context="summary.streak")
            ],
        },
        "blocker": None,
    }
    blocker = summary.get("blocker")
    if blocker is not None:
        blocker_obj = object_field(summary, "blocker", error_context="summary")
        normalized["blocker"] = {
            "run_id": int_field(blocker_obj, "run_id", error_context="summary.blocker"),
            "url": scalar_field(blocker_obj, "url", error_context="summary.blocker"),
            "failure_class": scalar_field(blocker_obj, "failure_class", error_context="summary.blocker"),
            "conclusion": scalar_field(blocker_obj, "conclusion", error_context="summary.blocker"),
        }
    return normalized


def is_threshold_shortfall_only(summary: dict[str, Any]) -> bool:
    reasons = summary["reasons"]
    return bool(reasons) and set(reasons).issubset(THRESHOLD_SHORTFALL_REASONS)


def is_schedule_shortfall_only(summary: dict[str, Any]) -> bool:
    reasons = summary["reasons"]
    return bool(reasons) and set(reasons) == {SCHEDULE_SHORTFALL_REASON}


def needs_managed_blocker(summary: dict[str, Any]) -> bool:
    if summary["verdict"] != "not_qualified":
        return False
    if is_threshold_shortfall_only(summary):
        return False
    blocker = summary.get("blocker")
    return isinstance(blocker, dict)


def build_blocker_title(summary: dict[str, Any]) -> str:
    blocker = summary["blocker"]
    return f"android-smoke: unblock reliability window after {blocker['failure_class']}"


def build_sync_plan(
    *,
    summary: dict[str, Any],
    markdown: str,
    tracker_issue: dict[str, Any],
    existing_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_summary = normalize_summary(summary)
    normalized_tracker = normalize_issue(tracker_issue)
    if not isinstance(markdown, str) or not markdown.strip():
        raise IssueSyncError("Reporter markdown must be a non-empty string")

    report_kind = "tracking_only"
    blocker_plan: dict[str, Any] = {"action": "noop"}
    if normalized_summary["verdict"] == "qualified":
        report_kind = "qualified"
    elif is_threshold_shortfall_only(normalized_summary):
        report_kind = "schedule_shortfall_only" if is_schedule_shortfall_only(normalized_summary) else "tracking_only"
    elif needs_managed_blocker(normalized_summary):
        report_kind = "managed_blocker"
        title = build_blocker_title(normalized_summary)
        marker = blocker_marker(normalized_summary["blocker"]["failure_class"])
        existing = select_managed_issue(existing_issues, expected_title=title, marker=marker)
        if existing is None:
            blocker_plan = {
                "action": "create",
                "title": title,
                "labels": MANAGED_BLOCKER_LABELS,
                "marker": marker,
                "failure_class": normalized_summary["blocker"]["failure_class"],
            }
        elif existing["state"] == "OPEN":
            blocker_plan = {
                "action": "update",
                "number": existing["number"],
                "title": title,
                "labels": MANAGED_BLOCKER_LABELS,
                "marker": marker,
                "failure_class": normalized_summary["blocker"]["failure_class"],
            }
        else:
            blocker_plan = {
                "action": "reopen",
                "number": existing["number"],
                "title": title,
                "labels": MANAGED_BLOCKER_LABELS,
                "marker": marker,
                "failure_class": normalized_summary["blocker"]["failure_class"],
            }

    desired_state = "CLOSED" if normalized_summary["verdict"] == "qualified" else "OPEN"
    return {
        "report_kind": report_kind,
        "summary": normalized_summary,
        "markdown": markdown.strip() + "\n",
        "tracker": {
            "issue": normalized_tracker["number"],
            "title": normalized_tracker["title"],
            "current_state": normalized_tracker["state"],
            "desired_state": desired_state,
        },
        "blocker": blocker_plan,
    }


def render_tracker_body(plan: dict[str, Any], blocker_issue_number: int | None) -> str:
    summary = plan["summary"]
    tracker = plan["tracker"]
    streak = summary["streak"]
    lines = [
        TRACKER_MARKER,
        "# Android smoke qualification tracker",
        "",
        f"This issue is automation-managed by `{TRACKER_SCRIPT_PATH}`.",
        "",
        f"- Tracker issue: `#{tracker['issue']}`",
        f"- Repo: `{summary['repo']}`",
        f"- Workflow: `{summary['workflow']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Verdict: `{summary['verdict']}`",
    ]
    if summary["reasons"]:
        lines.append("- Reasons: `" + "`, `".join(summary["reasons"]) + "`")
    else:
        lines.append("- Reasons: none")
    lines.extend(
        [
            "",
            "## Current streak counts",
            f"- `successful_run_count`, `{streak['successful_run_count']}`",
            f"- `schedule_main_success_count`, `{streak['schedule_main_success_count']}`",
            f"- `pull_request_success_count`, `{streak['pull_request_success_count']}`",
            "- `run_ids`, `" + ", ".join(str(run_id) for run_id in streak["run_ids"]) + "`",
            "",
        ]
    )
    if plan["report_kind"] == "qualified":
        lines.extend(
            [
                "## Qualification status",
                "- Qualified window recorded. Closing this tracker as completed.",
                "- No blocker issue is required.",
            ]
        )
    elif blocker_issue_number is not None:
        blocker = summary["blocker"]
        lines.extend(
            [
                "## Managed blocker",
                f"- Managed blocker issue: #{blocker_issue_number}",
                f"- Failure class: `{blocker['failure_class']}`",
                f"- Blocker run: [{blocker['run_id']}]({blocker['url']})",
            ]
        )
    else:
        lines.extend(
            [
                "## Managed blocker",
                "- No blocker issue is required yet.",
            ]
        )
    lines.extend(["", "## Reporter markdown", "", plan["markdown"].rstrip()])
    return "\n".join(lines).rstrip() + "\n"


def render_blocker_body(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    blocker = summary["blocker"]
    marker = blocker_marker(blocker["failure_class"])
    lines = [
        marker,
        f"# Android smoke reliability blocker: `{blocker['failure_class']}`",
        "",
        f"This issue is automation-managed by `{TRACKER_SCRIPT_PATH}`.",
        "",
        f"- Tracker issue: `#{plan['tracker']['issue']}`",
        f"- Repo: `{summary['repo']}`",
        f"- Workflow: `{summary['workflow']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Verdict: `{summary['verdict']}`",
        "- Reasons: `" + "`, `".join(summary["reasons"]) + "`",
        f"- Blocker run: [{blocker['run_id']}]({blocker['url']})",
        f"- Machine-readable failure_class: `{blocker['failure_class']}`",
        f"- Blocker conclusion: `{blocker['conclusion']}`",
        "",
        "## Reporter markdown",
        "",
        plan["markdown"].rstrip(),
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_dry_run(plan: dict[str, Any]) -> str:
    summary = {
        "report_kind": plan["report_kind"],
        "tracker": {
            "issue": plan["tracker"]["issue"],
            "current_state": plan["tracker"]["current_state"],
            "desired_state": plan["tracker"]["desired_state"],
        },
        "blocker": plan["blocker"],
    }
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


def apply_sync_plan(*, repo: str, plan: dict[str, Any], client: IssueClientProtocol) -> dict[str, Any]:
    blocker_issue_number = plan["blocker"].get("number")
    blocker_action = plan["blocker"]["action"]
    if blocker_action == "create":
        blocker_issue_number = client.create_issue(
            repo=repo,
            title=plan["blocker"]["title"],
            body=render_blocker_body(plan),
            labels=plan["blocker"]["labels"],
        )
    elif blocker_action == "update":
        client.edit_issue(
            repo=repo,
            number=plan["blocker"]["number"],
            body=render_blocker_body(plan),
            add_labels=plan["blocker"]["labels"],
        )
    elif blocker_action == "reopen":
        client.reopen_issue(repo=repo, number=plan["blocker"]["number"])
        client.edit_issue(
            repo=repo,
            number=plan["blocker"]["number"],
            body=render_blocker_body(plan),
            add_labels=plan["blocker"]["labels"],
        )
    elif blocker_action != "noop":
        raise IssueSyncError(f"Unsupported blocker action '{blocker_action}'")

    tracker_body = render_tracker_body(plan, blocker_issue_number=blocker_issue_number)
    tracker = plan["tracker"]
    if tracker["current_state"] == "CLOSED" and tracker["desired_state"] == "OPEN":
        client.reopen_issue(repo=repo, number=tracker["issue"])
        client.edit_issue(repo=repo, number=tracker["issue"], body=tracker_body)
    elif tracker["desired_state"] == "OPEN":
        client.edit_issue(repo=repo, number=tracker["issue"], body=tracker_body)
    elif tracker["current_state"] == "OPEN" and tracker["desired_state"] == "CLOSED":
        client.edit_issue(repo=repo, number=tracker["issue"], body=tracker_body)
        client.close_issue(repo=repo, number=tracker["issue"], reason="completed")
    elif tracker["desired_state"] == "CLOSED":
        client.edit_issue(repo=repo, number=tracker["issue"], body=tracker_body)
    else:
        raise IssueSyncError("Unsupported tracker transition")

    return {
        "tracker_issue": tracker["issue"],
        "tracker_desired_state": tracker["desired_state"],
        "blocker_action": blocker_action,
        "blocker_issue_number": blocker_issue_number,
    }


def gh_json(*args: str) -> Any:
    completed = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "gh command failed"
        raise IssueSyncError(stderr)
    try:
        return json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise IssueSyncError("gh command did not return valid JSON") from exc


def main() -> int:
    args = parse_args()
    try:
        summary = load_json(args.summary_json)
        markdown = load_text(args.markdown_file)
        issues = gh_json(
            "issue",
            "list",
            "--repo",
            args.repo,
            "--state",
            "all",
            "--limit",
            "500",
            "--json",
            "number,title,body,state",
        )
        if not isinstance(issues, list):
            raise IssueSyncError("GitHub issue search did not return a list")
        tracker_issue = find_issue_by_number(issues, issue_number=args.tracker_issue)
        plan = build_sync_plan(
            summary=summary,
            markdown=markdown,
            tracker_issue=tracker_issue,
            existing_issues=issues,
        )
        if args.dry_run:
            print(render_dry_run(plan), end="")
            return 0
        result = apply_sync_plan(repo=args.repo, plan=plan, client=GhIssueClient())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, IssueSyncError) as exc:
        print(f"android_smoke_issue_sync: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
