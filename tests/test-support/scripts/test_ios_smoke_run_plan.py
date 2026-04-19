import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("ios_smoke_run_plan.py")
spec = importlib.util.spec_from_file_location("ios_smoke_run_plan", MODULE_PATH)
ios_smoke_run_plan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ios_smoke_run_plan)


class HostEnvironmentNormalizationTests(unittest.TestCase):
    def test_load_ios_workflow_config_reads_runner_label_from_workflow_yaml(self) -> None:
        workflow = """jobs:
  smoke:
    runs-on: macos-15-xlarge
    steps:
      - name: Checkout
        uses: actions/checkout@v4
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "ios-simulator-smoke.yml"
            workflow_path.write_text(workflow, encoding="utf-8")
            config = ios_smoke_run_plan.load_ios_workflow_config(workflow_path)

        self.assertEqual(config, {"runner_label": "macos-15-xlarge"})

    def test_build_ios_host_environment_uses_workflow_runner_label(self) -> None:
        simulator_info = {
            "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-26-2",
            "runtime_name": "iOS 26.2",
            "device_name": "iPhone 16",
        }

        outputs = {
            ("xcode-select", "-p"): "/Applications/Xcode_16.4.app/Contents/Developer\n",
            ("xcodebuild", "-version"): "Xcode 16.4\nBuild version 16F6\n",
            ("xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"): "18.5\n",
            ("sw_vers", "-productVersion"): "15.7.4\n",
            ("sw_vers", "-buildVersion"): "24G517\n",
            ("uname", "-m"): "arm64\n",
        }

        with patch.dict(
            ios_smoke_run_plan.os.environ,
            {
                "ImageOS": "macos15",
                "ImageVersion": "20260414.0270.1",
                "GITHUB_REPOSITORY": "drousselhq/casgrain",
                "GITHUB_WORKFLOW": "ios-simulator-smoke",
                "GITHUB_RUN_ID": "24624581772",
                "GITHUB_RUN_ATTEMPT": "1",
            },
            clear=False,
        ), patch.object(
            ios_smoke_run_plan,
            "load_ios_workflow_config",
            return_value={"runner_label": "macos-15-xlarge"},
        ), patch.object(
            ios_smoke_run_plan,
            "command_output",
            side_effect=lambda *args: outputs[args],
        ), patch.object(
            ios_smoke_run_plan,
            "utc_now",
            return_value="2026-04-19T09:00:00Z",
        ):
            host_environment = ios_smoke_run_plan.build_ios_host_environment(simulator_info)

        self.assertEqual(host_environment["generated_at"], "2026-04-19T09:00:00Z")
        self.assertEqual(host_environment["workflow_run"]["run_url"], "https://github.com/drousselhq/casgrain/actions/runs/24624581772")
        self.assertEqual(host_environment["runner"]["label"], "macos-15-xlarge")
        self.assertEqual(host_environment["runner"]["image_name"], "macos-15-arm64")
        self.assertEqual(host_environment["runner"]["image_version"], "20260414.0270.1")
        self.assertEqual(host_environment["runner"]["os_version"], "15.7.4")
        ios_smoke_run_plan.validate_ios_host_environment(host_environment)

    def test_validate_ios_host_environment_rejects_missing_metadata(self) -> None:
        with self.assertRaises(SystemExit) as error:
            ios_smoke_run_plan.validate_ios_host_environment(
                {
                    "runner": {
                        "label": "macos-15",
                        "image_name": "macos-15-arm64",
                        "image_version": "20260414.0270.1",
                        "os_version": "15.7.4",
                        "os_build": "24G517",
                    },
                    "xcode": {
                        "app_path": "/Applications/Xcode_16.4.app",
                        "version": "16.4",
                        "simulator_sdk_version": "18.5",
                    },
                    "simulator": {
                        "runtime_identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-2",
                        "runtime_name": "iOS 26.2",
                        "device_name": "iPhone 16",
                    },
                }
            )

        self.assertIn("generated_at", str(error.exception))

    def test_validate_ios_host_environment_rejects_missing_runner_os_name(self) -> None:
        host_environment = {
            "generated_at": "2026-04-19T09:00:00Z",
            "workflow_run": {
                "repository": "drousselhq/casgrain",
                "workflow": "ios-simulator-smoke",
                "run_id": "24624581772",
                "run_attempt": "1",
                "run_url": "https://github.com/drousselhq/casgrain/actions/runs/24624581772",
            },
            "runner": {
                "label": "macos-15",
                "image_name": "macos-15-arm64",
                "image_version": "20260414.0270.1",
                "os_name": "macOS",
                "os_version": "15.7.4",
                "os_build": "24G517",
            },
            "xcode": {
                "app_path": "/Applications/Xcode_16.4.app",
                "version": "16.4",
                "simulator_sdk_version": "18.5",
            },
            "simulator": {
                "runtime_identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-2",
                "runtime_name": "iOS 26.2",
                "device_name": "iPhone 16",
            },
        }
        host_environment["runner"].pop("os_name")

        with self.assertRaises(SystemExit) as error:
            ios_smoke_run_plan.validate_ios_host_environment(host_environment)

        self.assertIn("runner.os_name", str(error.exception))


if __name__ == "__main__":
    unittest.main()
