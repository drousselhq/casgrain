from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tests" / "test-support" / "scripts" / "cve_watch_alert_gate.py"
SPEC = importlib.util.spec_from_file_location("cve_watch_alert_gate", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CveWatchAlertGateTests(unittest.TestCase):
    def write_summary(self, payload: dict[str, object]) -> str:
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        with temp:
            json.dump(payload, temp)
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return temp.name

    def run_gate(self, payload: dict[str, object]) -> tuple[int, str, str]:
        path = self.write_summary(payload)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = MODULE.main([
                "--summary-json",
                path,
                "--report-name",
                "Rust dependency CVE watch",
                "--run-url",
                "https://example.test/runs/1",
            ])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_clean_summary_passes_without_creating_backlog_work(self) -> None:
        code, stdout, stderr = self.run_gate({"alert": False, "advisory_count": 0, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 0)
        self.assertIn("no active CVE-watch findings", stdout)
        self.assertEqual(stderr, "")

    def test_active_summary_fails_job_with_workflow_error(self) -> None:
        code, stdout, stderr = self.run_gate({"alert": True, "advisory_count": 2, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 1)
        self.assertIn("::error title=Rust dependency CVE watch findings::Active findings detected (2)", stdout)
        self.assertIn("https://example.test/runs/1", stdout)
        self.assertEqual(stderr, "")

    def test_invalid_summary_fails_closed(self) -> None:
        code, stdout, stderr = self.run_gate({"advisory_count": 0, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("missing a boolean alert flag", stderr)

    def test_boolean_advisory_count_fails_closed(self) -> None:
        code, stdout, stderr = self.run_gate({"alert": True, "advisory_count": True, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("non-negative integer advisory_count", stderr)

    def test_inconsistent_clean_summary_with_advisories_fails_closed(self) -> None:
        code, stdout, stderr = self.run_gate({"alert": False, "advisory_count": 1, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("reports advisories without alert=true", stderr)

    def test_inconsistent_alert_summary_without_advisories_fails_closed(self) -> None:
        code, stdout, stderr = self.run_gate({"alert": True, "advisory_count": 0, "report_title": "security: dependency CVE watch findings"})

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("alert=true with zero advisories", stderr)


if __name__ == "__main__":
    unittest.main()
