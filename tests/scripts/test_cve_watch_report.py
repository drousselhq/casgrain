from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "cve_watch_report.py"
SPEC = importlib.util.spec_from_file_location("cve_watch_report", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CveWatchReportTests(unittest.TestCase):
    def test_build_summary_marks_clean_audit_without_alert(self) -> None:
        summary = MODULE.build_summary(
            {
                "database": {"last-updated": "2026-04-15T00:00:00Z", "last-commit": "abc123"},
                "lockfile": {"timestamp": "2026-04-15T00:00:00Z"},
                "vulnerabilities": {"list": []},
            },
            generated_at="2026-04-15T12:00:00+00:00",
        )

        self.assertFalse(summary["alert"])
        self.assertEqual(summary["advisory_count"], 0)
        markdown = MODULE.render_markdown(summary, run_url="")
        self.assertIn("No active Rust dependency advisories", markdown)
        self.assertIn("Automated scope today", markdown)

    def test_build_summary_renders_advisory_table_with_aliases(self) -> None:
        summary = MODULE.build_summary(
            {
                "database": {"last-updated": "2026-04-15T00:00:00Z", "last-commit": "def456"},
                "lockfile": {"timestamp": "2026-04-15T00:00:00Z"},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": {"name": "demo-crate", "version": "1.2.3"},
                            "advisory": {
                                "id": "RUSTSEC-2099-0001",
                                "title": "Demo vulnerability",
                                "aliases": ["CVE-2099-0001"],
                                "cvss": {"score": 8.8},
                                "url": "https://rustsec.org/advisories/RUSTSEC-2099-0001.html",
                            },
                            "versions": {
                                "patched": [">=1.2.4"],
                                "unaffected": ["<1.0.0"],
                            },
                        }
                    ]
                },
            },
            generated_at="2026-04-15T12:00:00+00:00",
        )

        self.assertTrue(summary["alert"])
        self.assertEqual(summary["advisory_ids"], ["RUSTSEC-2099-0001"])
        self.assertEqual(summary["aliases"], ["CVE-2099-0001"])
        markdown = MODULE.render_markdown(summary, run_url="https://example.test/run/1")
        self.assertIn("RUSTSEC-2099-0001", markdown)
        self.assertIn("CVE-2099-0001", markdown)
        self.assertIn("demo-crate", markdown)
        self.assertIn("patched: >=1.2.4", markdown)
        self.assertIn("Source run: https://example.test/run/1", markdown)

    def test_build_summary_rejects_unexpected_vulnerability_shape(self) -> None:
        with self.assertRaises(MODULE.AuditReportError):
            MODULE.build_summary(
                {"vulnerabilities": ["not-a-mapping"]},
                generated_at="2026-04-15T12:00:00+00:00",
            )

    def test_build_summary_rejects_non_mapping_metadata_and_versions(self) -> None:
        with self.assertRaises(MODULE.AuditReportError):
            MODULE.build_summary(
                {
                    "database": "bad-shape",
                    "lockfile": {},
                    "vulnerabilities": {"list": []},
                },
                generated_at="2026-04-15T12:00:00+00:00",
            )

        with self.assertRaises(MODULE.AuditReportError):
            MODULE.build_summary(
                {
                    "database": {},
                    "lockfile": {},
                    "vulnerabilities": {
                        "list": [
                            {
                                "package": {"name": "demo-crate", "version": "1.2.3"},
                                "advisory": {"id": "RUSTSEC-2099-0001"},
                                "versions": "not-a-mapping",
                            }
                        ]
                    },
                },
                generated_at="2026-04-15T12:00:00+00:00",
            )

    def test_build_summary_rejects_falsey_non_mapping_shapes(self) -> None:
        malformed_payloads = [
            {
                "database": None,
                "lockfile": {},
                "vulnerabilities": {"list": []},
            },
            {
                "database": {},
                "lockfile": None,
                "vulnerabilities": {"list": []},
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": None,
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": {"name": "demo-crate", "version": "1.2.3"},
                            "advisory": None,
                        }
                    ]
                },
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": None,
                            "advisory": {"id": "RUSTSEC-2099-0001"},
                        }
                    ]
                },
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": {"name": "demo-crate", "version": "1.2.3"},
                            "advisory": {"id": "RUSTSEC-2099-0001"},
                            "versions": None,
                        }
                    ]
                },
            },
            {
                "database": [],
                "lockfile": {},
                "vulnerabilities": {"list": []},
            },
            {
                "database": {},
                "lockfile": "",
                "vulnerabilities": {"list": []},
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": [],
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": {"name": "demo-crate", "version": "1.2.3"},
                            "advisory": "",
                        }
                    ]
                },
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": [],
                            "advisory": {"id": "RUSTSEC-2099-0001"},
                        }
                    ]
                },
            },
            {
                "database": {},
                "lockfile": {},
                "vulnerabilities": {
                    "list": [
                        {
                            "package": {"name": "demo-crate", "version": "1.2.3"},
                            "advisory": {"id": "RUSTSEC-2099-0001"},
                            "versions": "",
                        }
                    ]
                },
            },
        ]

        for payload in malformed_payloads:
            with self.subTest(payload=payload), self.assertRaises(MODULE.AuditReportError):
                MODULE.build_summary(payload, generated_at="2026-04-15T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
