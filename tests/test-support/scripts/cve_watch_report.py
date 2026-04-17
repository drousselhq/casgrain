#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditReportError(Exception):
    """Raised when cargo-audit report data cannot be parsed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert cargo-audit JSON into a triage-friendly CVE watch report."
    )
    parser.add_argument("--input", required=True, help="Path to cargo-audit JSON output")
    parser.add_argument(
        "--markdown-out",
        required=True,
        help="Path to write the rendered markdown report",
    )
    parser.add_argument(
        "--summary-out",
        required=True,
        help="Path to write machine-readable summary JSON",
    )
    parser.add_argument(
        "--run-url",
        default="",
        help="Optional workflow run URL to include in the report",
    )
    parser.add_argument(
        "--generated-at",
        default="",
        help="Optional ISO-8601 UTC timestamp override",
    )
    return parser.parse_args()


def coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


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
            raise AuditReportError(f"{error_context} field '{field_name}' must be an object")
        return {}
    if not isinstance(value, dict):
        raise AuditReportError(f"{error_context} field '{field_name}' must be an object")
    return value


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def advisory_cvss(advisory: dict[str, Any]) -> str:
    cvss = advisory.get("cvss")
    if isinstance(cvss, dict):
        score = cvss.get("score")
        if score not in (None, ""):
            return str(score)
    if cvss not in (None, ""):
        return str(cvss)
    return "unknown"


def required_scalar_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, ""):
        raise AuditReportError(f"{error_context} field '{field_name}' must be present and non-empty")
    if isinstance(value, (dict, list, tuple, set)):
        raise AuditReportError(f"{error_context} field '{field_name}' must be a scalar value")
    return str(value)


def versions_text(entry: dict[str, Any]) -> str:
    versions = object_field(
        entry,
        "versions",
        error_context="cargo-audit JSON vulnerability entry",
        required=False,
    )
    patched = coerce_list(versions.get("patched"))
    unaffected = coerce_list(versions.get("unaffected"))

    parts: list[str] = []
    if patched:
        parts.append("patched: " + ", ".join(str(item) for item in patched))
    if unaffected:
        parts.append("unaffected: " + ", ".join(str(item) for item in unaffected))
    return "; ".join(parts) if parts else "none listed"


def extract_findings(data: dict[str, Any]) -> list[dict[str, Any]]:
    vulnerabilities = object_field(
        data,
        "vulnerabilities",
        error_context="cargo-audit JSON",
    )

    if "list" not in vulnerabilities:
        raise AuditReportError("cargo-audit JSON field 'vulnerabilities.list' must be present")
    raw_list = vulnerabilities["list"]
    if not isinstance(raw_list, list):
        raise AuditReportError("cargo-audit JSON field 'vulnerabilities.list' must be a list")

    findings: list[dict[str, Any]] = []

    for entry in raw_list:
        if not isinstance(entry, dict):
            raise AuditReportError("cargo-audit JSON vulnerability entries must be objects")
        advisory = object_field(
            entry,
            "advisory",
            error_context="cargo-audit JSON vulnerability entry",
        )
        package = object_field(
            entry,
            "package",
            error_context="cargo-audit JSON vulnerability entry",
        )
        aliases = [str(alias) for alias in coerce_list(advisory.get("aliases"))]
        findings.append(
            {
                "advisory_id": required_scalar_field(
                    advisory,
                    "id",
                    error_context="cargo-audit JSON vulnerability advisory",
                ),
                "title": required_scalar_field(
                    advisory,
                    "title",
                    error_context="cargo-audit JSON vulnerability advisory",
                ),
                "package": required_scalar_field(
                    package,
                    "name",
                    error_context="cargo-audit JSON vulnerability package",
                ),
                "version": required_scalar_field(
                    package,
                    "version",
                    error_context="cargo-audit JSON vulnerability package",
                ),
                "aliases": aliases,
                "cvss": advisory_cvss(advisory),
                "patched_versions": versions_text(entry),
                "url": str(advisory.get("url", "")),
            }
        )

    findings.sort(key=lambda item: (item["package"], item["advisory_id"]))
    return findings


def build_summary(data: dict[str, Any], generated_at: str) -> dict[str, Any]:
    findings = extract_findings(data)
    database = object_field(data, "database", error_context="cargo-audit JSON")
    lockfile = object_field(data, "lockfile", error_context="cargo-audit JSON")

    return {
        "alert": bool(findings),
        "advisory_count": len(findings),
        "package_count": len({item["package"] for item in findings}),
        "advisory_ids": [item["advisory_id"] for item in findings],
        "aliases": sorted({alias for item in findings for alias in item["aliases"]}),
        "database_last_updated": database.get("last-updated", "unknown"),
        "database_commit": database.get("last-commit", "unknown"),
        "lockfile_timestamp": lockfile.get("timestamp", "unknown"),
        "generated_at": generated_at,
        "findings": findings,
        "issue_title": "security: dependency CVE watch findings",
        "scope": "Rust dependency advisories reported by cargo audit",
    }


def render_markdown(summary: dict[str, Any], run_url: str) -> str:
    generated_at = summary["generated_at"]
    db_updated = summary["database_last_updated"]
    advisory_count = summary["advisory_count"]
    package_count = summary["package_count"]
    issue_title = summary["issue_title"]
    lines = [
        "<!-- cve-watch-report -->",
        f"# {issue_title}",
        "",
        "This issue is maintained automatically by the scheduled CVE watch workflow.",
        "",
        "## Scope",
        f"- Automated scope today: {summary['scope']}",
        "- GitHub Actions, downloaded tooling, and other non-Cargo infrastructure still require the existing manual/security-review cadence.",
        f"- Generated at: `{generated_at}`",
        f"- RustSec advisory DB last updated: `{db_updated}`",
    ]

    if run_url:
        lines.append(f"- Source run: {run_url}")

    if advisory_count == 0:
        lines.extend(
            [
                "",
                "## Status",
                "- No active Rust dependency advisories were reported by `cargo audit`.",
                "- Clean runs are recorded in the workflow summary only; this issue should normally stay closed or absent when the dependency surface is clean.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "## Active findings",
            f"- Advisory count: **{advisory_count}**",
            f"- Affected packages: **{package_count}**",
            "",
            "| Advisory | CVE aliases | Package | Current version | CVSS | Patched versions |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    for finding in summary["findings"]:
        advisory_cell = finding["advisory_id"]
        if finding["url"]:
            advisory_cell = f"[{finding['advisory_id']}]({finding['url']})"
        aliases = ", ".join(finding["aliases"]) if finding["aliases"] else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    sanitize_cell(advisory_cell),
                    sanitize_cell(aliases),
                    sanitize_cell(finding["package"]),
                    sanitize_cell(finding["version"]),
                    sanitize_cell(finding["cvss"]),
                    sanitize_cell(finding["patched_versions"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Triage expectations",
            "1. Confirm whether the affected package is reachable in the current Casgrain build/runtime path.",
            "2. Open or update a remediation PR when an upgrade or exception is clear.",
            "3. If remediation cannot land in-repo yet, keep the blocker explicit in GitHub instead of letting this report become tribal knowledge.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise AuditReportError("cargo-audit JSON root must be an object")

        summary = build_summary(data, generated_at=generated_at)
        markdown = render_markdown(summary, run_url=args.run_url)

        Path(args.summary_out).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    except (OSError, json.JSONDecodeError, AuditReportError) as exc:
        print(f"cve_watch_report: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
