from __future__ import annotations

import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ANDROID_SMOKE_PATHS = [
    "Cargo.toml",
    "Cargo.lock",
    "crates/application/**",
    "crates/casgrain/**",
    "crates/compiler/**",
    "crates/domain/**",
    "crates/runner/**",
    "crates/android/**",
    "tests/test-support/fixtures/android-smoke/**",
    "tests/test-support/fixtures/android-smoke/reliability-issue-sync/**",
    "tests/test-support/scripts/android_smoke_run_plan.py",
    "tests/test-support/scripts/android_smoke_reliability_window.py",
    "tests/test-support/scripts/android_smoke_issue_sync.py",
    "tests/test-support/scripts/validate_android_smoke_artifacts.py",
    "tests/scripts/test_android_smoke_reliability_window.py",
    "tests/scripts/test_android_smoke_issue_sync.py",
    ".github/workflows/android-emulator-smoke.yml",
    ".github/runner-host-watch.json",
]
IOS_SMOKE_PATHS = [
    "Cargo.toml",
    "Cargo.lock",
    "crates/application/**",
    "crates/casgrain/**",
    "crates/compiler/**",
    "crates/domain/**",
    "crates/runner/**",
    "crates/ios/**",
    "tests/test-support/fixtures/ios-smoke/**",
    "tests/test-support/scripts/ios_smoke.sh",
    "tests/test-support/scripts/ios_smoke_run_plan.py",
    ".github/workflows/ios-simulator-smoke.yml",
    ".github/runner-host-watch.json",
]


class MobileSmokeWorkflowTriggerTests(unittest.TestCase):
    def load_workflow(self, relative_path: str) -> dict:
        workflow = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        if not isinstance(workflow, dict):
            self.fail(f"workflow {relative_path} did not parse to a mapping")
        return workflow

    def workflow_on_block(self, workflow: dict) -> dict:
        on_block = workflow.get("on", workflow.get(True))
        self.assertIsInstance(on_block, dict)
        return on_block

    def job_steps(self, workflow: dict, job_name: str) -> list[dict]:
        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        job = jobs.get(job_name)
        self.assertIsInstance(job, dict)
        steps = job.get("steps")
        self.assertIsInstance(steps, list)
        return steps

    def step_named(self, steps: list[dict], name: str) -> dict:
        for step in steps:
            if step.get("name") == name:
                return step
        self.fail(f"missing workflow step {name!r}")

    def test_android_smoke_push_trigger_bootstraps_main_runner_host_evidence(self) -> None:
        workflow = self.load_workflow(".github/workflows/android-emulator-smoke.yml")
        push = self.workflow_on_block(workflow).get("push")
        self.assertIsInstance(push, dict)
        self.assertEqual(push.get("branches"), ["main"])
        self.assertEqual(
            push.get("paths"),
            ANDROID_SMOKE_PATHS,
        )

    def test_android_smoke_pull_request_trigger_always_reports_status_context(self) -> None:
        workflow = self.load_workflow(".github/workflows/android-emulator-smoke.yml")
        pull_request = self.workflow_on_block(workflow).get("pull_request")
        self.assertIn(pull_request, ({}, None))

    def test_android_smoke_change_detection_step_tracks_android_surface_paths(self) -> None:
        workflow = self.load_workflow(".github/workflows/android-emulator-smoke.yml")
        steps = self.job_steps(workflow, "smoke")
        change_step = self.step_named(steps, "Decide whether Android smoke is required")
        self.assertEqual(change_step.get("id"), "changes")
        self.assertEqual(
            change_step.get("env"),
            {
                "EVENT_NAME": "${{ github.event_name }}",
                "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
                "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
            },
        )
        run_script = change_step.get("run")
        self.assertIsInstance(run_script, str)
        for pattern in ANDROID_SMOKE_PATHS:
            if pattern == ".github/runner-host-watch.json":
                continue
            self.assertIn(pattern, run_script)

    def test_ios_smoke_push_trigger_bootstraps_main_runner_host_evidence(self) -> None:
        workflow = self.load_workflow(".github/workflows/ios-simulator-smoke.yml")
        push = self.workflow_on_block(workflow).get("push")
        self.assertIsInstance(push, dict)
        self.assertEqual(push.get("branches"), ["main"])
        self.assertEqual(
            push.get("paths"),
            IOS_SMOKE_PATHS,
        )


if __name__ == "__main__":
    unittest.main()
