#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


class CoverageReportError(Exception):
    """Raised when cargo-llvm-cov JSON cannot be parsed safely."""


Metric = dict[str, int | float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render CI-friendly coverage summaries from cargo-llvm-cov JSON output."
    )
    parser.add_argument("--input", required=True, help="Path to cargo-llvm-cov JSON summary output")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used to normalize file paths in the report",
    )
    parser.add_argument(
        "--markdown-out",
        required=True,
        help="Path to write the rendered markdown coverage summary",
    )
    parser.add_argument(
        "--summary-out",
        required=True,
        help="Path to write machine-readable distilled coverage summary JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional minimum line-coverage threshold to render in the summary",
    )
    parser.add_argument(
        "--top-files",
        type=int,
        default=5,
        help="How many lowest line-coverage files to surface in the markdown summary",
    )
    return parser.parse_args()


def object_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if value is ... or not isinstance(value, dict):
        raise CoverageReportError(f"{error_context} field '{field_name}' must be an object")
    return value


def list_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> list[Any]:
    value = container.get(field_name, ...)
    if value is ... or not isinstance(value, list):
        raise CoverageReportError(f"{error_context} field '{field_name}' must be a list")
    return value


def number_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> int | float:
    value = container.get(field_name, ...)
    if value is ... or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoverageReportError(f"{error_context} field '{field_name}' must be numeric")
    return value


def metric_field(container: dict[str, Any], field_name: str, *, error_context: str) -> Metric:
    metric = object_field(container, field_name, error_context=error_context)
    count = int(number_field(metric, "count", error_context=f"{error_context}.{field_name}"))
    covered = int(number_field(metric, "covered", error_context=f"{error_context}.{field_name}"))
    percent = float(number_field(metric, "percent", error_context=f"{error_context}.{field_name}"))
    return {"count": count, "covered": covered, "percent": percent}


def empty_metric() -> Metric:
    return {"count": 0, "covered": 0, "percent": 0.0}


def aggregate_metrics(metrics: list[Metric]) -> Metric:
    count = sum(int(metric["count"]) for metric in metrics)
    covered = sum(int(metric["covered"]) for metric in metrics)
    percent = (covered / count * 100.0) if count else 0.0
    return {"count": count, "covered": covered, "percent": percent}


def format_ratio(metric: Metric) -> str:
    return f"{int(metric['covered'])}/{int(metric['count'])}"


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def relative_path(filename: str, repo_root: Path) -> str:
    file_path = Path(filename)
    try:
        normalized = file_path.resolve().relative_to(repo_root.resolve())
        return normalized.as_posix()
    except (OSError, RuntimeError, ValueError):
        if file_path.is_absolute():
            return file_path.as_posix()
        return PurePosixPath(filename).as_posix()


def scope_name(path_text: str) -> str:
    parts = PurePosixPath(path_text).parts
    if len(parts) >= 2 and parts[0] == "crates":
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return path_text


