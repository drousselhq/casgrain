from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "security_tooling_cve_watch.py"
SPEC = importlib.util.spec_from_file_location("security_tooling_cve_watch", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SecurityToolingCveWatchTests(unittest.TestCase):
    def sample_manifest(self) -> dict[str, object]:
        return {
            "report_title": "security: security-tooling CVE watch findings",
            "scope": "Workflow-installed security tooling outside Cargo.lock / Dependabot coverage",
            "tools": [
                {
                    "tool": "gitleaks",
                    "version": "8.30.1",
                    "workflows": [
                        ".github/workflows/security.yml:16",
                        ".github/workflows/security.yml:31",
                    ],
                    "source_rule": {
                        "kind": "manual-review-required",
                        "rationale": "No trustworthy machine-readable advisory feed is wired for downloaded release tarballs yet.",
                    },
                },
                {
                    "tool": "cargo-audit",
                    "version": "0.22.1",
                    "workflows": [
                        ".github/workflows/security.yml:54",
                        ".github/workflows/cve-watch.yml:34",
                    ],
                    "source_rule": {
                        "kind": "github-security-vulnerabilities",
                        "ecosystem": "RUST",
                        "package": "cargo-audit",
                        "source": "GitHub securityVulnerabilities GraphQL",
                    },
                },
                {
                    "tool": "cargo-deny",
                    "version": "0.18.3",
                    "workflows": [
                        ".github/workflows/security.yml:73",
                    ],
                    "source_rule": {
                        "kind": "github-security-vulnerabilities",
                        "ecosystem": "RUST",
                        "package": "cargo-deny",
                        "source": "GitHub securityVulnerabilities GraphQL",
                    },
                },
            ],
        }

    def test_build_summary_reports_manual_and_clean_outcomes_without_alert(self) -> None:
        summary = MODULE.build_summary(
            self.sample_manifest(),
            advisory_index={
                "cargo-audit": [],
                "cargo-deny": [],
            },
            generated_at="2026-04-18T21:45:00+00:00",
        )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        self.assertEqual(summary["manual_review_count"], 1)
        self.assertEqual(
            [result["outcome"] for result in summary["results"]],
            [
                "manual-review-required",
                "no known actionable advisory for pinned version",
                "no known actionable advisory for pinned version",
            ],
        )

        markdown = MODULE.render_markdown(summary, run_url="https://example.test/runs/75")
        self.assertIn("manual-review-required", markdown)
        self.assertIn("gitleaks", markdown)
        self.assertIn("cargo-audit", markdown)
        self.assertIn("Source run: https://example.test/runs/75", markdown)

    def test_build_summary_marks_actionable_when_pinned_version_matches_vulnerability_range(self) -> None:
        summary = MODULE.build_summary(
            self.sample_manifest(),
            advisory_index={
                "cargo-audit": [
                    {
                        "ghsa_id": "GHSA-test-1234",
                        "summary": "cargo-audit vulnerable before 0.22.2",
                        "severity": "HIGH",
                        "permalink": "https://github.com/advisories/GHSA-test-1234",
                        "identifiers": [
                            {"type": "GHSA", "value": "GHSA-test-1234"},
                            {"type": "CVE", "value": "CVE-2026-1234"},
                        ],
                        "vulnerable_version_range": ">= 0.22.0, < 0.22.2",
                        "first_patched_version": "0.22.2",
                    }
                ],
                "cargo-deny": [],
            },
            generated_at="2026-04-18T21:45:00+00:00",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 1)
        cargo_audit = next(result for result in summary["results"] if result["tool"] == "cargo-audit")
        self.assertEqual(cargo_audit["outcome"], "actionable advisory affects pinned version")
        self.assertEqual(cargo_audit["aliases"], ["CVE-2026-1234", "GHSA-test-1234"])
        self.assertEqual(cargo_audit["first_patched_version"], "0.22.2")
        self.assertEqual(cargo_audit["affected_workflows"], [
            ".github/workflows/security.yml:54",
            ".github/workflows/cve-watch.yml:34",
        ])

        markdown = MODULE.render_markdown(summary, run_url="")
        self.assertIn("GHSA-test-1234", markdown)
        self.assertIn("CVE-2026-1234", markdown)
        self.assertIn("0.22.1", markdown)
        self.assertIn("0.22.2", markdown)

    def test_range_match_handles_exact_and_disjoint_versions(self) -> None:
        self.assertTrue(MODULE.version_in_range("0.18.3", ">= 0.18.0, < 0.18.4"))
        self.assertTrue(MODULE.version_in_range("1.2.3", "= 1.2.3"))
        self.assertFalse(MODULE.version_in_range("0.18.3", ">= 0.18.4"))
        self.assertFalse(MODULE.version_in_range("0.18.3", "< 0.18.0 || >= 1.0.0"))

    def test_build_summary_fails_closed_on_missing_manifest_tool_version(self) -> None:
        manifest = self.sample_manifest()
        manifest["tools"][1] = {
            "tool": "cargo-audit",
            "workflows": [".github/workflows/security.yml:54"],
            "source_rule": {
                "kind": "github-security-vulnerabilities",
                "ecosystem": "RUST",
                "package": "cargo-audit",
                "source": "GitHub securityVulnerabilities GraphQL",
            },
        }

        with self.assertRaises(MODULE.SecurityToolingWatchError):
            MODULE.build_summary(
                manifest,
                advisory_index={"cargo-audit": [], "cargo-deny": []},
                generated_at="2026-04-18T21:45:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
