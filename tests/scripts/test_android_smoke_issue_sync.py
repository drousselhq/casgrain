from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "android_smoke_issue_sync.py"
SPEC = importlib.util.spec_from_file_location("android_smoke_issue_sync", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

FIXTURE_DIR = (
    REPO_ROOT / "tests" / "test-support" / "fixtures" / "android-smoke" / "reliability-issue-sync"
)


def load_summary(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / f"{name}.summary.json").read_text(encoding="utf-8"))


def load_markdown(name: str) -> str:
    return (FIXTURE_DIR / f"{name}.markdown.md").read_text(encoding="utf-8")


class FakeIssueClient:
    def __init__(self) -> None:
        self.operations: list[tuple] = []
        self.next_created_number = 900

    def create_issue(self, *, repo: str, title: str, body: str, labels: list[str]) -> int:
        self.operations.append(("create", repo, title, body, tuple(labels)))
        number = self.next_created_number
        self.next_created_number += 1
        return number

    def edit_issue(self, *, repo: str, number: int, body: str, add_labels: list[str] | None = None) -> None:
        self.operations.append(("edit", repo, number, body, tuple(add_labels or [])))

    def reopen_issue(self, *, repo: str, number: int) -> None:
        self.operations.append(("reopen", repo, number))

    def close_issue(self, *, repo: str, number: int, reason: str) -> None:
        self.operations.append(("close", repo, number, reason))


