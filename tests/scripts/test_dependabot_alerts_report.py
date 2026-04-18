from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "dependabot_alerts_report.py"
SPEC = importlib.util.spec_from_file_location("dependabot_alerts_report", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def make_alert(
    *,
    number: int,
    ecosystem: str,
    package: str,
    manifest_path: str,
    summary: str = "Security advisory summary",
    first_patched_version: str = "1.2.3",
    aliases: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "number": number,
        "html_url": f"https://github.com/drousselhq/casgrain/security/dependabot/{number}",
        "dependency": {
            "manifest_path": manifest_path,
            "package": {
                "ecosystem": ecosystem,
                "name": package,
            },
        },
        "security_advisory": {
            "ghsa_id": f"GHSA-test-{number}",
            "cve_id": f"CVE-2026-{number:04d}",
            "summary": summary,
            "references": [{"url": f"https://github.com/advisories/GHSA-test-{number}"}],
            "identifiers": aliases if aliases is not None else [{"type": "GHSA", "value": f"GHSA-test-{number}"}],
        },
        "security_vulnerability": {
            "severity": "high",
            "vulnerable_version_range": "< 1.2.3",
            "first_patched_version": {"identifier": first_patched_version},
        },
    }


class DependabotAlertsReportTests(unittest.TestCase):
    def test_build_summary_ignores_unwatched_cargo_alerts(self) -> None:
        summary = MODULE.build_summary(
            [
                make_alert(
                    number=11,
                    ecosystem="cargo",
                    package="serde",
                    manifest_path="Cargo.lock",
                )
            ],
            "2026-04-18T20:00:00+00:00",
        )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        self.assertEqual(summary["findings"], [])

    def test_build_summary_keeps_watched_actions_and_maven_alerts(self) -> None:
        summary = MODULE.build_summary(
            [
                make_alert(
                    number=21,
                    ecosystem="github_actions",
                    package="actions/checkout",
                    manifest_path=".github/workflows/cve-watch.yml",
                ),
                make_alert(
                    number=22,
                    ecosystem="maven",
                    package="com.android.application",
                    manifest_path="tests/test-support/fixtures/android-smoke/app/build.gradle.kts",
                ),
                make_alert(
                    number=23,
                    ecosystem="cargo",
                    package="serde",
                    manifest_path="Cargo.lock",
                ),
            ],
            "2026-04-18T20:00:00+00:00",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_count"], 2)
        self.assertEqual(summary["package_count"], 2)
        self.assertEqual(summary["surfaces"], ["GitHub Actions", "Gradle-managed dependencies"])
        self.assertEqual(
            [finding["package"] for finding in summary["findings"]],
            ["actions/checkout", "com.android.application"],
        )

    def test_render_markdown_mentions_separate_cargo_watch(self) -> None:
        summary = MODULE.build_summary(
            [
                make_alert(
                    number=31,
                    ecosystem="actions",
                    package="actions/cache",
                    manifest_path=".github/workflows/security.yml",
                )
            ],
            "2026-04-18T20:00:00+00:00",
        )

        markdown = MODULE.render_markdown(summary, "https://example.test/runs/31")

        self.assertIn("Rust crate advisories remain covered by the separate `cargo audit` watch", markdown)
        self.assertIn("GitHub Actions", markdown)
        self.assertIn("#31", markdown)

    def test_build_summary_accepts_paginated_slurp_shape(self) -> None:
        summary = MODULE.build_summary(
            [
                [
                    make_alert(
                        number=41,
                        ecosystem="github-actions",
                        package="actions/upload-artifact",
                        manifest_path=".github/workflows/rust-ci.yml",
                    )
                ]
            ],
            "2026-04-18T20:00:00+00:00",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["alert_numbers"], ["41"])

    def test_build_summary_fails_closed_on_missing_dependency_package_ecosystem(self) -> None:
        with self.assertRaises(MODULE.DependabotReportError):
            MODULE.build_summary(
                [
                    {
                        "number": 51,
                        "dependency": {
                            "package": {
                                "name": "actions/checkout",
                            }
                        },
                        "security_advisory": {"summary": "Broken"},
                        "security_vulnerability": {"severity": "high"},
                    }
                ],
                "2026-04-18T20:00:00+00:00",
            )

    def test_build_summary_fails_closed_on_missing_summary_for_watched_alert(self) -> None:
        alert = make_alert(
            number=61,
            ecosystem="maven",
            package="com.android.application",
            manifest_path="tests/test-support/fixtures/android-smoke/app/build.gradle.kts",
        )
        del alert["security_advisory"]["summary"]

        with self.assertRaises(MODULE.DependabotReportError):
            MODULE.build_summary([alert], "2026-04-18T20:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
