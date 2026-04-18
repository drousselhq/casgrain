#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_MARKER = "<!-- cve-watch-report -->"
MANAGED_LABELS = ["devops", "security-review-needed"]


class IssueSyncError(Exception):
    """Raised when CVE watch issue synchronization cannot proceed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize the managed CVE-watch findings issue from summary JSON."
    )
    parser.add_argument("--repo", required=True, help="owner/repo for gh issue operations")
    parser.add_argument(
        "--summary-json",
        required=True,
        help="Path to the machine-readable summary JSON emitted by cve_watch_report.py",
    )
    parser.add_argument(
        "--markdown-file",
        required=True,
        help="Path to the rendered markdown report to apply to the managed issue",
    )
    parser.add_argument(
        "--run-url",
        default="",
        help="Workflow run URL for clean-close comments",
    )
    return parser.parse_args()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    number = issue.get("number")
    title = issue.get("title")
    body = issue.get("body") or ""
    state = str(issue.get("state", "")).upper()
    if not isinstance(number, int) or number <= 0:
        raise IssueSyncError("GitHub issue search result is missing a valid numeric issue number")
    if not isinstance(title, str) or not title:
        raise IssueSyncError(f"GitHub issue #{number} is missing a valid title")
    if state not in {"OPEN", "CLOSED"}:
        raise IssueSyncError(f"GitHub issue #{number} has unsupported state '{state}'")
    return {"number": number, "title": title, "body": body, "state": state}


def select_managed_issue(
    issues: list[dict[str, Any]], *, expected_title: str
) -> dict[str, Any] | None:
    normalized = [normalize_issue(issue) for issue in issues if issue.get("title") == expected_title]
    marker_matches = [issue for issue in normalized if REPORT_MARKER in issue.get("body", "")]
    if not marker_matches:
        return None
    marker_matches.sort(key=lambda issue: (issue["state"] != "OPEN", issue["number"]))
    return marker_matches[0]


def build_clean_comment(*, run_url: str, advisory_count: int) -> str:
    lines = ["Scheduled CVE watch is clean again.", ""]
    if run_url:
        lines.append(f"Latest clean run: {run_url}")
    lines.append(f"Advisory count: {advisory_count}")
    return "\n".join(lines) + "\n"


def build_sync_plan(
    *,
    summary: dict[str, Any],
    markdown: str,
    existing_issues: list[dict[str, Any]],
    run_url: str,
) -> dict[str, Any]:
    issue_title = summary.get("issue_title")
    if not isinstance(issue_title, str) or not issue_title:
        raise IssueSyncError("CVE watch summary is missing a non-empty issue_title")
    advisory_count = summary.get("advisory_count")
    if not isinstance(advisory_count, int) or advisory_count < 0:
        raise IssueSyncError("CVE watch summary is missing a valid advisory_count")
    alert = summary.get("alert")
    if not isinstance(alert, bool):
        raise IssueSyncError("CVE watch summary is missing a boolean alert flag")
    if REPORT_MARKER not in markdown:
        raise IssueSyncError("Managed CVE-watch markdown must include the report marker")

    existing = select_managed_issue(existing_issues, expected_title=issue_title)
    if alert:
        if existing is None:
            return {
                "action": "create",
                "title": issue_title,
                "body": markdown,
                "labels": MANAGED_LABELS,
            }
        if existing["state"] == "OPEN":
            return {
                "action": "update",
                "number": existing["number"],
                "body": markdown,
                "labels": MANAGED_LABELS,
            }
        return {
            "action": "reopen",
            "number": existing["number"],
            "body": markdown,
            "labels": MANAGED_LABELS,
        }

    if existing is None or existing["state"] != "OPEN":
        return {"action": "noop"}

    return {
        "action": "close",
        "number": existing["number"],
        "comment": build_clean_comment(run_url=run_url, advisory_count=advisory_count),
    }


def gh_json(*args: str) -> Any:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout or "[]")


def gh_run(*args: str) -> None:
    subprocess.run(["gh", *args], check=True, text=True, capture_output=True)


def apply_sync_plan(*, repo: str, plan: dict[str, Any]) -> str:
    action = plan["action"]
    if action == "noop":
        return "noop"
    if action == "create":
        gh_run(
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            plan["title"],
            "--body-file",
            plan["body_file"],
            "--label",
            ",".join(plan["labels"]),
        )
        return "create"
    if action == "update":
        gh_run(
            "issue",
            "edit",
            str(plan["number"]),
            "--repo",
            repo,
            "--body-file",
            plan["body_file"],
            "--add-label",
            ",".join(plan["labels"]),
        )
        return "update"
    if action == "reopen":
        gh_run("issue", "reopen", str(plan["number"]), "--repo", repo)
        gh_run(
            "issue",
            "edit",
            str(plan["number"]),
            "--repo",
            repo,
            "--body-file",
            plan["body_file"],
            "--add-label",
            ",".join(plan["labels"]),
        )
        return "reopen"
    if action == "close":
        comment_path = plan["comment_file"]
        gh_run(
            "issue",
            "comment",
            str(plan["number"]),
            "--repo",
            repo,
            "--body-file",
            comment_path,
        )
        gh_run(
            "issue",
            "close",
            str(plan["number"]),
            "--repo",
            repo,
            "--reason",
            "completed",
        )
        return "close"
    raise IssueSyncError(f"Unsupported sync action '{action}'")


def main() -> int:
    args = parse_args()

    try:
        summary = load_json(args.summary_json)
        if not isinstance(summary, dict):
            raise IssueSyncError("CVE watch summary JSON root must be an object")
        markdown = load_text(args.markdown_file)
        search_results = gh_json(
            "issue",
            "list",
            "--repo",
            args.repo,
            "--state",
            "all",
            "--search",
            f"{summary.get('issue_title', '')} in:title",
            "--limit",
            "100",
            "--json",
            "number,title,body,state",
        )
        if not isinstance(search_results, list):
            raise IssueSyncError("GitHub issue search did not return a list")

        plan = build_sync_plan(
            summary=summary,
            markdown=markdown,
            existing_issues=search_results,
            run_url=args.run_url,
        )

        body_file = Path(args.markdown_file)
        if plan["action"] in {"create", "update", "reopen"}:
            plan = {**plan, "body_file": str(body_file)}
        if plan["action"] == "close":
            comment_path = body_file.parent / "cve-watch-clean-comment.txt"
            comment_path.write_text(plan["comment"], encoding="utf-8")
            plan = {**plan, "comment_file": str(comment_path)}

        applied = apply_sync_plan(repo=args.repo, plan=plan)
        print(applied)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, IssueSyncError) as exc:
        print(f"cve_watch_issue_sync: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
