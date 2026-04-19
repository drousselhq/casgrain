import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("android_smoke_run_plan.py")
spec = importlib.util.spec_from_file_location("android_smoke_run_plan", MODULE_PATH)
android_smoke_run_plan = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(android_smoke_run_plan)

APP_ID = "hq.droussel.casgrain.smoke"
APP_WINDOW = "mCurrentFocus=Window{42 u0 hq.droussel.casgrain.smoke/.MainActivity}"
APP_ACTIVITY = "ResumedActivity: ActivityRecord{42 u0 hq.droussel.casgrain.smoke/.MainActivity t12}"
LAUNCHER_WINDOW = "mCurrentFocus=Window{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}"
LAUNCHER_ACTIVITY = "ResumedActivity: ActivityRecord{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}"
ANR_WINDOW = "mCurrentFocus=Window{42 u0 Application Not Responding: com.google.android.apps.nexuslauncher}"

ANR_DIALOG_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<hierarchy rotation=\"0\">
  <node index=\"0\" text=\"\" resource-id=\"\" class=\"android.widget.FrameLayout\" bounds=\"[0,0][1080,2400]\">
    <node index=\"0\" text=\"Wait\" resource-id=\"android:id/aerr_wait\" class=\"android.widget.Button\" bounds=\"[100,200][300,320]\" />
  </node>
</hierarchy>
"""

NO_MATCHING_SELECTOR_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<hierarchy rotation=\"0\">
  <node index=\"0\" text=\"\" resource-id=\"\" class=\"android.widget.FrameLayout\" bounds=\"[0,0][1080,2400]\">
    <node index=\"0\" text=\"Count: 0\" resource-id=\"hq.droussel.casgrain.smoke:id/count_label\" class=\"android.widget.TextView\" content-desc=\"count-label\" bounds=\"[100,80][500,160]\" />
  </node>
</hierarchy>
"""
MALFORMED_UI_XML = "<hierarchy><node"
EMPTY_UI_XML = ""


def monotonic_side_effect(*values: float):
    iterator = iter(values)
    last = values[-1]

    def fake_monotonic() -> float:
        try:
            return next(iterator)
        except StopIteration:
            return last

    return fake_monotonic


