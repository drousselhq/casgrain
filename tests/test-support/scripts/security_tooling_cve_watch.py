#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ISSUE_TITLE = "security: security-tooling CVE watch findings"
SCOPE_TEXT = "Workflow-installed security tooling outside Cargo.lock / Dependabot coverage"
REPORT_MARKER = "<!-- cve-watch-report -->"
GRAPHQL_QUERY = """
query($ecosystem: SecurityAdvisoryEcosystem!, $package: String!) {
  securityVulnerabilities(first: 100, ecosystem: $ecosystem, package: $package) {
    nodes {
      advisory {
        ghsaId
        summary
        permalink
        identifiers { type value }
      }
      package {
        ecosystem
        name
      }
      vulnerableVersionRange
      firstPatchedVersion { identifier }
      severity
      updatedAt
    }
  }
}
"""


class SecurityToolingWatchError(Exception):
    """Raised when the security-tooling watch cannot proceed safely."""


SEMVER_RE = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)"
    r"(?:\.(?P<minor>0|[1-9]\d*))?"
    r"(?:\.(?P<patch>0|[1-9]\d*))?"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a triage-friendly CVE watch report for workflow-installed security tooling."
    )
    parser.add_argument("--manifest", required=True, help="Path to the checked-in security-tooling manifest")
    parser.add_argument("--markdown-out", required=True, help="Path to write rendered markdown output")
    parser.add_argument("--summary-out", required=True, help="Path to write machine-readable summary JSON")
    parser.add_argument("--run-url", default="", help="Optional workflow run URL to include in the report")
    parser.add_argument(
        "--generated-at",
        default="",
        help="Optional ISO-8601 UTC timestamp override for deterministic tests",
    )
    return parser.parse_args()


def required_scalar_field(container: dict[str, Any], field_name: str, *, error_context: str) -> str:
    value = container.get(field_name, ...)
    if value in (..., None, ""):
        raise SecurityToolingWatchError(
            f"{error_context} field '{field_name}' must be present and non-empty"
        )
    if isinstance(value, (dict, list, tuple, set)):
        raise SecurityToolingWatchError(
            f"{error_context} field '{field_name}' must be a scalar value"
        )
    return str(value)


def required_object_field(container: dict[str, Any], field_name: str, *, error_context: str) -> dict[str, Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, dict):
        raise SecurityToolingWatchError(f"{error_context} field '{field_name}' must be an object")
    return value


def required_list_field(container: dict[str, Any], field_name: str, *, error_context: str) -> list[Any]:
    value = container.get(field_name, ...)
    if not isinstance(value, list):
        raise SecurityToolingWatchError(f"{error_context} field '{field_name}' must be a list")
    return value


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def normalize_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SecurityToolingWatchError("Security-tooling manifest JSON root must be an object")

    issue_title = required_scalar_field(data, "issue_title", error_context="security-tooling manifest")
    scope = required_scalar_field(data, "scope", error_context="security-tooling manifest")
    tools_input = required_list_field(data, "tools", error_context="security-tooling manifest")
    if not tools_input:
        raise SecurityToolingWatchError("Security-tooling manifest must define at least one tool")

    normalized_tools: list[dict[str, Any]] = []
    for index, tool_entry in enumerate(tools_input):
        if not isinstance(tool_entry, dict):
            raise SecurityToolingWatchError("Security-tooling manifest tools must be objects")
        context = f"security-tooling manifest tool #{index + 1}"
        tool_name = required_scalar_field(tool_entry, "tool", error_context=context)
        version = required_scalar_field(tool_entry, "version", error_context=context)
        workflows = required_list_field(tool_entry, "workflows", error_context=context)
        if not workflows or not all(isinstance(item, str) and item for item in workflows):
            raise SecurityToolingWatchError(f"{context} field 'workflows' must contain non-empty strings")
        source_rule = required_object_field(tool_entry, "source_rule", error_context=context)
        kind = required_scalar_field(source_rule, "kind", error_context=f"{context} source_rule")

        normalized_source_rule = {"kind": kind}
        if kind == "github-security-vulnerabilities":
            normalized_source_rule.update(
                {
                    "ecosystem": required_scalar_field(
                        source_rule,
                        "ecosystem",
                        error_context=f"{context} source_rule",
                    ),
                    "package": required_scalar_field(
                        source_rule,
                        "package",
                        error_context=f"{context} source_rule",
                    ),
                    "source": required_scalar_field(
                        source_rule,
                        "source",
                        error_context=f"{context} source_rule",
                    ),
                }
            )
        elif kind == "manual-review-required":
            normalized_source_rule["rationale"] = required_scalar_field(
                source_rule,
                "rationale",
                error_context=f"{context} source_rule",
            )
        else:
            raise SecurityToolingWatchError(
                f"{context} source_rule kind '{kind}' is not supported"
            )

        normalized_tools.append(
            {
                "tool": tool_name,
                "version": version,
                "workflows": workflows,
                "source_rule": normalized_source_rule,
            }
        )

    return {
        "issue_title": issue_title,
        "scope": scope,
        "tools": normalized_tools,
    }


