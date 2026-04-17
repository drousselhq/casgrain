import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("android_smoke_run_plan.py")
spec = importlib.util.spec_from_file_location("android_smoke_run_plan", MODULE_PATH)
android_smoke_run_plan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(android_smoke_run_plan)


class BootSignalsReadyTests(unittest.TestCase):
    def test_ready_when_boot_properties_and_package_manager_are_ready(self) -> None:
        self.assertTrue(
            android_smoke_run_plan.boot_signals_ready(
                "1", "1", "package:/system/framework/framework-res.apk"
            )
        )

    def test_ready_when_dev_bootcomplete_is_absent_but_primary_boot_signal_is_ready(self) -> None:
        self.assertTrue(
            android_smoke_run_plan.boot_signals_ready(
                "1", "", "package:/system/framework/framework-res.apk"
            )
        )

    def test_not_ready_when_primary_boot_signal_is_missing(self) -> None:
        self.assertFalse(
            android_smoke_run_plan.boot_signals_ready(
                "0", "1", "package:/system/framework/framework-res.apk"
            )
        )

    def test_not_ready_when_package_manager_probe_is_not_ready(self) -> None:
        self.assertFalse(
            android_smoke_run_plan.boot_signals_ready("1", "1", "Error: Can't find service: package")
        )


class WaitForBootCompletionTests(unittest.TestCase):
    def test_retries_until_package_manager_probe_succeeds(self) -> None:
        probe_results = iter(
            [
                (True, "1"),
                (True, "1"),
                (False, "Error: Can't find service: package"),
                (True, "1"),
                (True, "1"),
                (True, "package:android"),
            ]
        )

        monotonic_values = [0.0, 0.0, 1.0, 1.0, 1.5, 2.0]

        def fake_monotonic() -> float:
            if monotonic_values:
                return monotonic_values.pop(0)
            return 2.0

        with patch.object(android_smoke_run_plan, "resolve_boot_timeout", return_value=30.0), patch.object(
            android_smoke_run_plan, "probe_adb", side_effect=lambda *args, **kwargs: next(probe_results)
        ) as probe_mock, patch.object(
            android_smoke_run_plan.time, "monotonic", side_effect=fake_monotonic
        ), patch.object(android_smoke_run_plan.time, "sleep") as sleep_mock:
            android_smoke_run_plan.wait_for_boot_completion("adb")

        self.assertEqual(probe_mock.call_count, 6)
        sleep_mock.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
