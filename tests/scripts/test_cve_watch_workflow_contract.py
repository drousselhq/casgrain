from __future__ import annotations

from pathlib import Path
import unittest

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "cve-watch.yml"


class CveWatchWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.workflow_text)

    def test_workflow_no_longer_writes_github_issues(self) -> None:
        self.assertNotIn("issues: write", self.workflow_text)
        self.assertNotIn("cve_watch_issue_sync.py", self.workflow_text)
        self.assertNotIn("Synchronize managed", self.workflow_text)

    def test_cve_finding_slices_fail_the_scheduled_run_after_rendering_summary(self) -> None:
        jobs = self.workflow["jobs"]
        expected_jobs = [
            "dependency-cve-watch",
            "non-cargo-dependabot-watch",
            "security-tooling-watch",
        ]
        for job_name in expected_jobs:
            with self.subTest(job=job_name):
                steps = jobs[job_name]["steps"]
                step_names = [step["name"] for step in steps]
                self.assertTrue(
                    any(name.startswith("Add ") and "workflow summary" in name for name in step_names),
                    step_names,
                )
                gate_steps = [step for step in steps if "cve_watch_alert_gate.py" in step.get("run", "")]
                self.assertEqual(len(gate_steps), 1, step_names)

    def test_runner_host_watch_is_report_only(self) -> None:
        steps = self.workflow["jobs"]["runner-host-watch"]["steps"]
        self.assertTrue(any(step["name"] == "Add runner-host report to workflow summary" for step in steps))
        self.assertFalse(any("cve_watch_alert_gate.py" in step.get("run", "") for step in steps))


if __name__ == "__main__":
    unittest.main()