def parse_semver(version: str) -> tuple[tuple[int, int, int], tuple[Any, ...] | None]:
    match = SEMVER_RE.match(version.strip())
    if match is None:
        raise SecurityToolingWatchError(f"Unsupported semantic version '{version}'")
    core = (
        int(match.group("major") or 0),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
    )
    prerelease_text = match.group("prerelease")
    if not prerelease_text:
        return core, None

    prerelease_parts: list[Any] = []
    for part in prerelease_text.split("."):
        prerelease_parts.append(int(part) if part.isdigit() else part)
    return core, tuple(prerelease_parts)


def compare_prerelease(
    left: tuple[Any, ...] | None,
    right: tuple[Any, ...] | None,
) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1

    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue
        left_is_int = isinstance(left_part, int)
        right_is_int = isinstance(right_part, int)
        if left_is_int and right_is_int:
            return -1 if left_part < right_part else 1
        if left_is_int != right_is_int:
            return -1 if left_is_int else 1
        return -1 if str(left_part) < str(right_part) else 1

    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def compare_versions(left: str, right: str) -> int:
    left_core, left_prerelease = parse_semver(left)
    right_core, right_prerelease = parse_semver(right)
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    return compare_prerelease(left_prerelease, right_prerelease)


def evaluate_comparator(version: str, comparator: str) -> bool:
    normalized = comparator.strip()
    if not normalized:
        raise SecurityToolingWatchError("Version comparator cannot be empty")

    match = re.match(r"^(<=|>=|<|>|=|==)?\s*(.+?)\s*$", normalized)
    if match is None:
        raise SecurityToolingWatchError(f"Unsupported version comparator '{comparator}'")
    operator = match.group(1) or "="
    target = match.group(2)
    comparison = compare_versions(version, target)
    if operator in {"=", "=="}:
        return comparison == 0
    if operator == "<":
        return comparison < 0
    if operator == "<=":
        return comparison <= 0
    if operator == ">":
        return comparison > 0
    if operator == ">=":
        return comparison >= 0
    raise SecurityToolingWatchError(f"Unsupported version comparator operator '{operator}'")


def version_in_range(version: str, version_range: str) -> bool:
    normalized = version_range.strip()
    if not normalized:
        raise SecurityToolingWatchError("Version range cannot be empty")

    or_clauses = [clause.strip() for clause in normalized.split("||") if clause.strip()]
    if not or_clauses:
        raise SecurityToolingWatchError(f"Version range '{version_range}' did not contain a usable clause")

    for clause in or_clauses:
        comparators = [segment.strip() for segment in clause.split(",") if segment.strip()]
        if comparators and all(evaluate_comparator(version, comparator) for comparator in comparators):
            return True
    return False