class AndroidSmokeIssueSyncTests(unittest.TestCase):
    def test_build_sync_plan_keeps_tracker_open_without_blocker_for_schedule_shortfall(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("schedule-shortfall"),
            markdown=load_markdown("schedule-shortfall"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        self.assertEqual(plan["report_kind"], "schedule_shortfall_only")
        self.assertEqual(plan["tracker"]["current_state"], "OPEN")
        self.assertEqual(plan["tracker"]["desired_state"], "OPEN")
        self.assertEqual(plan["blocker"]["action"], "noop")
        tracker_body = MODULE.render_tracker_body(plan, blocker_issue_number=None)
        self.assertIn(MODULE.TRACKER_MARKER, tracker_body)
        self.assertIn("No blocker issue is required yet", tracker_body)
        self.assertIn("schedule_main_runs_below_threshold", tracker_body)

    def test_build_sync_plan_keeps_tracker_open_without_blocker_for_total_threshold_shortfall(self) -> None:
        summary = load_summary("schedule-shortfall")
        summary["reasons"] = ["total_runs_below_threshold"]
        summary["streak"] = {
            "successful_run_count": 2,
            "schedule_main_success_count": 1,
            "pull_request_success_count": 1,
            "run_ids": [24620000001, 24620000000],
        }

        plan = MODULE.build_sync_plan(
            summary=summary,
            markdown=load_markdown("schedule-shortfall"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        self.assertEqual(plan["report_kind"], "tracking_only")
        self.assertEqual(plan["tracker"]["desired_state"], "OPEN")
        self.assertEqual(plan["blocker"]["action"], "noop")
        tracker_body = MODULE.render_tracker_body(plan, blocker_issue_number=None)
        self.assertIn("No blocker issue is required yet", tracker_body)
        self.assertIn("total_runs_below_threshold", tracker_body)

    def test_build_sync_plan_closes_tracker_when_qualified(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("qualified"),
            markdown=load_markdown("qualified"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        self.assertEqual(plan["report_kind"], "qualified")
        self.assertEqual(plan["tracker"]["desired_state"], "CLOSED")
        self.assertEqual(plan["blocker"]["action"], "noop")
        tracker_body = MODULE.render_tracker_body(plan, blocker_issue_number=None)
        self.assertIn("Qualified window recorded", tracker_body)
        self.assertIn("300010", tracker_body)
        self.assertIn("schedule_main_success_count`, `3`", tracker_body)

    def test_build_sync_plan_creates_blocker_issue_for_concrete_blocker(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("blocker"),
            markdown=load_markdown("blocker"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        self.assertEqual(plan["report_kind"], "managed_blocker")
        self.assertEqual(plan["tracker"]["desired_state"], "OPEN")
        self.assertEqual(plan["blocker"]["action"], "create")
        self.assertEqual(
            plan["blocker"]["title"],
            "android-smoke: unblock reliability window after artifact-contract-breach",
        )
        self.assertEqual(plan["blocker"]["labels"], ["enhancement", "devops"])

    def test_select_managed_issue_ignores_plain_title_without_marker(self) -> None:
        issue = MODULE.select_managed_issue(
            issues=[
                {
                    "number": 75,
                    "title": "android-smoke: unblock reliability window after artifact-contract-breach",
                    "body": "human-created issue without the managed marker",
                    "state": "OPEN",
                },
                {
                    "number": 76,
                    "title": "android-smoke: unblock reliability window after artifact-contract-breach",
                    "body": f"{MODULE.blocker_marker('artifact-contract-breach')}\nautomated blocker\n",
                    "state": "CLOSED",
                },
            ],
            expected_title="android-smoke: unblock reliability window after artifact-contract-breach",
            marker=MODULE.blocker_marker("artifact-contract-breach"),
        )

        self.assertIsNotNone(issue)
        self.assertEqual(issue["number"], 76)

    def test_build_sync_plan_reuses_closed_managed_blocker_issue(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("blocker"),
            markdown=load_markdown("blocker"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "CLOSED"},
            existing_issues=[
                {
                    "number": 220,
                    "title": "android-smoke: unblock reliability window after artifact-contract-breach",
                    "body": f"{MODULE.blocker_marker('artifact-contract-breach')}\nold blocker\n",
                    "state": "CLOSED",
                }
            ],
        )

        self.assertEqual(plan["tracker"]["current_state"], "CLOSED")
        self.assertEqual(plan["tracker"]["desired_state"], "OPEN")
        self.assertEqual(plan["blocker"]["action"], "reopen")
        self.assertEqual(plan["blocker"]["number"], 220)

    def test_render_dry_run_reports_actions_for_blocker_case(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("blocker"),
            markdown=load_markdown("blocker"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        dry_run = MODULE.render_dry_run(plan)
        self.assertIn('"report_kind": "managed_blocker"', dry_run)
        self.assertIn('"action": "create"', dry_run)
        self.assertIn('"issue": 132', dry_run)

    def test_apply_sync_plan_reopens_tracker_and_updates_blocker_without_live_github(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("blocker"),
            markdown=load_markdown("blocker"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "CLOSED"},
            existing_issues=[],
        )

        client = FakeIssueClient()
        result = MODULE.apply_sync_plan(repo="drousselhq/casgrain", plan=plan, client=client)

        self.assertEqual(result["blocker_issue_number"], 900)
        self.assertEqual(client.operations[0][0], "create")
        self.assertEqual(client.operations[1], ("reopen", "drousselhq/casgrain", 132))
        self.assertEqual(client.operations[2][0], "edit")
        self.assertIn("#900", client.operations[2][3])

    def test_apply_sync_plan_closes_tracker_when_qualified_without_live_github(self) -> None:
        plan = MODULE.build_sync_plan(
            summary=load_summary("qualified"),
            markdown=load_markdown("qualified"),
            tracker_issue={"number": 132, "title": "Track Android smoke qualification after reliability sync lands", "body": "old", "state": "OPEN"},
            existing_issues=[],
        )

        client = FakeIssueClient()
        MODULE.apply_sync_plan(repo="drousselhq/casgrain", plan=plan, client=client)

        self.assertEqual(client.operations[0][0], "edit")
        self.assertEqual(client.operations[1], ("close", "drousselhq/casgrain", 132, "completed"))


if __name__ == "__main__":
    unittest.main()