class HostEnvironmentNormalizationTests(unittest.TestCase):
    def test_load_android_workflow_config_reads_watched_values_from_workflow_yaml(self) -> None:
        workflow = """jobs:
  smoke:
    runs-on: ubuntu-24.04
    steps:
      - name: Set up Java
        with:
          java-version: '21'
      - name: Set up Gradle
        with:
          gradle-version: '8.10'
      - name: Run generated-plan Android smoke path
        with:
          api-level: 35
          arch: arm64-v8a
          target: google_apis_playstore
          profile: pixel_8
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "android-emulator-smoke.yml"
            workflow_path.write_text(workflow, encoding="utf-8")
            config = android_smoke_run_plan.load_android_workflow_config(workflow_path)

        self.assertEqual(
            config,
            {
                "runner_label": "ubuntu-24.04",
                "java_version": "21",
                "gradle_version": "8.10",
                "api_level": "35",
                "arch": "arm64-v8a",
                "target": "google_apis_playstore",
                "profile": "pixel_8",
            },
        )

    def test_build_android_host_environment_uses_workflow_config_for_watched_fields(self) -> None:
        emulator_info = {"device_name": "sdk_gphone64_x86_64", "os_version": "14"}
        java_output = "java.runtime.version = 21.0.2+13\n"
        gradle_output = "Gradle 8.10\n"

        with patch.dict(
            android_smoke_run_plan.os.environ,
            {
                "ImageOS": "ubuntu24",
                "ImageVersion": "20260413.86.1",
                "GITHUB_REPOSITORY": "drousselhq/casgrain",
                "GITHUB_WORKFLOW": "android-emulator-smoke",
                "GITHUB_RUN_ID": "24624943594",
                "GITHUB_RUN_ATTEMPT": "1",
            },
            clear=False,
        ), patch.object(
            android_smoke_run_plan,
            "load_android_workflow_config",
            return_value={
                "runner_label": "ubuntu-24.04",
                "java_version": "21",
                "gradle_version": "8.10",
                "api_level": "35",
                "arch": "arm64-v8a",
                "target": "google_apis_playstore",
                "profile": "pixel_8",
            },
        ), patch.object(
            android_smoke_run_plan,
            "command_output",
            side_effect=[java_output, gradle_output],
        ), patch.object(
            android_smoke_run_plan,
            "read_os_release_value",
            side_effect=lambda field, fallback: {
                "NAME": "Ubuntu",
                "VERSION": "24.04.4 LTS (Noble Numbat)",
            }.get(field, fallback),
        ), patch.object(
            android_smoke_run_plan,
            "utc_now",
            return_value="2026-04-19T09:00:00Z",
        ):
            host_environment = android_smoke_run_plan.build_android_host_environment(emulator_info)

        self.assertEqual(host_environment["generated_at"], "2026-04-19T09:00:00Z")
        self.assertEqual(host_environment["workflow_run"]["run_url"], "https://github.com/drousselhq/casgrain/actions/runs/24624943594")
        self.assertEqual(host_environment["runner"]["label"], "ubuntu-24.04")
        self.assertEqual(host_environment["runner"]["image_name"], "ubuntu-24.04")
        self.assertEqual(host_environment["runner"]["os_version"], "24.04.4")
        self.assertEqual(host_environment["java"]["configured_major"], "21")
        self.assertEqual(host_environment["gradle"]["configured_version"], "8.10")
        self.assertEqual(host_environment["emulator"]["api_level"], "35")
        self.assertEqual(host_environment["emulator"]["arch"], "arm64-v8a")
        self.assertEqual(host_environment["emulator"]["target"], "google_apis_playstore")
        self.assertEqual(host_environment["emulator"]["profile"], "pixel_8")


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

        with patch.object(android_smoke_run_plan, "resolve_boot_timeout", return_value=30.0), patch.object(
            android_smoke_run_plan, "probe_adb", side_effect=lambda *args, **kwargs: next(probe_results)
        ) as probe_mock, patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.0, 0.0, 0.9, 1.0, 1.0),
        ), patch.object(android_smoke_run_plan.time, "sleep") as sleep_mock:
            android_smoke_run_plan.wait_for_boot_completion("adb")

        self.assertEqual(probe_mock.call_count, 6)
        sleep_mock.assert_called_once_with(1.0)

    def test_timeout_writes_boot_readiness_failure_artifacts(self) -> None:
        probe_results = iter(
            [
                (True, "0"),
                (True, "0"),
                (False, "Error: Can't find service: package"),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "resolve_boot_timeout", return_value=1.0
        ), patch.object(
            android_smoke_run_plan, "probe_adb", side_effect=lambda *args, **kwargs: next(probe_results)
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.0, 0.0, 1.1, 1.1),
        ), patch.object(android_smoke_run_plan.time, "sleep"):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_boot_completion("adb", artifact_dir=artifact_dir)
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())

        self.assertIn("did not finish booting", str(error.exception))
        self.assertEqual(failure["failure_class"], "boot-readiness-failure")
        self.assertEqual(
            failure["artifacts"],
            {
                "foreground_window": None,
                "foreground_activity": None,
                "last_ui_dump": None,
            },
        )
        self.assertIn("sys.boot_completed='0'", failure["reason"])


class EnsureDeviceReadyTests(unittest.TestCase):
    def test_wait_for_device_failure_writes_boot_readiness_failure_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "resolve_device_timeout", return_value=20.0
        ), patch.object(
            android_smoke_run_plan,
            "run_adb",
            side_effect=SystemExit("adb wait-for-device failed: no devices/emulators found"),
        ), patch.object(android_smoke_run_plan, "wait_for_boot_completion") as wait_for_boot_completion_mock:
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.ensure_device_ready("adb", artifact_dir=artifact_dir)
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())

        self.assertEqual(str(error.exception), "adb wait-for-device failed: no devices/emulators found")
        self.assertEqual(failure["failure_class"], "boot-readiness-failure")
        self.assertEqual(
            failure["artifacts"],
            {
                "foreground_window": None,
                "foreground_activity": None,
                "last_ui_dump": None,
            },
        )
        wait_for_boot_completion_mock.assert_not_called()

    def test_non_device_state_writes_boot_readiness_failure_artifacts(self) -> None:
        wait_for_device_result = subprocess.CompletedProcess(
            args=["adb", "wait-for-device"],
            returncode=0,
            stdout="",
            stderr="",
        )
        get_state_result = subprocess.CompletedProcess(
            args=["adb", "get-state"],
            returncode=0,
            stdout="offline\n",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "resolve_device_timeout", return_value=20.0
        ), patch.object(
            android_smoke_run_plan,
            "run_adb",
            side_effect=[wait_for_device_result, get_state_result],
        ), patch.object(android_smoke_run_plan, "wait_for_boot_completion") as wait_for_boot_completion_mock:
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.ensure_device_ready("adb", artifact_dir=artifact_dir)
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())

        self.assertEqual(str(error.exception), "adb device is not ready: expected 'device', got 'offline'")
        self.assertEqual(failure["failure_class"], "boot-readiness-failure")
        self.assertEqual(
            failure["artifacts"],
            {
                "foreground_window": None,
                "foreground_activity": None,
                "last_ui_dump": None,
            },
        )
        wait_for_boot_completion_mock.assert_not_called()


class WaitForAppForegroundTests(unittest.TestCase):
    def test_dismisses_foreign_anr_overlay_and_retries_until_app_is_foreground(self) -> None:
        snapshots = iter(
            [
                {"window": ANR_WINDOW, "activity": APP_ACTIVITY},
                {"window": ANR_WINDOW, "activity": APP_ACTIVITY},
                {"window": APP_WINDOW, "activity": APP_ACTIVITY},
            ]
        )

        with patch.object(
            android_smoke_run_plan, "dump_foreground_state", side_effect=lambda adb: next(snapshots)
        ), patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=ANR_DIALOG_XML
        ), patch.object(
            android_smoke_run_plan, "tap_selector"
        ) as tap_selector_mock, patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.1, 0.2),
        ), patch.object(android_smoke_run_plan.time, "sleep") as sleep_mock:
            result = android_smoke_run_plan.wait_for_app_foreground("adb", APP_ID, timeout_s=1.0)

        self.assertEqual(result["window"], APP_WINDOW)
        tap_selector_mock.assert_called_once()
        sleep_mock.assert_called_once_with(0.5)

    def test_launch_timeout_writes_app_foreground_failure_artifacts(self) -> None:
        snapshot = {"window": LAUNCHER_WINDOW, "activity": LAUNCHER_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.5, 1.1),
        ), patch.object(android_smoke_run_plan.time, "sleep"):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_app_foreground(
                    "adb", APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            foreground_window = (artifact_dir / android_smoke_run_plan.FOREGROUND_WINDOW_ARTIFACT).read_text()

        self.assertIn("did not reach the foreground", str(error.exception))
        self.assertEqual(failure["failure_class"], "app-foreground-failure")
        self.assertEqual(failure["artifacts"]["foreground_window"], android_smoke_run_plan.FOREGROUND_WINDOW_ARTIFACT)
        self.assertEqual(foreground_window, LAUNCHER_WINDOW)

    def test_malformed_ui_dump_writes_structured_failure_artifacts_during_anr_recovery(self) -> None:
        snapshot = {"window": ANR_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=MALFORMED_UI_XML
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_app_foreground(
                    "adb", APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("failed to parse uiautomator XML dump", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["foreground_window"], android_smoke_run_plan.FOREGROUND_WINDOW_ARTIFACT)
        self.assertEqual(failure["artifacts"]["foreground_activity"], android_smoke_run_plan.FOREGROUND_ACTIVITY_ARTIFACT)
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, MALFORMED_UI_XML)

    def test_empty_ui_dump_writes_structured_failure_artifacts_during_anr_recovery(self) -> None:
        snapshot = {"window": ANR_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=EMPTY_UI_XML
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_app_foreground(
                    "adb", APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("uiautomator dump returned empty XML", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, EMPTY_UI_XML)


class WaitForSelectorTests(unittest.TestCase):
    def test_timeout_writes_selector_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=NO_MATCHING_SELECTOR_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan, "dismiss_known_system_dialog", return_value=False
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.5, 1.1),
        ), patch.object(android_smoke_run_plan.time, "sleep"):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_selector(
                    "adb", "tap-button", app_id=APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("timed out waiting for selector 'tap-button'", str(error.exception))
        self.assertEqual(failure["failure_class"], "selector-timeout")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, NO_MATCHING_SELECTOR_XML)

    def test_empty_ui_dump_writes_structured_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=EMPTY_UI_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_selector(
                    "adb", "tap-button", app_id=APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("uiautomator dump returned empty XML", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, EMPTY_UI_XML)

    def test_malformed_ui_dump_writes_structured_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=MALFORMED_UI_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_selector(
                    "adb", "tap-button", app_id=APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("failed to parse uiautomator XML dump", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, MALFORMED_UI_XML)

    def test_ui_dump_command_failure_still_writes_structured_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan,
            "dump_ui_xml",
            side_effect=SystemExit("adb exec-out cat /sdcard/window_dump.xml failed: remote object missing"),
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_selector(
                    "adb", "tap-button", app_id=APP_ID, artifact_dir=artifact_dir, timeout_s=1.0
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("adb exec-out cat /sdcard/window_dump.xml failed", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, "")


class WaitForTextTests(unittest.TestCase):
    def test_timeout_writes_text_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=NO_MATCHING_SELECTOR_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan, "dismiss_known_system_dialog", return_value=False
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0, 0.5, 1.1),
        ), patch.object(android_smoke_run_plan.time, "sleep"):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_text(
                    "adb",
                    "count-label",
                    "Count: 1",
                    app_id=APP_ID,
                    artifact_dir=artifact_dir,
                    timeout_s=1.0,
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())

        self.assertIn("to have text 'Count: 1'", str(error.exception))
        self.assertEqual(failure["failure_class"], "text-timeout")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)

    def test_empty_ui_dump_writes_structured_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=EMPTY_UI_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_text(
                    "adb",
                    "count-label",
                    "Count: 1",
                    app_id=APP_ID,
                    artifact_dir=artifact_dir,
                    timeout_s=1.0,
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("uiautomator dump returned empty XML", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, EMPTY_UI_XML)

    def test_malformed_ui_dump_writes_structured_failure_artifacts(self) -> None:
        snapshot = {"window": APP_WINDOW, "activity": APP_ACTIVITY}

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            android_smoke_run_plan, "dump_ui_xml", return_value=MALFORMED_UI_XML
        ), patch.object(
            android_smoke_run_plan, "dump_foreground_state", return_value=snapshot
        ), patch.object(
            android_smoke_run_plan.time,
            "monotonic",
            side_effect=monotonic_side_effect(0.0),
        ):
            artifact_dir = Path(tmpdir)
            with self.assertRaises(SystemExit) as error:
                android_smoke_run_plan.wait_for_text(
                    "adb",
                    "count-label",
                    "Count: 1",
                    app_id=APP_ID,
                    artifact_dir=artifact_dir,
                    timeout_s=1.0,
                )
            failure = json.loads((artifact_dir / android_smoke_run_plan.FAILURE_ARTIFACT).read_text())
            ui_last = (artifact_dir / android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT).read_text()

        self.assertIn("failed to parse uiautomator XML dump", str(error.exception))
        self.assertEqual(failure["failure_class"], "ui-dump-failure")
        self.assertEqual(failure["artifacts"]["last_ui_dump"], android_smoke_run_plan.LAST_UI_DUMP_ARTIFACT)
        self.assertEqual(ui_last, MALFORMED_UI_XML)


if __name__ == "__main__":
    unittest.main()
