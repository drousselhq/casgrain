#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class CoverageRegressionError(Exception):
    """Raised when coverage summary JSON cannot be parsed safely."""


Metric = dict[str, int | float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a branch coverage summary against a baseline coverage summary."
    )
    parser.add_argument("--current", required=True, help="Path to the current branch coverage-report.json")
    parser.add_argument(
        "--baseline",
        default=None,
        help="Optional path to the baseline coverage-report.json (for example latest successful main)",
    )
    parser.add_argument("--summary-out", required=True, help="Path to write machine-readable comparison JSON")
    parser.add_argument("--markdown-out", required=True, help="Path to write markdown comparison summary")
    parser.add_argument(
        "--baseline-label",
        default="baseline",
        help="Human-readable label for the baseline (default: baseline)",
    )
    parser.add_argument(
        "--baseline-run-id",
        default=None,
        help="Optional GitHub Actions run ID that produced the baseline artifact",
    )
    return parser.parse_args()


def object_field(container: dict[str, Any], field_name: str, *, error_context: str) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if value is ... or not isinstance(value, dict):
        raise CoverageRegressionError(f"{error_context} field '{field_name}' must be an object")
    return value


def number_field(container: dict[str, Any], field_name: str, *, error_context: str) -> int | float:
    value = container.get(field_name, ...)
    if value is ... or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoverageRegressionError(f"{error_context} field '{field_name}' must be numeric")
    return value


def non_negative_int_field(container: dict[str, Any], field_name: str, *, error_context: str) -> int:
    value = container.get(field_name, ...)
    if value is ... or isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CoverageRegressionError(f"{error_context} field '{field_name}' must be a non-negative integer")
    return value


def metric_field(container: dict[str, Any], field_name: str, *, error_context: str) -> Metric:
    metric = object_field(container, field_name, error_context=error_context)
    count = non_negative_int_field(metric, "count", error_context=f"{error_context}.{field_name}")
    covered = non_negative_int_field(metric, "covered", error_context=f"{error_context}.{field_name}")
    percent = float(number_field(metric, "percent", error_context=f"{error_context}.{field_name}"))
    return {"count": count, "covered": covered, "percent": percent}


def load_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CoverageRegressionError(f"coverage summary not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CoverageRegressionError(f"coverage summary is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise CoverageRegressionError("coverage summary root must be an object")

    totals = object_field(payload, "totals", error_context="coverage summary")
    return {
        "totals": {
            "lines": metric_field(totals, "lines", error_context="coverage summary totals"),
            "functions": metric_field(totals, "functions", error_context="coverage summary totals"),
            "regions": metric_field(totals, "regions", error_context="coverage summary totals"),
        }
    }


def compare_reports(
    *,
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
    baseline_label: str,
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    current_lines = current["totals"]["lines"]

    if baseline is None:
        return {
            "status": "skipped",
            "baseline_label": baseline_label,
            "baseline_run_id": baseline_run_id,
            "meets_non_regression_gate": None,
            "line_percent_delta": None,
            "current": current,
            "baseline": None,
            "reason": f"{baseline_label} coverage baseline artifact unavailable",
        }

    baseline_lines = baseline["totals"]["lines"]
    delta = float(current_lines["percent"]) - float(baseline_lines["percent"])
    meets_gate = delta >= -1e-9
    return {
        "status": "evaluated",
        "baseline_label": baseline_label,
        "baseline_run_id": baseline_run_id,
        "meets_non_regression_gate": meets_gate,
        "line_percent_delta": delta,
        "current": current,
        "baseline": baseline,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    baseline_label = summary["baseline_label"]
    lines = ["## Coverage non-regression vs %s" % baseline_label, ""]

    if summary["status"] == "skipped":
        lines.append(
            f"⚪ Non-regression check skipped: {summary['reason']}. The 75% workspace floor still applies, but this PR was not compared against the latest successful {baseline_label} artifact."
        )
        if summary.get("baseline_run_id"):
            lines.append("")
            lines.append(f"Baseline run id: `{summary['baseline_run_id']}`")
        return "\n".join(lines) + "\n"

    current_lines = summary["current"]["totals"]["lines"]
    baseline_lines = summary["baseline"]["totals"]["lines"]
    delta = float(summary["line_percent_delta"])

    if summary["meets_non_regression_gate"]:
        lines.append(f"✅ Overall line coverage stayed at or above the {baseline_label} baseline.")
    else:
        lines.append(f"❌ Overall line coverage regressed below the {baseline_label} baseline.")

    lines.extend(
        [
            "",
            f"- {baseline_label}: **{baseline_lines['percent']:.2f}%** ({baseline_lines['covered']}/{baseline_lines['count']})",
            f"- current PR head: **{current_lines['percent']:.2f}%** ({current_lines['covered']}/{current_lines['count']})",
            f"- delta: **{delta:+.2f}** percentage points",
            "",
            "This gate only checks overall line-coverage non-regression. The stronger 85%+ changed-code and 90%+ critical-logic expectations still require reviewer judgment and targeted tests.",
        ]
    )
    if summary.get("baseline_run_id"):
        lines.extend(["", f"Baseline artifact run id: `{summary['baseline_run_id']}`"])
    return "\n".join(lines) + "\n"


def write_outputs(*, summary: dict[str, Any], summary_out: Path, markdown_out: Path) -> None:
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(summary), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        current = load_summary(Path(args.current))
        baseline_path = Path(args.baseline) if args.baseline else None
        baseline = None
        if baseline_path is not None and baseline_path.exists():
            baseline = load_summary(baseline_path)
        summary = compare_reports(
            current=current,
            baseline=baseline,
            baseline_label=args.baseline_label,
            baseline_run_id=args.baseline_run_id,
        )
        write_outputs(summary=summary, summary_out=Path(args.summary_out), markdown_out=Path(args.markdown_out))
    except CoverageRegressionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if summary["meets_non_regression_gate"] is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
