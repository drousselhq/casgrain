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

    def test_validate_failure_contract_allows_ui_dump_failures_with_preserved_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            (artifact_dir / "foreground-window.txt").write_text("launcher")
            (artifact_dir / "ui-last.xml").write_text("")
            (artifact_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "reason": "failed to capture emulator UI hierarchy while waiting for selector 'tap-button': uiautomator dump returned empty XML",
                        "failure_class": "ui-dump-failure",
                        "artifacts": {
                            "foreground_window": "foreground-window.txt",
                            "foreground_activity": None,
                            "last_ui_dump": "ui-last.xml",
                        },
                    }
                )
            )

            contract = validate_android_smoke_artifacts.validate_failure_contract(artifact_dir)

        self.assertEqual(contract["failure_class"], "ui-dump-failure")
        self.assertEqual(contract["present_diagnostics"], ["foreground-window.txt", "ui-last.xml"])

    def test_validate_failure_contract_rejects_ui_dump_failure_without_last_ui_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            (artifact_dir / "foreground-window.txt").write_text("launcher")
            (artifact_dir / "failure.json").write_text(
                json.dumps(
                    {
                        "reason": "failed to capture emulator UI hierarchy while waiting for selector 'tap-button': uiautomator dump returned empty XML",
                        "failure_class": "ui-dump-failure",
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

        self.assertIn("ui-dump-failure must reference last_ui_dump", str(error.exception))

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


class SuccessContractHostEnvironmentTests(unittest.TestCase):
    def make_success_artifact_dir(self, artifact_dir: Path) -> None:
        (artifact_dir / "android-tap-counter-1.png").write_bytes(b"png")
        (artifact_dir / "ui-before-tap.xml").write_text("<hierarchy />")
        (artifact_dir / "ui-after-tap.xml").write_text("<hierarchy />")
        (artifact_dir / "plan.json").write_text(json.dumps({"plan_id": "increment-the-counter-once"}))
        (artifact_dir / "emulator.json").write_text(
            json.dumps(
                {
                    "device_name": "sdk_gphone64_x86_64",
                    "os_version": "14",
                }
            )
        )
        (artifact_dir / "host-environment.json").write_text(
            json.dumps(
                {
                    "runner": {
                        "label": "ubuntu-latest",
                        "image_name": "ubuntu-24.04",
                        "image_version": "20260413.86.1",
                        "os_version": "24.04.4",
                    },
                    "java": {
                        "configured_major": "17",
                        "resolved_version": "17.0.18+8",
                    },
                    "gradle": {
                        "configured_version": "8.7",
                        "resolved_version": "8.7",
                    },
                    "emulator": {
                        "api_level": "34",
                        "device_name": "sdk_gphone64_x86_64",
                        "os_version": "14",
                    },
                }
            )
        )
        (artifact_dir / "trace.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "run_id": "android-smoke-increment-the-counter-once",
                    "plan_id": "increment-the-counter-once",
                    "diagnostics": [],
                    "artifacts": [
                        {"artifact_id": "android-tap-counter-1"},
                        {"artifact_id": "android-smoke-emulator"},
                        {"artifact_id": "android-ui-before-tap"},
                        {"artifact_id": "android-ui-after-tap"},
                        {"artifact_id": "android-host-environment"},
                    ],
                }
            )
        )

    def test_validate_success_contract_requires_host_environment_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            self.make_success_artifact_dir(artifact_dir)
            contract = validate_android_smoke_artifacts.validate_success_contract(artifact_dir)

        self.assertEqual(contract["status"], "passed")
        self.assertEqual(contract["host_environment"]["runner"]["image_name"], "ubuntu-24.04")

    def test_validate_success_contract_rejects_missing_host_environment_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            self.make_success_artifact_dir(artifact_dir)
            (artifact_dir / "host-environment.json").unlink()

            with self.assertRaises(SystemExit) as error:
                validate_android_smoke_artifacts.validate_success_contract(artifact_dir)

        self.assertIn("host-environment.json", str(error.exception))


if __name__ == "__main__":
    unittest.main()
