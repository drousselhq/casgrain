import argparse
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("validate_android_smoke_artifacts.py")
spec = importlib.util.spec_from_file_location("validate_android_smoke_artifacts", MODULE_PATH)
validate_android_smoke_artifacts = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validate_android_smoke_artifacts)


class ValidateFailureContractTests(unittest.TestCase):
    def test_validate_failure_contract_surfaces_machine_readable_failure_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            (artifact_dir / "foreground-window.txt").write_text("launcher")
            (artifact_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "reason": "fixture app did not reach the foreground after launch",
                        "failure_class": "app-foreground-failure",
                        "artifacts": {
                            "foreground_window": "foreground-window.txt",
                            "foreground_activity": None,
                            "last_ui_dump": None,
                        },
                    }
                )
            )

            contract = validate_android_smoke_artifacts.validate_failure_contract(artifact_dir)

        self.assertEqual(contract["failure_class"], "app-foreground-failure")
        self.assertEqual(contract["status"], "failed")

    def test_validate_failure_contract_allows_boot_readiness_without_preserved_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            (artifact_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "reason": "Android emulator did not finish booting before the smoke run started",
                        "failure_class": "boot-readiness-failure",
                        "artifacts": {
                            "foreground_window": None,
                            "foreground_activity": None,
                            "last_ui_dump": None,
                        },
                    }
                )
            )

            contract = validate_android_smoke_artifacts.validate_failure_contract(artifact_dir)

        self.assertEqual(contract["failure_class"], "boot-readiness-failure")
        self.assertEqual(contract["present_diagnostics"], [])

    def test_validate_failure_contract_rejects_unknown_failure_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            (artifact_dir / "foreground-window.txt").write_text("launcher")
            (artifact_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "reason": "fixture app did not reach the foreground after launch",
                        "failure_class": "typo-foreground-failure",
                        "artifacts": {
                            "foreground_window": "foreground-window.txt",
                            "foreground_activity": None,
                            "last_ui_dump": None,
                        },
                    }
                )
            )

            with self.assertRaises(SystemExit) as error:
                validate_android_smoke_artifacts.validate_failure_contract(artifact_dir)

        self.assertIn("unknown failure_class", str(error.exception))


class MainContractBreachTests(unittest.TestCase):
    def test_main_writes_artifact_contract_breach_summary_when_bundle_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            stdout = StringIO()
            with patch.object(
                validate_android_smoke_artifacts,
                "parse_args",
                return_value=argparse.Namespace(artifact_dir=str(artifact_dir)),
            ), redirect_stdout(stdout):
                exit_code = validate_android_smoke_artifacts.main()

            summary = json.loads((artifact_dir / "evidence-summary.json").read_text())

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["contract"]["failure_class"], "artifact-contract-breach")
        self.assertIn("must contain either trace.json or failure.json", summary["contract"]["reason"])

    def test_main_writes_artifact_contract_breach_summary_when_artifact_dir_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "missing-artifacts"
            stdout = StringIO()
            with patch.object(
                validate_android_smoke_artifacts,
                "parse_args",
                return_value=argparse.Namespace(artifact_dir=str(artifact_dir)),
            ), redirect_stdout(stdout):
                exit_code = validate_android_smoke_artifacts.main()

            summary = json.loads((artifact_dir / "evidence-summary.json").read_text())

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["contract"]["failure_class"], "artifact-contract-breach")
        self.assertIn("artifact directory does not exist", summary["contract"]["reason"])

    def test_main_writes_contract_breach_summary_when_artifact_dir_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "artifacts-file"
            artifact_path.write_text("not a directory")
            fallback_dir = artifact_path.parent / f"{artifact_path.name}-artifacts"
            stdout = StringIO()
            with patch.object(
                validate_android_smoke_artifacts,
                "parse_args",
                return_value=argparse.Namespace(artifact_dir=str(artifact_path)),
            ), redirect_stdout(stdout):
                exit_code = validate_android_smoke_artifacts.main()

            summary = json.loads((fallback_dir / "evidence-summary.json").read_text())

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["contract"]["failure_class"], "artifact-contract-breach")
        self.assertEqual(summary["requested_artifact_dir"], str(artifact_path.resolve()))
        self.assertEqual(summary["artifact_dir"], str(fallback_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
