from __future__ import annotations

import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


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

    def test_android_smoke_push_trigger_bootstraps_main_runner_host_evidence(self) -> None:
        workflow = self.load_workflow(".github/workflows/android-emulator-smoke.yml")
        push = self.workflow_on_block(workflow).get("push")
        self.assertIsInstance(push, dict)
        self.assertEqual(push.get("branches"), ["main"])
        self.assertEqual(
            push.get("paths"),
            [
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
            ],
        )

    def test_ios_smoke_push_trigger_bootstraps_main_runner_host_evidence(self) -> None:
        workflow = self.load_workflow(".github/workflows/ios-simulator-smoke.yml")
        push = self.workflow_on_block(workflow).get("push")
        self.assertIsInstance(push, dict)
        self.assertEqual(push.get("branches"), ["main"])
        self.assertEqual(
            push.get("paths"),
            [
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
            ],
        )


if __name__ == "__main__":
    unittest.main()
