#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WATCHED_ECOSYSTEM_LABELS = {
    "actions": "GitHub Actions",
    "github-actions": "GitHub Actions",
    "github_actions": "GitHub Actions",
    "gradle": "Gradle-managed dependencies",
    "maven": "Gradle-managed dependencies",
}
ISSUE_TITLE = "security: non-cargo CVE watch findings"
SCOPE_TEXT = (
    "GitHub-native Dependabot alerts for GitHub Actions and Gradle-managed dependencies"
)


class DependabotReportError(Exception):
    """Raised when Dependabot alert data cannot be parsed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Dependabot alerts JSON into a triage-friendly non-Cargo CVE watch report."
    )
    parser.add_argument("--input", required=True, help="Path to Dependabot alerts JSON output")
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


def required_object_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, dict):
        raise DependabotReportError(f"{error_context} field '{field_name}' must be an object")
    return value


def optional_object_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if value is ... or value is None:
        return {}
    if not isinstance(value, dict):
        raise DependabotReportError(f"{error_context} field '{field_name}' must be an object")
    return value


def required_scalar_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, ""):
        raise DependabotReportError(f"{error_context} field '{field_name}' must be present and non-empty")
    if isinstance(value, (dict, list, tuple, set)):
        raise DependabotReportError(f"{error_context} field '{field_name}' must be a scalar value")
    return str(value)


def optional_scalar_field(
    container: dict[str, Any],
    field_name: str,
    *,
    error_context: str,
    default: str = "",
) -> str:
    value = container.get(field_name, default)
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list, tuple, set)):
        raise DependabotReportError(f"{error_context} field '{field_name}' must be a scalar value")
    return str(value)


def coerce_alert_entries(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise DependabotReportError("Dependabot alerts JSON root must be a list")

    flattened: list[dict[str, Any]] = []
    for entry in data:
        if isinstance(entry, list):
            for nested in entry:
                if not isinstance(nested, dict):
                    raise DependabotReportError("Dependabot alert entries must be objects")
                flattened.append(nested)
            continue
        if not isinstance(entry, dict):
            raise DependabotReportError("Dependabot alert entries must be objects")
        flattened.append(entry)
    return flattened


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def advisory_aliases(advisory: dict[str, Any]) -> list[str]:
    aliases: set[str] = set()
    ghsa_id = optional_scalar_field(
        advisory,
        "ghsa_id",
        error_context="Dependabot alert security_advisory",
        default="",
    )
    if ghsa_id:
        aliases.add(ghsa_id)

    cve_id = optional_scalar_field(
        advisory,
        "cve_id",
        error_context="Dependabot alert security_advisory",
        default="",
    )
    if cve_id:
        aliases.add(cve_id)

    identifiers = advisory.get("identifiers", [])
    if identifiers in (None, ""):
        identifiers = []
    if not isinstance(identifiers, list):
        raise DependabotReportError(
            "Dependabot alert security_advisory field 'identifiers' must be a list"
        )
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            raise DependabotReportError("Dependabot advisory identifiers must be objects")
        value = required_scalar_field(
            identifier,
            "value",
            error_context="Dependabot advisory identifier",
        )
        aliases.add(value)

    return sorted(aliases)


def extract_findings(data: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for entry in coerce_alert_entries(data):
        dependency = required_object_field(
            entry,
            "dependency",
            error_context="Dependabot alert",
        )
        package = required_object_field(
            dependency,
            "package",
            error_context="Dependabot alert dependency",
        )
        ecosystem = required_scalar_field(
            package,
            "ecosystem",
            error_context="Dependabot alert dependency package",
        ).lower()

        surface = WATCHED_ECOSYSTEM_LABELS.get(ecosystem)
        if surface is None:
            continue

        security_advisory = required_object_field(
            entry,
            "security_advisory",
            error_context="Dependabot alert",
        )
        security_vulnerability = required_object_field(
            entry,
            "security_vulnerability",
            error_context="Dependabot alert",
        )
        first_patched = optional_object_field(
            security_vulnerability,
            "first_patched_version",
            error_context="Dependabot alert security_vulnerability",
        )

        aliases = advisory_aliases(security_advisory)
        severity = optional_scalar_field(
            security_vulnerability,
            "severity",
            error_context="Dependabot alert security_vulnerability",
            default="",
        ) or optional_scalar_field(
            security_advisory,
            "severity",
            error_context="Dependabot alert security_advisory",
            default="unknown",
        )
        manifest_path = optional_scalar_field(
            dependency,
            "manifest_path",
            error_context="Dependabot alert dependency",
            default="unknown",
        )
        url = optional_scalar_field(
            entry,
            "html_url",
            error_context="Dependabot alert",
            default="",
        )
        if not url:
            references = security_advisory.get("references", [])
            if references in (None, ""):
                references = []
            if not isinstance(references, list):
                raise DependabotReportError(
                    "Dependabot alert security_advisory field 'references' must be a list"
                )
            for reference in references:
                if not isinstance(reference, dict):
                    raise DependabotReportError("Dependabot advisory references must be objects")
                url = optional_scalar_field(
                    reference,
                    "url",
                    error_context="Dependabot advisory reference",
                    default="",
                )
                if url:
                    break

        findings.append(
            {
                "alert_number": required_scalar_field(
                    entry,
                    "number",
                    error_context="Dependabot alert",
                ),
                "aliases": aliases,
                "ecosystem": ecosystem,
                "surface": surface,
                "package": required_scalar_field(
                    package,
                    "name",
                    error_context="Dependabot alert dependency package",
                ),
                "manifest_path": manifest_path,
                "severity": severity,
                "vulnerable_version_range": optional_scalar_field(
                    security_vulnerability,
                    "vulnerable_version_range",
                    error_context="Dependabot alert security_vulnerability",
                    default="unknown",
                ),
                "first_patched_version": optional_scalar_field(
                    first_patched,
                    "identifier",
                    error_context="Dependabot alert security_vulnerability first_patched_version",
                    default="none listed",
                ),
                "summary": required_scalar_field(
                    security_advisory,
                    "summary",
                    error_context="Dependabot alert security_advisory",
                ),
                "url": url,
            }
        )

    findings.sort(key=lambda item: (item["surface"], item["manifest_path"], item["package"], item["alert_number"]))
    return findings


def build_summary(data: Any, generated_at: str) -> dict[str, Any]:
    findings = extract_findings(data)
    return {
        "alert": bool(findings),
        "advisory_count": len(findings),
        "package_count": len({item["package"] for item in findings}),
        "ecosystems": sorted({item["ecosystem"] for item in findings}),
        "surfaces": sorted({item["surface"] for item in findings}),
        "manifest_paths": sorted({item["manifest_path"] for item in findings}),
        "aliases": sorted({alias for item in findings for alias in item["aliases"]}),
        "alert_numbers": [item["alert_number"] for item in findings],
        "generated_at": generated_at,
        "findings": findings,
        "issue_title": ISSUE_TITLE,
        "scope": SCOPE_TEXT,
    }


def render_markdown(summary: dict[str, Any], run_url: str) -> str:
    lines = [
        "<!-- cve-watch-report -->",
        f"# {summary['issue_title']}",
        "",
        "This issue is maintained automatically by the scheduled CVE watch workflow.",
        "",
        "## Scope",
        f"- Automated scope today: {summary['scope']}",
        "- Rust crate advisories remain covered by the separate `cargo audit` watch and PR-time `cargo audit` check.",
        "- Downloaded CLI tooling, runner-image CVEs, and repository settings blockers still require the manual security-review cadence.",
        f"- Generated at: `{summary['generated_at']}`",
    ]
    if run_url:
        lines.append(f"- Source run: {run_url}")

    if summary["advisory_count"] == 0:
        lines.extend(
            [
                "",
                "## Status",
                "- No active GitHub-native Dependabot alerts matched the watched non-Cargo ecosystems.",
                "- Clean runs are recorded in the workflow summary only; this issue should normally stay closed or absent when the watched surfaces are clean.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "## Active findings",
            f"- Alert count: **{summary['advisory_count']}**",
            f"- Affected packages: **{summary['package_count']}**",
            f"- Watched surfaces currently hit: **{', '.join(summary['surfaces'])}**",
            "",
            "| Alert | GHSA / CVE aliases | Surface | Package | Manifest path | Severity | First patched version |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for finding in summary["findings"]:
        alert_cell = f"#{finding['alert_number']}"
        if finding["url"]:
            alert_cell = f"[{alert_cell}]({finding['url']})"
        aliases = ", ".join(finding["aliases"]) if finding["aliases"] else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    sanitize_cell(alert_cell),
                    sanitize_cell(aliases),
                    sanitize_cell(finding["surface"]),
                    sanitize_cell(finding["package"]),
                    sanitize_cell(finding["manifest_path"]),
                    sanitize_cell(finding["severity"]),
                    sanitize_cell(finding["first_patched_version"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Triage notes"])
    for finding in summary["findings"]:
        aliases = ", ".join(finding["aliases"]) if finding["aliases"] else "no alias listed"
        lines.extend(
            [
                f"- **#{finding['alert_number']} — {finding['package']}** ({finding['surface']}; `{finding['manifest_path']}`)",
                f"  - advisory IDs: {aliases}",
                f"  - severity: {finding['severity']}",
                f"  - vulnerable range: `{finding['vulnerable_version_range']}`",
                f"  - first patched version: `{finding['first_patched_version']}`",
                f"  - summary: {finding['summary']}",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        summary = build_summary(data, generated_at)
        markdown = render_markdown(summary, args.run_url)
    except (OSError, json.JSONDecodeError, DependabotReportError) as exc:
        print(f"dependabot_alerts_report: {exc}", file=sys.stderr)
        return 2

    Path(args.summary_out).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