def build_summary(
    data: dict[str, Any],
    *,
    repo_root: Path,
    threshold: float | None,
    top_files: int,
) -> dict[str, Any]:
    reports = list_field(data, "data", error_context="cargo-llvm-cov JSON")
    if not reports:
        raise CoverageReportError("cargo-llvm-cov JSON field 'data' must contain at least one report")

    report = reports[0]
    if not isinstance(report, dict):
        raise CoverageReportError("cargo-llvm-cov JSON report entries must be objects")

    totals_container = object_field(report, "totals", error_context="cargo-llvm-cov report")
    files_container = list_field(report, "files", error_context="cargo-llvm-cov report")

    totals = {
        "lines": metric_field(totals_container, "lines", error_context="cargo-llvm-cov report totals"),
        "functions": metric_field(
            totals_container,
            "functions",
            error_context="cargo-llvm-cov report totals",
        ),
        "regions": metric_field(totals_container, "regions", error_context="cargo-llvm-cov report totals"),
    }

    files: list[dict[str, Any]] = []
    scopes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "scope": "",
            "file_count": 0,
            "lines_metrics": [],
            "functions_metrics": [],
            "regions_metrics": [],
        }
    )

    for entry in files_container:
        if not isinstance(entry, dict):
            raise CoverageReportError("cargo-llvm-cov file entries must be objects")
        filename = entry.get("filename")
        if not isinstance(filename, str) or not filename:
            raise CoverageReportError("cargo-llvm-cov file entries must contain a non-empty filename")
        summary = object_field(entry, "summary", error_context=f"cargo-llvm-cov file '{filename}'")
        rel_path = relative_path(filename, repo_root)
        scope = scope_name(rel_path)
        file_summary = {
            "path": rel_path,
            "scope": scope,
            "lines": metric_field(summary, "lines", error_context=f"coverage summary for {rel_path}"),
            "functions": metric_field(
                summary,
                "functions",
                error_context=f"coverage summary for {rel_path}",
            ),
            "regions": metric_field(
                summary,
                "regions",
                error_context=f"coverage summary for {rel_path}",
            ),
        }
        files.append(file_summary)

        scope_entry = scopes[scope]
        scope_entry["scope"] = scope
        scope_entry["file_count"] += 1
        scope_entry["lines_metrics"].append(file_summary["lines"])
        scope_entry["functions_metrics"].append(file_summary["functions"])
        scope_entry["regions_metrics"].append(file_summary["regions"])

    files.sort(key=lambda item: (item["lines"]["percent"], item["path"]))

    scope_summaries = []
    for scope, scope_entry in scopes.items():
        scope_summaries.append(
            {
                "scope": scope,
                "file_count": scope_entry["file_count"],
                "lines": aggregate_metrics(scope_entry["lines_metrics"]),
                "functions": aggregate_metrics(scope_entry["functions_metrics"]),
                "regions": aggregate_metrics(scope_entry["regions_metrics"]),
            }
        )

    scope_summaries.sort(key=lambda item: (item["lines"]["percent"], item["scope"]))

    line_threshold = float(threshold) if threshold is not None else None
    line_percent = float(totals["lines"]["percent"])

    summary = {
        "line_threshold": line_threshold,
        "meets_line_threshold": None if line_threshold is None else line_percent >= line_threshold,
        "totals": totals,
        "file_count": len(files),
        "scopes": scope_summaries,
        "files": files,
        "lowest_line_coverage_files": files[: max(top_files, 0)],
    }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines_metric = totals["lines"]
    functions_metric = totals["functions"]
    regions_metric = totals["regions"]
    threshold = summary["line_threshold"]
    meets_threshold = summary["meets_line_threshold"]

    if threshold is None:
        status = "Coverage report generated."
    elif meets_threshold:
        status = f"✅ Line coverage is above the configured {threshold:.0f}% threshold."
    else:
        status = f"❌ Line coverage is below the configured {threshold:.0f}% threshold."

    markdown = [
        "## Coverage summary",
        "",
        f"- {status}",
        (
            f"- Lines: **{lines_metric['percent']:.2f}%** "
            f"({format_ratio(lines_metric)})"
            + (f" against threshold **{threshold:.0f}%**" if threshold is not None else "")
        ),
        f"- Functions: **{functions_metric['percent']:.2f}%** ({format_ratio(functions_metric)})",
        f"- Regions: **{regions_metric['percent']:.2f}%** ({format_ratio(regions_metric)})",
        f"- Files measured: **{summary['file_count']}**",
        "",
    ]

    scopes = summary["scopes"]
    if scopes:
        markdown.extend(
            [
                "### Coverage by scope",
                "",
                "| Scope | Files | Line % | Covered / total lines | Function % | Region % |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for scope in scopes:
            markdown.append(
                "| "
                + " | ".join(
                    [
                        sanitize_cell(scope["scope"]),
                        str(scope["file_count"]),
                        f"{scope['lines']['percent']:.2f}%",
                        sanitize_cell(format_ratio(scope["lines"])),
                        f"{scope['functions']['percent']:.2f}%",
                        f"{scope['regions']['percent']:.2f}%",
                    ]
                )
                + " |"
            )
        markdown.append("")

    lowest_files = summary["lowest_line_coverage_files"]
    if lowest_files:
        markdown.extend(
            [
                "### Lowest line-coverage files",
                "",
                "| File | Line % | Covered / total lines | Function % | Region % |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for file_summary in lowest_files:
            markdown.append(
                "| "
                + " | ".join(
                    [
                        sanitize_cell(file_summary["path"]),
                        f"{file_summary['lines']['percent']:.2f}%",
                        sanitize_cell(format_ratio(file_summary["lines"])),
                        f"{file_summary['functions']['percent']:.2f}%",
                        f"{file_summary['regions']['percent']:.2f}%",
                    ]
                )
                + " |"
            )
        markdown.append("")

    markdown.extend(
        [
            "### Artifacts",
            "",
            "- `target/llvm-cov/coverage-summary.json` — raw cargo-llvm-cov summary JSON",
            "- `target/llvm-cov/coverage-report.json` — distilled summary for future ratchet/reporting automation",
            "- `target/llvm-cov/lcov.info` — LCOV export for downstream tooling",
        ]
    )

    return "\n".join(markdown) + "\n"


def main() -> int:
    args = parse_args()
    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise CoverageReportError("cargo-llvm-cov JSON root must be an object")

        summary = build_summary(
            data,
            repo_root=Path(args.repo_root),
            threshold=args.threshold,
            top_files=args.top_files,
        )
        markdown = render_markdown(summary)

        Path(args.summary_out).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    except (CoverageReportError, OSError, json.JSONDecodeError) as exc:
        print(f"coverage_report: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
