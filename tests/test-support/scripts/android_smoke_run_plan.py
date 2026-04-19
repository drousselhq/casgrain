#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

APP_ID_ENV = "CASGRAIN_ANDROID_SMOKE_APP_ID"
ACTIVITY_ENV = "CASGRAIN_ANDROID_SMOKE_ACTIVITY"
APK_ENV = "CASGRAIN_ANDROID_SMOKE_APK"
ADB_ENV = "CASGRAIN_ANDROID_ADB"
DEVICE_TIMEOUT_ENV = "CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS"
BOOT_TIMEOUT_ENV = "CASGRAIN_ANDROID_BOOT_TIMEOUT_SECS"
LAUNCH_TIMEOUT_ENV = "CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS"
DEFAULT_APP_ID = "hq.droussel.casgrain.smoke"
DEFAULT_APK = "tests/test-support/fixtures/android-smoke/app/build/outputs/apk/debug/app-debug.apk"
DEFAULT_APK_GLOB = "tests/test-support/fixtures/android-smoke/app/build/outputs/apk/debug/*.apk"
DEFAULT_DEVICE_TIMEOUT_SECS = 20.0
DEFAULT_BOOT_TIMEOUT_SECS = 90.0
DEFAULT_LAUNCH_TIMEOUT_SECS = 20.0
DEFAULT_MAIN_ACTIVITY = ".MainActivity"
UI_DUMP_REMOTE_PATH = "/sdcard/window_dump.xml"
FOREGROUND_WINDOW_ARTIFACT = "foreground-window.txt"
FOREGROUND_ACTIVITY_ARTIFACT = "foreground-activity.txt"
LAST_UI_DUMP_ARTIFACT = "ui-last.xml"
FAILURE_ARTIFACT = "failure.json"
FAILURE_CLASS_BOOT_READINESS = "boot-readiness-failure"
FAILURE_CLASS_APP_FOREGROUND = "app-foreground-failure"
FAILURE_CLASS_SELECTOR_TIMEOUT = "selector-timeout"
FAILURE_CLASS_TEXT_TIMEOUT = "text-timeout"
FAILURE_CLASS_UI_DUMP = "ui-dump-failure"


class UIDumpFailure(Exception):
    def __init__(self, message: str, *, ui_xml: str | None) -> None:
        super().__init__(message)
        self.ui_xml = ui_xml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the first Android smoke fixture plan against an emulator-backed adb harness."
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--artifact-dir", required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def decode_command_output(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace").strip()
    return output.strip() if isinstance(output, str) else ""


def load_json(path: Path, label: str) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise SystemExit(f"missing {label} at {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {label} at {path}: {error}") from error
    except OSError as error:
        raise SystemExit(f"failed to read {label} at {path}: {error}") from error


def validate_supported_plan(plan: dict) -> None:
    expect(
        plan.get("target", {}).get("platform") == "android",
        "fixture bridge only supports Android plans",
    )
    expect(
        plan.get("target", {}).get("device_class") == "emulator",
        "fixture bridge currently supports emulator-targeted plans only",
    )
    steps = plan.get("steps", [])
    expect(len(steps) == 4, "fixture bridge currently supports exactly four tap-counter steps")

    launch, tap, assertion, screenshot = steps
    expect(
        launch.get("action", {}).get("kind") == "launch_app"
        and launch["action"].get("app_id") == "app.under.test",
        "first step must launch the fixture app",
    )
    expect(
        launch.get("postconditions")
        == [{"kind": "app_in_foreground", "app_id": "app.under.test"}],
        "launch step must assert the fixture app is in the foreground",
    )
    expect(
        tap.get("action", {}).get("kind") == "tap"
        and tap["action"].get("target", {}).get("kind") == "accessibility_id"
        and tap["action"]["target"].get("value") == "tap-button",
        "second step must tap accessibility id tap-button",
    )
    expect(not tap.get("postconditions"), "tap step must not introduce extra postconditions")
    expect(
        assertion.get("action", {}).get("kind") == "noop"
        and assertion.get("postconditions")
        == [
            {
                "kind": "text_equals",
                "target": {"kind": "accessibility_id", "value": "count-label"},
                "value": "Count: 1",
            }
        ],
        "third step must assert count-label equals Count: 1",
    )
    expect(
        screenshot.get("action", {}).get("kind") == "take_screenshot"
        and screenshot["action"].get("name") == "android-tap-counter",
        "final step must capture screenshot android-tap-counter",
    )


