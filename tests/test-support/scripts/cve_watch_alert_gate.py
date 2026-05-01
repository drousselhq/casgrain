#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class AlertGateError(Exception):
    """Raised when a CVE-watch summary cannot be evaluated safely."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail a scheduled CVE-watch job when its rendered summary contains active findings."
    )
    parser.add_argument("--summary-json", required=True, help="Path to the report summary JSON")
    parser.add_argument("--report-name", required=True, help="Human-readable report name for logs")
    parser.add_argument("--run-url", default="", help="Workflow run URL to include in failure output")
    return parser.parse_args(argv)


def load_summary(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AlertGateError("CVE watch summary JSON root must be an object")
    return payload


def normalize_summary(summary: dict[str, Any]) -> tuple[bool, int, str]:
    alert = summary.get("alert")
    if not isinstance(alert, bool):
        raise AlertGateError("CVE watch summary is missing a boolean alert flag")
    advisory_count = summary.get("advisory_count")
    if type(advisory_count) is not int or advisory_count < 0:
        raise AlertGateError("CVE watch summary is missing a non-negative integer advisory_count")
    title = summary.get("report_title") or summary.get("title") or "CVE watch findings"
    if not isinstance(title, str) or not title:
        raise AlertGateError("CVE watch summary title must be a non-empty string when present")
    if alert and advisory_count == 0:
        raise AlertGateError("CVE watch summary reports alert=true with zero advisories")
    if not alert and advisory_count > 0:
        raise AlertGateError("CVE watch summary reports advisories without alert=true")
    return alert, advisory_count, title


def render_failure_message(*, report_name: str, title: str, advisory_count: int, run_url: str) -> str:
    lines = [
        f"::error title={report_name} findings::Active findings detected ({advisory_count}). See the workflow summary for {title}.",
        f"{report_name}: active findings detected for {title}",
        f"Advisory count: {advisory_count}",
    ]
    if run_url:
        lines.append(f"Run: {run_url}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        alert, advisory_count, title = normalize_summary(load_summary(args.summary_json))
    except (OSError, json.JSONDecodeError, AlertGateError) as exc:
        print(f"cve_watch_alert_gate: {exc}", file=sys.stderr)
        return 2

    if not alert:
        print(f"{args.report_name}: no active CVE-watch findings")
        return 0

    print(
        render_failure_message(
            report_name=args.report_name,
            title=title,
            advisory_count=advisory_count,
            run_url=args.run_url,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
