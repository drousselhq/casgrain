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
LAUNCH_TIMEOUT_ENV = "CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS"
DEFAULT_APP_ID = "hq.droussel.casgrain.smoke"
DEFAULT_APK = "tests/fixtures/android-smoke/app/build/outputs/apk/debug/app-debug.apk"
DEFAULT_APK_GLOB = "tests/fixtures/android-smoke/app/build/outputs/apk/debug/*.apk"
DEFAULT_DEVICE_TIMEOUT_SECS = 20.0
DEFAULT_LAUNCH_TIMEOUT_SECS = 20.0
DEFAULT_MAIN_ACTIVITY = ".MainActivity"
UI_DUMP_REMOTE_PATH = "/sdcard/window_dump.xml"
FOREGROUND_WINDOW_ARTIFACT = "foreground-window.txt"
FOREGROUND_ACTIVITY_ARTIFACT = "foreground-activity.txt"
LAST_UI_DUMP_ARTIFACT = "ui-last.xml"
FAILURE_ARTIFACT = "failure.json"


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

    candidates = sorted((repo_root / "tests/fixtures/android-smoke/app/build/outputs/apk/debug").glob("*.apk"))
    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        candidate_list = ", ".join(str(path) for path in candidates)
        raise SystemExit(
            "found multiple Android smoke fixture APK candidates under "
            f"{repo_root / 'tests/fixtures/android-smoke/app/build/outputs/apk/debug'}: {candidate_list}; "
            f"set {APK_ENV} explicitly"
        )

    raise SystemExit(
        f"missing Android smoke fixture APK at {default_path}; no APKs matched {repo_root / DEFAULT_APK_GLOB}; "
        f"set {APK_ENV} to a built debug APK"
    )


def resolve_device_timeout() -> float:
    raw = os.environ.get(DEVICE_TIMEOUT_ENV, str(DEFAULT_DEVICE_TIMEOUT_SECS))
    return resolve_positive_timeout(raw, DEVICE_TIMEOUT_ENV)


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
        stdout = error.stdout.strip() if isinstance(error.stdout, str) else ""
        stderr = error.stderr.strip() if isinstance(error.stderr, str) else ""
        details = stderr or stdout or str(error)
        raise SystemExit(f"adb {' '.join(args)} failed: {details}") from error


def ensure_device_ready(adb: str) -> None:
    timeout = resolve_device_timeout()
    run_adb(adb, "wait-for-device", timeout=timeout)
    state = run_adb(adb, "get-state", timeout=max(1.0, timeout / 2)).stdout.strip()
    expect(state == "device", f"adb device is not ready: expected 'device', got {state!r}")


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
            ui_root = parse_ui(dump_ui_xml(adb))
            if dismiss_known_system_dialog(adb, ui_root, app_id=app_id):
                continue
        time.sleep(0.5)

    window_snapshot = last_snapshot.get("window", "")
    activity_snapshot = last_snapshot.get("activity", "")
    if artifact_dir is not None:
        write_failure_diagnostics(
            artifact_dir,
            f"fixture app {app_id!r} did not reach the foreground after launch",
            window_snapshot=window_snapshot or None,
            activity_snapshot=activity_snapshot or None,
        )
    raise SystemExit(
        f"fixture app {app_id!r} did not reach the foreground after launch; latest focus state:\n"
        f"[window]\n{window_snapshot}\n\n[activity]\n{activity_snapshot}"
    )


def dump_ui_xml(adb: str) -> str:
    run_adb(adb, "shell", "uiautomator", "dump", UI_DUMP_REMOTE_PATH)
    dump = run_adb(adb, "exec-out", "cat", UI_DUMP_REMOTE_PATH).stdout
    expect(dump.strip(), "uiautomator dump returned empty XML")
    return dump


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_failure_diagnostics(
    artifact_dir: Path,
    reason: str,
    *,
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
        last_xml = dump_ui_xml(adb)
        root = parse_ui(last_xml)
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
        last_xml = dump_ui_xml(adb)
        root = parse_ui(last_xml)
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
    before_tap_dump_path = artifact_dir / "ui-before-tap.xml"
    after_tap_dump_path = artifact_dir / "ui-after-tap.xml"

    started_at = utc_now()
    ensure_device_ready(adb)
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