def identifiers_from_advisory(advisory: dict[str, Any]) -> list[str]:
    identifiers = advisory.get("identifiers", [])
    if identifiers in (None, ""):
        identifiers = []
    if not isinstance(identifiers, list):
        raise SecurityToolingWatchError("GitHub advisory identifiers must be a list")

    aliases: set[str] = set()
    ghsa_id = advisory.get("ghsa_id") or advisory.get("ghsaId")
    if ghsa_id:
        aliases.add(required_scalar_field({"ghsa_id": ghsa_id}, "ghsa_id", error_context="GitHub advisory"))
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            raise SecurityToolingWatchError("GitHub advisory identifier entries must be objects")
        aliases.add(required_scalar_field(identifier, "value", error_context="GitHub advisory identifier"))
    return sorted(aliases)


def normalize_vulnerabilities(data: Any) -> list[dict[str, Any]]:
    nodes = data
    if isinstance(data, dict) and "nodes" in data:
        nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise SecurityToolingWatchError("GitHub vulnerability query result must be a list of nodes")

    normalized: list[dict[str, Any]] = []
    for entry in nodes:
        if not isinstance(entry, dict):
            raise SecurityToolingWatchError("GitHub vulnerability entries must be objects")

        if {"ghsa_id", "summary", "permalink", "vulnerable_version_range", "severity"}.issubset(entry.keys()):
            identifiers = entry.get("identifiers", [])
            if identifiers in (None, ""):
                identifiers = []
            if not isinstance(identifiers, list):
                raise SecurityToolingWatchError("Normalized GitHub vulnerability identifiers must be a list")
            normalized.append(
                {
                    "ghsa_id": required_scalar_field(entry, "ghsa_id", error_context="GitHub vulnerability"),
                    "summary": required_scalar_field(entry, "summary", error_context="GitHub vulnerability"),
                    "permalink": required_scalar_field(entry, "permalink", error_context="GitHub vulnerability"),
                    "identifiers": identifiers,
                    "vulnerable_version_range": required_scalar_field(
                        entry,
                        "vulnerable_version_range",
                        error_context="GitHub vulnerability",
                    ),
                    "first_patched_version": str(entry.get("first_patched_version", "none listed") or "none listed"),
                    "severity": required_scalar_field(entry, "severity", error_context="GitHub vulnerability"),
                }
            )
            continue

        advisory = required_object_field(entry, "advisory", error_context="GitHub vulnerability")
        vulnerable_range = required_scalar_field(
            entry,
            "vulnerable_version_range",
            error_context="GitHub vulnerability",
        ) if "vulnerable_version_range" in entry else required_scalar_field(
            entry,
            "vulnerableVersionRange",
            error_context="GitHub vulnerability",
        )
        first_patched = entry.get("first_patched_version", entry.get("firstPatchedVersion", {}))
        if first_patched in (None, ""):
            first_patched = {}
        if not isinstance(first_patched, dict):
            raise SecurityToolingWatchError(
                "GitHub vulnerability field 'first_patched_version' must be an object when present"
            )
        severity = required_scalar_field(entry, "severity", error_context="GitHub vulnerability")
        normalized.append(
            {
                "ghsa_id": required_scalar_field(
                    advisory,
                    "ghsaId",
                    error_context="GitHub advisory",
                ) if "ghsaId" in advisory else required_scalar_field(
                    advisory,
                    "ghsa_id",
                    error_context="GitHub advisory",
                ),
                "summary": required_scalar_field(advisory, "summary", error_context="GitHub advisory"),
                "permalink": required_scalar_field(advisory, "permalink", error_context="GitHub advisory"),
                "identifiers": advisory.get("identifiers", []),
                "vulnerable_version_range": vulnerable_range,
                "first_patched_version": str(first_patched.get("identifier", "none listed") or "none listed"),
                "severity": severity,
            }
        )
    return normalized