def sha256_for(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_adb() -> str:
    return os.environ.get(ADB_ENV, "adb")


def resolve_app_id() -> str:
    return os.environ.get(APP_ID_ENV, DEFAULT_APP_ID)


def resolve_launch_component(app_id: str) -> str:
    configured = os.environ.get(ACTIVITY_ENV, DEFAULT_MAIN_ACTIVITY)
    if "/" in configured:
        return configured
    if configured.startswith("."):
        return f"{app_id}/{configured}"
    return f"{app_id}/{configured}"


def resolve_apk_path(repo_root: Path) -> Path:
    configured_path = os.environ.get(APK_ENV)
    if configured_path is not None:
        path = Path(configured_path)
        if not path.is_absolute():
            path = repo_root / path
        expect(
            path.is_file(),
            f"missing Android smoke fixture APK at {path}; set {APK_ENV} to a built debug APK",
        )
        return path

    default_path = repo_root / DEFAULT_APK
    if default_path.is_file():
        return default_path

    candidates = sorted((repo_root / "tests/test-support/fixtures/android-smoke/app/build/outputs/apk/debug").glob("*.apk"))
    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        candidate_list = ", ".join(str(path) for path in candidates)
        raise SystemExit(
            "found multiple Android smoke fixture APK candidates under "
            f"{repo_root / 'tests/test-support/fixtures/android-smoke/app/build/outputs/apk/debug'}: {candidate_list}; "
            f"set {APK_ENV} explicitly"
        )

    raise SystemExit(
        f"missing Android smoke fixture APK at {default_path}; no APKs matched {repo_root / DEFAULT_APK_GLOB}; "
        f"set {APK_ENV} to a built debug APK"
    )


def resolve_device_timeout() -> float:
    raw = os.environ.get(DEVICE_TIMEOUT_ENV, str(DEFAULT_DEVICE_TIMEOUT_SECS))
    return resolve_positive_timeout(raw, DEVICE_TIMEOUT_ENV)


def resolve_boot_timeout() -> float:
    raw = os.environ.get(BOOT_TIMEOUT_ENV, str(DEFAULT_BOOT_TIMEOUT_SECS))
    return resolve_positive_timeout(raw, BOOT_TIMEOUT_ENV)


def resolve_launch_timeout() -> float:
    raw = os.environ.get(LAUNCH_TIMEOUT_ENV, str(DEFAULT_LAUNCH_TIMEOUT_SECS))
    return resolve_positive_timeout(raw, LAUNCH_TIMEOUT_ENV)


def resolve_positive_timeout(raw: str, env_name: str) -> float:
    try:
        timeout = float(raw)
    except ValueError as error:
        raise SystemExit(
            f"invalid {env_name} value {raw!r}; expected a positive number of seconds"
        ) from error
    expect(timeout > 0, f"{env_name} must be greater than zero")
    return timeout


def run_adb(adb: str, *args: str, text: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [adb, *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise SystemExit(f"failed to launch adb binary '{adb}': {error}") from error
    except subprocess.TimeoutExpired as error:
        timeout_label = f" after {error.timeout:g}s" if error.timeout is not None else ""
        raise SystemExit(f"adb {' '.join(args)} timed out{timeout_label}") from error
    except subprocess.CalledProcessError as error:
        stdout = decode_command_output(error.stdout)
        stderr = decode_command_output(error.stderr)
        details = stderr or stdout or str(error)
        raise SystemExit(f"adb {' '.join(args)} failed: {details}") from error


def probe_adb(adb: str, *args: str, timeout: float) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [adb, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise SystemExit(f"failed to launch adb binary '{adb}': {error}") from error
    except subprocess.TimeoutExpired:
        return False, f"<timed out after {timeout:g}s>"

    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output


def boot_signals_ready(sys_boot_completed: str, dev_bootcomplete: str, package_manager_probe: str) -> bool:
    return (
        sys_boot_completed == "1"
        and (not dev_bootcomplete or dev_bootcomplete == "1")
        and package_manager_probe.startswith("package:")
    )


def wait_for_boot_completion(adb: str, *, artifact_dir: Path | None = None) -> None:
    timeout = resolve_boot_timeout()
    deadline = time.monotonic() + timeout
    last_boot = ""
    last_dev_boot = ""
    last_pm_status = ""

    while time.monotonic() < deadline:
        remaining_total = deadline - time.monotonic()
        probe_timeout = max(0.2, min(2.0, remaining_total / 3))
        boot_ok, last_boot = probe_adb(adb, "shell", "getprop", "sys.boot_completed", timeout=probe_timeout)
        dev_ok, last_dev_boot = probe_adb(adb, "shell", "getprop", "dev.bootcomplete", timeout=probe_timeout)
        pm_ok, last_pm_status = probe_adb(adb, "shell", "pm", "path", "android", timeout=probe_timeout)
        if boot_ok and dev_ok and pm_ok and boot_signals_ready(last_boot, last_dev_boot, last_pm_status):
            return
        sleep_for = min(1.0, max(0.0, deadline - time.monotonic()))
        if sleep_for:
            time.sleep(sleep_for)

    reason = (
        "Android emulator did not finish booting before the smoke run started; "
        f"observed sys.boot_completed={last_boot!r}, dev.bootcomplete={last_dev_boot!r}, "
        f"package-manager probe={last_pm_status!r}"
    )
    if artifact_dir is not None:
        write_failure_diagnostics(
            artifact_dir,
            reason,
            failure_class=FAILURE_CLASS_BOOT_READINESS,
        )
    raise SystemExit(reason)


def ensure_device_ready(adb: str, *, artifact_dir: Path | None = None) -> None:
    timeout = resolve_device_timeout()
    try:
        run_adb(adb, "wait-for-device", timeout=timeout)
        state = run_adb(adb, "get-state", timeout=max(1.0, timeout / 2)).stdout.strip()
        expect(state == "device", f"adb device is not ready: expected 'device', got {state!r}")
    except SystemExit as error:
        if artifact_dir is not None:
            write_failure_diagnostics(
                artifact_dir,
                str(error),
                failure_class=FAILURE_CLASS_BOOT_READINESS,
            )
        raise
    wait_for_boot_completion(adb, artifact_dir=artifact_dir)


def install_fixture_app(adb: str, apk_path: Path) -> None:
    run_adb(adb, "install", "-r", str(apk_path))


def reset_fixture_app(adb: str, app_id: str) -> None:
    run_adb(adb, "shell", "am", "force-stop", app_id)
    run_adb(adb, "shell", "pm", "clear", app_id)


def launch_fixture_app(adb: str, app_id: str) -> None:
    run_adb(adb, "shell", "am", "start", "-W", "-n", resolve_launch_component(app_id))


def dump_foreground_state(adb: str) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for label, command in (
        ("window", ("shell", "dumpsys", "window", "windows")),
        ("activity", ("shell", "dumpsys", "activity", "activities")),
    ):
        try:
            snapshots[label] = run_adb(adb, *command).stdout.strip()
        except SystemExit as error:
            snapshots[label] = f"<failed to capture {label} state: {error}>"
    return snapshots


def relevant_foreground_line(snapshot: str, markers: tuple[str, ...]) -> str | None:
    matches = [line.strip() for line in snapshot.splitlines() if any(marker in line for marker in markers)]
    return matches[-1] if matches else None


def app_is_in_foreground(snapshots: dict[str, str], app_id: str) -> bool:
    window_line = relevant_foreground_line(snapshots.get("window", ""), ("mCurrentFocus", "mFocusedApp"))
    activity_line = relevant_foreground_line(
        snapshots.get("activity", ""),
        ("topResumedActivity", "ResumedActivity"),
    )

    evidence = []
    if window_line is not None:
        evidence.append(app_id in window_line)
    if activity_line is not None:
        evidence.append(app_id in activity_line)
    return bool(evidence) and all(evidence)


def wait_for_app_foreground(
    adb: str,
    app_id: str,
    *,
    artifact_dir: Path | None = None,
    timeout_s: float = DEFAULT_LAUNCH_TIMEOUT_SECS,
) -> dict[str, str]:
    deadline = time.monotonic() + timeout_s
    last_snapshot: dict[str, str] = {}
    while time.monotonic() < deadline:
        last_snapshot = dump_foreground_state(adb)
        if app_is_in_foreground(last_snapshot, app_id):
            return last_snapshot
        if blocking_anr_package(last_snapshot.get("window", ""), app_id) is not None:
            ui_root, _ = load_ui_root_for_wait(
                adb,
                artifact_dir=artifact_dir,
                wait_description=f"waiting for fixture app {app_id!r} to reach the foreground",
                foreground_snapshot=last_snapshot,
            )
            if dismiss_known_system_dialog(adb, ui_root, app_id=app_id):
                continue
        time.sleep(0.5)

    window_snapshot = last_snapshot.get("window", "")
    activity_snapshot = last_snapshot.get("activity", "")
    if artifact_dir is not None:
        write_failure_diagnostics(
            artifact_dir,
            f"fixture app {app_id!r} did not reach the foreground after launch",
            failure_class=FAILURE_CLASS_APP_FOREGROUND,
            window_snapshot=window_snapshot or None,
            activity_snapshot=activity_snapshot or None,
        )
    raise SystemExit(
        f"fixture app {app_id!r} did not reach the foreground after launch; latest focus state:\n"
        f"[window]\n{window_snapshot}\n\n[activity]\n{activity_snapshot}"
    )


def dump_ui_xml(adb: str) -> str:
    run_adb(adb, "shell", "uiautomator", "dump", UI_DUMP_REMOTE_PATH)
    dump = run_adb(adb, "exec-out", "cat", UI_DUMP_REMOTE_PATH, text=False).stdout
    return dump.decode("utf-8", errors="replace") if isinstance(dump, bytes) else dump


def load_ui_root(adb: str) -> tuple[ET.Element, str]:
    try:
        ui_xml = dump_ui_xml(adb)
    except SystemExit as error:
        raise UIDumpFailure(str(error), ui_xml="") from error
    if not ui_xml.strip():
        raise UIDumpFailure("uiautomator dump returned empty XML", ui_xml=ui_xml)
    try:
        return parse_ui(ui_xml), ui_xml
    except SystemExit as error:
        raise UIDumpFailure(str(error), ui_xml=ui_xml) from error


def best_effort_foreground_state(adb: str) -> dict[str, str]:
    try:
        return dump_foreground_state(adb)
    except SystemExit:
        return {}


def load_ui_root_for_wait(
    adb: str,
    *,
    artifact_dir: Path | None,
    wait_description: str,
    foreground_snapshot: dict[str, str] | None = None,
) -> tuple[ET.Element, str]:
    try:
        return load_ui_root(adb)
    except UIDumpFailure as error:
        latest_foreground = foreground_snapshot if foreground_snapshot is not None else best_effort_foreground_state(adb)
        reason = f"failed to capture emulator UI hierarchy while {wait_description}: {error}"
        if artifact_dir is not None:
            write_failure_diagnostics(
                artifact_dir,
                reason,
                failure_class=FAILURE_CLASS_UI_DUMP,
                window_snapshot=latest_foreground.get("window") or None,
                activity_snapshot=latest_foreground.get("activity") or None,
                ui_xml=error.ui_xml,
            )
        raise SystemExit(reason) from error


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_failure_diagnostics(
    artifact_dir: Path,
    reason: str,
    *,
    failure_class: str,
    window_snapshot: str | None = None,
    activity_snapshot: str | None = None,
    ui_xml: str | None = None,
) -> None:
    if window_snapshot is not None:
        write_text(artifact_dir / FOREGROUND_WINDOW_ARTIFACT, window_snapshot)
    if activity_snapshot is not None:
        write_text(artifact_dir / FOREGROUND_ACTIVITY_ARTIFACT, activity_snapshot)
    if ui_xml is not None:
        write_text(artifact_dir / LAST_UI_DUMP_ARTIFACT, ui_xml)

    payload = {
        "reason": reason,
        "failure_class": failure_class,
        "captured_at": utc_now(),
        "artifacts": {
            "foreground_window": FOREGROUND_WINDOW_ARTIFACT if window_snapshot is not None else None,
            "foreground_activity": FOREGROUND_ACTIVITY_ARTIFACT if activity_snapshot is not None else None,
            "last_ui_dump": LAST_UI_DUMP_ARTIFACT if ui_xml is not None else None,
        },
    }
    write_text(artifact_dir / FAILURE_ARTIFACT, json.dumps(payload, indent=2) + "\n")


def parse_ui(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise SystemExit(f"failed to parse uiautomator XML dump: {error}") from error


def selector_variants(selector: str) -> set[str]:
    underscored = selector.replace("-", "_")
    return {selector, underscored}


def node_matches(node: ET.Element, selector: str) -> bool:
    variants = selector_variants(selector)
    content_desc = node.attrib.get("content-desc", "")
    resource_id = node.attrib.get("resource-id", "")
    view_id = resource_id.rsplit("/", 1)[-1] if resource_id else ""
    return content_desc in variants or view_id in variants


def find_node(root: ET.Element, selector: str) -> ET.Element | None:
    for node in root.iter("node"):
        if node_matches(node, selector):
            return node
    return None


def blocking_anr_package(window_snapshot: str, app_id: str) -> str | None:
    match = re.search(r"Application Not Responding: ([^}\n]+)", window_snapshot)
    if match is None:
        return None
    package_name = match.group(1).strip()
    if package_name == app_id:
        return None
    return package_name


def dismiss_known_system_dialog(
    adb: str,
    root: ET.Element,
    *,
    app_id: str,
) -> bool:
    window_snapshot = dump_foreground_state(adb).get("window", "")
    foreign_anr_package = blocking_anr_package(window_snapshot, app_id)
    if foreign_anr_package is None:
        return False

    wait_button = find_node(root, "aerr_wait")
    if wait_button is None:
        return False

    tap_selector(adb, wait_button)
    time.sleep(0.5)
    return True


def parse_bounds(bounds: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    expect(match is not None, f"invalid bounds string in uiautomator dump: {bounds!r}")
    left, top, right, bottom = (int(group) for group in match.groups())
    return left, top, right, bottom


def center_point(node: ET.Element) -> tuple[int, int]:
    left, top, right, bottom = parse_bounds(node.attrib.get("bounds", ""))
    return ((left + right) // 2, (top + bottom) // 2)


def wait_for_selector(
    adb: str,
    selector: str,
    *,
    app_id: str,
    artifact_dir: Path | None = None,
    timeout_s: float = 15.0,
) -> tuple[ET.Element, str]:
    deadline = time.monotonic() + timeout_s
    last_xml = ""
    while time.monotonic() < deadline:
        root, last_xml = load_ui_root_for_wait(
            adb,
            artifact_dir=artifact_dir,
            wait_description=f"waiting for selector {selector!r}",
        )
        node = find_node(root, selector)
        if node is not None:
            return node, last_xml
        if dismiss_known_system_dialog(adb, root, app_id=app_id):
            continue
        time.sleep(0.5)
    if artifact_dir is not None:
        latest_foreground = dump_foreground_state(adb)
        write_failure_diagnostics(
            artifact_dir,
            f"timed out waiting for selector {selector!r} in emulator UI hierarchy",
            failure_class=FAILURE_CLASS_SELECTOR_TIMEOUT,
            window_snapshot=latest_foreground.get("window"),
            activity_snapshot=latest_foreground.get("activity"),
            ui_xml=last_xml or None,
        )
    raise SystemExit(f"timed out waiting for selector {selector!r} in emulator UI hierarchy")


def wait_for_text(
    adb: str,
    selector: str,
    expected_text: str,
    *,
    app_id: str,
    artifact_dir: Path | None = None,
    timeout_s: float = 15.0,
) -> tuple[ET.Element, str]:
    deadline = time.monotonic() + timeout_s
    last_xml = ""
    while time.monotonic() < deadline:
        root, last_xml = load_ui_root_for_wait(
            adb,
            artifact_dir=artifact_dir,
            wait_description=f"waiting for selector {selector!r} to have text {expected_text!r}",
        )
        node = find_node(root, selector)
        if node is not None and node.attrib.get("text") == expected_text:
            return node, last_xml
        if dismiss_known_system_dialog(adb, root, app_id=app_id):
            continue
        time.sleep(0.5)
    if artifact_dir is not None:
        latest_foreground = dump_foreground_state(adb)
        write_failure_diagnostics(
            artifact_dir,
            f"timed out waiting for selector {selector!r} to have text {expected_text!r}",
            failure_class=FAILURE_CLASS_TEXT_TIMEOUT,
            window_snapshot=latest_foreground.get("window"),
            activity_snapshot=latest_foreground.get("activity"),
            ui_xml=last_xml or None,
        )
    raise SystemExit(
        f"timed out waiting for selector {selector!r} to have text {expected_text!r}"
    )


def tap_selector(adb: str, node: ET.Element) -> None:
    x, y = center_point(node)
    run_adb(adb, "shell", "input", "tap", str(x), str(y))


def capture_screenshot(adb: str, path: Path) -> None:
    screenshot = run_adb(adb, "exec-out", "screencap", "-p", text=False).stdout
    expect(bool(screenshot), "adb screencap returned empty output")
    path.write_bytes(screenshot)


def read_device_property(adb: str, prop: str, fallback: str) -> str:
    value = run_adb(adb, "shell", "getprop", prop).stdout.strip()
    return value or fallback


def read_os_release_value(field_name: str, fallback: str) -> str:
    os_release = Path("/etc/os-release")
    if not os_release.is_file():
        return fallback
    for line in os_release.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{field_name}="):
            return line.split("=", 1)[1].strip().strip('"') or fallback
    return fallback


def command_output(*args: str) -> str:
    completed = subprocess.run(
        list(args),
        check=True,
        capture_output=True,
        text=True,
    )
    return (completed.stdout + completed.stderr).strip()


def parse_java_runtime_version(output: str) -> str:
    match = re.search(r"java\.runtime\.version\s*=\s*(\S+)", output)
    if match:
        return match.group(1).removesuffix("-LTS")
    match = re.search(r"Runtime Version .*? (\S+)", output)
    if match:
        return match.group(1).removesuffix("-LTS")
    return "unknown"


def parse_gradle_version(output: str) -> str:
    match = re.search(r"^Gradle\s+(\S+)", output, flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def normalize_runner_image_name(image_name: str) -> str:
    normalized = image_name.strip().lower()
    if not normalized or normalized == "unknown":
        return image_name or "unknown"
    ubuntu_match = re.fullmatch(r"ubuntu(\d{2})(\d{2})?", normalized)
    if ubuntu_match:
        major = ubuntu_match.group(1)
        minor = ubuntu_match.group(2) or "04"
        return f"ubuntu-{major}.{minor}"
    return image_name


def normalize_linux_os_version(version_text: str) -> str:
    match = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", version_text)
    if match:
        return match.group(1)
    return version_text.strip() or "unknown"


def github_run_metadata() -> dict[str, str]:
    return {
        "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "android-emulator-smoke"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "run_url": os.environ.get(
            "GITHUB_SERVER_URL", "https://github.com"
        )
        + "/"
        + os.environ.get("GITHUB_REPOSITORY", "local")
        + "/actions/runs/"
        + os.environ.get("GITHUB_RUN_ID", "local"),
    }


def build_android_host_environment(emulator_info: dict[str, str]) -> dict[str, object]:
    java_output = command_output("java", "-XshowSettings:properties", "-version")
    gradle_output = command_output("gradle", "--version")
    raw_image_name = os.environ.get("ImageOS", "unknown")
    os_version = normalize_linux_os_version(
        read_os_release_value("VERSION", read_os_release_value("VERSION_ID", "unknown"))
    )
    return {
        "generated_at": utc_now(),
        "workflow_run": github_run_metadata(),
        "runner": {
            "label": "ubuntu-latest",
            "image_name": normalize_runner_image_name(raw_image_name),
            "image_version": os.environ.get("ImageVersion", "unknown"),
            "os_name": read_os_release_value("NAME", "Ubuntu"),
            "os_version": os_version,
        },
        "java": {
            "distribution": "temurin",
            "configured_major": "17",
            "resolved_version": parse_java_runtime_version(java_output),
        },
        "gradle": {
            "configured_version": "8.7",
            "resolved_version": parse_gradle_version(gradle_output),
        },
        "emulator": {
            "api_level": "34",
            "arch": "x86_64",
            "target": "google_apis",
            "profile": "pixel_7",
            "device_name": emulator_info["device_name"],
            "os_version": emulator_info["os_version"],
        },
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    plan_path = Path(args.plan).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    plan = load_json(plan_path, "compiled plan")
    validate_supported_plan(plan)

    adb = resolve_adb()
    app_id = resolve_app_id()
    apk_path = resolve_apk_path(repo_root)
    screenshot_path = artifact_dir / "android-tap-counter-1.png"
    emulator_info_path = artifact_dir / "emulator.json"
    host_environment_path = artifact_dir / "host-environment.json"
    before_tap_dump_path = artifact_dir / "ui-before-tap.xml"
    after_tap_dump_path = artifact_dir / "ui-after-tap.xml"

    started_at = utc_now()
    ensure_device_ready(adb, artifact_dir=artifact_dir)
    install_fixture_app(adb, apk_path)
    reset_fixture_app(adb, app_id)
    launch_fixture_app(adb, app_id)
    wait_for_app_foreground(
        adb,
        app_id,
        artifact_dir=artifact_dir,
        timeout_s=resolve_launch_timeout(),
    )

    tap_button, before_tap_xml = wait_for_selector(
        adb,
        "tap-button",
        app_id=app_id,
        artifact_dir=artifact_dir,
    )
    write_text(before_tap_dump_path, before_tap_xml)

    count_label_root = parse_ui(before_tap_xml)
    count_label = find_node(count_label_root, "count-label")
    expect(count_label is not None, "count-label was missing after launching the fixture app")
    expect(
        count_label.attrib.get("text") == "Count: 0",
        f"expected initial count-label text to be 'Count: 0', got {count_label.attrib.get('text')!r}",
    )

    tap_selector(adb, tap_button)
    _, after_tap_xml = wait_for_text(
        adb,
        "count-label",
        "Count: 1",
        app_id=app_id,
        artifact_dir=artifact_dir,
    )
    write_text(after_tap_dump_path, after_tap_xml)
    capture_screenshot(adb, screenshot_path)

    device_name = read_device_property(adb, "ro.product.model", "unknown Android emulator")
    os_version = read_device_property(adb, "ro.build.version.release", "unknown")
    finished_at = utc_now()

    emulator_info = {
        "adb_binary": adb,
        "app_id": app_id,
        "apk_path": str(apk_path),
        "device_name": device_name,
        "os_version": os_version,
    }
    emulator_info_path.write_text(json.dumps(emulator_info, indent=2) + "\n")
    host_environment = build_android_host_environment(emulator_info)
    host_environment_path.write_text(json.dumps(host_environment, indent=2) + "\n")

    steps = [
        {
            "step_id": step["step_id"],
            "status": "passed",
            "attempts": 1,
            "failure": None,
            "artifacts": [],
        }
        for step in plan["steps"]
    ]

    screenshot_artifact = {
        "artifact_id": "android-tap-counter-1",
        "artifact_type": "screenshot",
        "path": str(screenshot_path),
        "sha256": sha256_for(screenshot_path),
        "step_id": plan["steps"][-1]["step_id"],
    }
    steps[-1]["artifacts"] = [screenshot_artifact]

    trace = {
        "run_id": f"android-smoke-{plan['plan_id']}",
        "plan_id": plan["plan_id"],
        "device": {
            "platform": "android",
            "name": device_name,
            "os_version": os_version,
        },
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "passed",
        "steps": steps,
        "artifacts": [
            screenshot_artifact,
            {
                "artifact_id": "android-smoke-emulator",
                "artifact_type": "emulator_descriptor",
                "path": str(emulator_info_path),
                "sha256": sha256_for(emulator_info_path),
                "step_id": None,
            },
            {
                "artifact_id": "android-host-environment",
                "artifact_type": "host_environment",
                "path": str(host_environment_path),
                "sha256": sha256_for(host_environment_path),
                "step_id": None,
            },
            {
                "artifact_id": "android-ui-before-tap",
                "artifact_type": "ui_hierarchy",
                "path": str(before_tap_dump_path),
                "sha256": sha256_for(before_tap_dump_path),
                "step_id": plan["steps"][1]["step_id"],
            },
            {
                "artifact_id": "android-ui-after-tap",
                "artifact_type": "ui_hierarchy",
                "path": str(after_tap_dump_path),
                "sha256": sha256_for(after_tap_dump_path),
                "step_id": plan["steps"][2]["step_id"],
            },
        ],
        "diagnostics": [],
    }
    print(json.dumps(trace))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or str(error)
        print(message, file=sys.stderr)
        raise SystemExit(error.returncode)
    except SystemExit:
        raise
    except Exception as error:  # pragma: no cover - defensive CLI wrapper
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
