import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("ios_smoke_run_plan.py")
spec = importlib.util.spec_from_file_location("ios_smoke_run_plan", MODULE_PATH)
ios_smoke_run_plan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ios_smoke_run_plan)


class HostEnvironmentNormalizationTests(unittest.TestCase):
    def test_build_ios_host_environment_normalizes_runner_image_family(self) -> None:
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
            {"ImageOS": "macos15", "ImageVersion": "20260414.0270.1"},
            clear=False,
        ), patch.object(
            ios_smoke_run_plan,
            "command_output",
            side_effect=lambda *args: outputs[args],
        ):
            host_environment = ios_smoke_run_plan.build_ios_host_environment(simulator_info)

        self.assertEqual(host_environment["runner"]["image_name"], "macos-15-arm64")
        self.assertEqual(host_environment["runner"]["image_version"], "20260414.0270.1")
        self.assertEqual(host_environment["runner"]["os_version"], "15.7.4")


if __name__ == "__main__":
    unittest.main()