def fetch_github_security_vulnerabilities(*, ecosystem: str, package: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={GRAPHQL_QUERY}",
            "-f",
            f"ecosystem={ecosystem}",
            "-f",
            f"package={package}",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise SecurityToolingWatchError("GitHub GraphQL response root must be an object")
    data = required_object_field(payload, "data", error_context="GitHub GraphQL response")
    vulnerabilities = required_object_field(
        data,
        "securityVulnerabilities",
        error_context="GitHub GraphQL response data",
    )
    return normalize_vulnerabilities(vulnerabilities)


def evaluate_tool(tool: dict[str, Any], advisory_index: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    source_rule = tool["source_rule"]
    kind = source_rule["kind"]
    if kind == "manual-review-required":
        return {
            "tool": tool["tool"],
            "pinned_version": tool["version"],
            "outcome": "manual-review-required",
            "source_rule": source_rule,
            "affected_workflows": tool["workflows"],
            "aliases": [],
            "findings": [],
            "first_patched_version": "n/a",
            "severity": "manual",
            "rationale": source_rule["rationale"],
        }

    package = source_rule["package"]
    vulnerabilities = advisory_index.get(package)
    if vulnerabilities is None:
        raise SecurityToolingWatchError(
            f"Advisory index did not include required package '{package}'"
        )

    actionable_findings: list[dict[str, Any]] = []
    for vulnerability in normalize_vulnerabilities(vulnerabilities):
        if version_in_range(tool["version"], vulnerability["vulnerable_version_range"]):
            actionable_findings.append(vulnerability)

    actionable_findings.sort(key=lambda finding: (finding["ghsa_id"], finding["vulnerable_version_range"]))
    aliases = sorted({alias for finding in actionable_findings for alias in identifiers_from_advisory(finding)})
    if not actionable_findings:
        return {
            "tool": tool["tool"],
            "pinned_version": tool["version"],
            "outcome": "no known actionable advisory for pinned version",
            "source_rule": source_rule,
            "affected_workflows": tool["workflows"],
            "aliases": [],
            "findings": [],
            "first_patched_version": "n/a",
            "severity": "none",
            "rationale": source_rule["source"],
        }

    top = actionable_findings[0]
    return {
        "tool": tool["tool"],
        "pinned_version": tool["version"],
        "outcome": "actionable advisory affects pinned version",
        "source_rule": source_rule,
        "affected_workflows": tool["workflows"],
        "aliases": aliases,
        "findings": actionable_findings,
        "first_patched_version": top["first_patched_version"],
        "severity": top["severity"],
        "rationale": source_rule["source"],
    }


def build_summary(
    manifest: Any,
    *,
    advisory_index: dict[str, list[dict[str, Any]]],
    generated_at: str,
) -> dict[str, Any]:
    normalized_manifest = normalize_manifest(manifest)
    results = [evaluate_tool(tool, advisory_index) for tool in normalized_manifest["tools"]]
    actionable_results = [result for result in results if result["outcome"] == "actionable advisory affects pinned version"]
    manual_results = [result for result in results if result["outcome"] == "manual-review-required"]

    return {
        "alert": bool(actionable_results),
        "advisory_count": sum(len(result["findings"]) for result in actionable_results),
        "manual_review_count": len(manual_results),
        "generated_at": generated_at,
        "issue_title": normalized_manifest["issue_title"],
        "scope": normalized_manifest["scope"],
        "results": results,
        "tool_count": len(results),
    }


def sanitize_cell(value: Any) -> str:
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(summary: dict[str, Any], run_url: str) -> str:
    lines = [
        REPORT_MARKER,
        f"# {summary['issue_title']}",
        "",
        "This issue/report is maintained automatically by the scheduled CVE watch workflow.",
        "",
        "## Scope",
        f"- Automated scope today: {summary['scope']}",
        "- The checked-in inventory lives at `.github/security-tooling-watch.json`.",
        "- Rust CLI tooling uses GitHub security advisory data keyed by the pinned crates.io package name and compares the pinned version against each advisory's vulnerable range.",
        "- `gitleaks` remains explicit `manual-review-required` until the repo adopts a trustworthy machine-readable advisory source for that downloaded release-tarball path.",
        "- Runner-image / host-toolchain CVEs remain out of scope for this slice and stay tracked separately.",
        f"- Generated at: `{summary['generated_at']}`",
    ]
    if run_url:
        lines.append(f"- Source run: {run_url}")

    lines.extend(
        [
            "",
            "## Tool outcomes",
            "| Tool | Pinned version | Source rule | Outcome | Workflow locations |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for result in summary["results"]:
        source_rule = result["source_rule"]
        if source_rule["kind"] == "manual-review-required":
            source_text = "manual-review-required"
        else:
            source_text = f"{source_rule['source']} ({source_rule['ecosystem']}::{source_rule['package']})"
        lines.append(
            "| "
            + " | ".join(
                [
                    sanitize_cell(result["tool"]),
                    sanitize_cell(result["pinned_version"]),
                    sanitize_cell(source_text),
                    sanitize_cell(result["outcome"]),
                    sanitize_cell(", ".join(result["affected_workflows"])),
                ]
            )
            + " |"
        )

    if summary["alert"]:
        lines.extend(
            [
                "",
                "## Actionable findings",
                f"- Actionable advisory count: **{summary['advisory_count']}**",
                f"- Tools affected: **{', '.join(sorted({result['tool'] for result in summary['results'] if result['outcome'] == 'actionable advisory affects pinned version'}))}**",
            ]
        )
        for result in summary["results"]:
            if result["outcome"] != "actionable advisory affects pinned version":
                continue
            lines.extend(
                [
                    "",
                    f"### {result['tool']}",
                    f"- Pinned version: `{result['pinned_version']}`",
                    f"- Consumed by: {', '.join(result['affected_workflows'])}",
                ]
            )
            for finding in result["findings"]:
                lines.extend(
                    [
                        f"- Advisory: [{finding['ghsa_id']}]({finding['permalink']}) ({', '.join(identifiers_from_advisory(finding))})",
                        f"- Severity: {finding['severity']}",
                        f"- Vulnerable range: `{finding['vulnerable_version_range']}`",
                        f"- First patched version: `{finding['first_patched_version']}`",
                        f"- Summary: {finding['summary']}",
                    ]
                )
    else:
        lines.extend(
            [
                "",
                "## Status",
                "- No watched tool currently has a known actionable advisory affecting the pinned version.",
                "- Clean runs still render manual-review-required surfaces in the workflow summary so the remaining gap stays explicit.",
            ]
        )

    if summary["manual_review_count"]:
        lines.extend(["", "## Manual-review-required surfaces"])
        for result in summary["results"]:
            if result["outcome"] != "manual-review-required":
                continue
            lines.extend(
                [
                    f"- `{result['tool']}` `{result['pinned_version']}` — {result['rationale']}",
                    f"  - Consumed by: {', '.join(result['affected_workflows'])}",
                ]
            )

    return "\n".join(lines) + "\n"


def fetch_advisory_index(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    advisory_index: dict[str, list[dict[str, Any]]] = {}
    for tool in manifest["tools"]:
        source_rule = tool["source_rule"]
        if source_rule["kind"] != "github-security-vulnerabilities":
            continue
        package = source_rule["package"]
        if package in advisory_index:
            continue
        advisory_index[package] = fetch_github_security_vulnerabilities(
            ecosystem=source_rule["ecosystem"],
            package=package,
        )
    return advisory_index


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    args = parse_args()
    generated_at = args.generated_at or utc_now_iso()

    try:
        manifest = normalize_manifest(load_json(args.manifest))
        advisory_index = fetch_advisory_index(manifest)
        summary = build_summary(manifest, advisory_index=advisory_index, generated_at=generated_at)
        markdown = render_markdown(summary, run_url=args.run_url)
        write_json(args.summary_out, summary)
        write_text(args.markdown_out, markdown)
    except (
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        SecurityToolingWatchError,
    ) as exc:
        print(f"security_tooling_cve_watch: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
