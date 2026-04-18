from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "cve_watch_issue_sync.py"
SPEC = importlib.util.spec_from_file_location("cve_watch_issue_sync", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CveWatchIssueSyncTests(unittest.TestCase):
    def test_build_sync_plan_creates_issue_when_alert_active_without_existing_issue(self) -> None:
        summary = {
            "alert": True,
            "advisory_count": 2,
            "issue_title": "security: dependency CVE watch findings",
        }

        plan = MODULE.build_sync_plan(
            summary=summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=[],
            run_url="https://example.test/runs/101",
        )

        self.assertEqual(plan["action"], "create")
        self.assertEqual(plan["title"], "security: dependency CVE watch findings")
        self.assertEqual(plan["labels"], ["devops", "security-review-needed"])

    def test_build_sync_plan_updates_existing_open_managed_issue(self) -> None:
        summary = {
            "alert": True,
            "advisory_count": 1,
            "issue_title": "security: dependency CVE watch findings",
        }

        plan = MODULE.build_sync_plan(
            summary=summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=[
                {
                    "number": 42,
                    "title": "security: dependency CVE watch findings",
                    "body": f"{MODULE.REPORT_MARKER}\nold body\n",
                    "state": "OPEN",
                }
            ],
            run_url="https://example.test/runs/102",
        )

        self.assertEqual(plan["action"], "update")
        self.assertEqual(plan["number"], 42)
        self.assertEqual(plan["labels"], ["devops", "security-review-needed"])

    def test_build_sync_plan_reopens_existing_closed_managed_issue_on_recurrence(self) -> None:
        summary = {
            "alert": True,
            "advisory_count": 1,
            "issue_title": "security: dependency CVE watch findings",
        }

        plan = MODULE.build_sync_plan(
            summary=summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=[
                {
                    "number": 7,
                    "title": "security: dependency CVE watch findings",
                    "body": f"{MODULE.REPORT_MARKER}\nclosed body\n",
                    "state": "CLOSED",
                }
            ],
            run_url="https://example.test/runs/103",
        )

        self.assertEqual(plan["action"], "reopen")
        self.assertEqual(plan["number"], 7)
        self.assertEqual(plan["labels"], ["devops", "security-review-needed"])

    def test_build_sync_plan_closes_existing_open_issue_when_clean(self) -> None:
        summary = {
            "alert": False,
            "advisory_count": 0,
            "issue_title": "security: dependency CVE watch findings",
        }

        plan = MODULE.build_sync_plan(
            summary=summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=[
                {
                    "number": 18,
                    "title": "security: dependency CVE watch findings",
                    "body": f"{MODULE.REPORT_MARKER}\nold body\n",
                    "state": "OPEN",
                }
            ],
            run_url="https://example.test/runs/104",
        )

        self.assertEqual(plan["action"], "close")
        self.assertEqual(plan["number"], 18)
        self.assertIn("Latest clean run: https://example.test/runs/104", plan["comment"])
        self.assertIn("Advisory count: 0", plan["comment"])

    def test_build_sync_plan_ignores_plain_title_issue_without_report_marker(self) -> None:
        alert_summary = {
            "alert": True,
            "advisory_count": 1,
            "issue_title": "security: dependency CVE watch findings",
        }
        clean_summary = {
            "alert": False,
            "advisory_count": 0,
            "issue_title": "security: dependency CVE watch findings",
        }
        existing_issues = [
            {
                "number": 99,
                "title": "security: dependency CVE watch findings",
                "body": "human-created issue without the managed marker",
                "state": "OPEN",
            }
        ]

        alert_plan = MODULE.build_sync_plan(
            summary=alert_summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=existing_issues,
            run_url="https://example.test/runs/105",
        )
        clean_plan = MODULE.build_sync_plan(
            summary=clean_summary,
            markdown=f"{MODULE.REPORT_MARKER}\n# security: dependency CVE watch findings\n",
            existing_issues=existing_issues,
            run_url="https://example.test/runs/106",
        )

        self.assertEqual(alert_plan["action"], "create")
        self.assertEqual(clean_plan["action"], "noop")

    def test_select_managed_issue_prefers_report_marker_over_plain_title_match(self) -> None:
        issue = MODULE.select_managed_issue(
            [
                {
                    "number": 5,
                    "title": "security: dependency CVE watch findings",
                    "body": "human-created note without marker",
                    "state": "OPEN",
                },
                {
                    "number": 6,
                    "title": "security: dependency CVE watch findings",
                    "body": f"{MODULE.REPORT_MARKER}\nautomated body\n",
                    "state": "CLOSED",
                },
            ],
            expected_title="security: dependency CVE watch findings",
        )

        self.assertIsNotNone(issue)
        self.assertEqual(issue["number"], 6)


if __name__ == "__main__":
    unittest.main()
