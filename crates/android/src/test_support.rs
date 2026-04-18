use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
    time::{SystemTime, UNIX_EPOCH},
};

use domain::{
    ActionKind, ArtifactPolicy, AssertionKind, CapabilitySet, ExecutablePlan, ExecutionDefaults,
    FailurePolicy, PlanFormatVersion, PlanSource, PlanStep, RetryPolicy, Selector, SourceKind,
    StepIntent, TargetPlatform, TargetProfile,
};

pub(crate) fn supported_smoke_plan() -> ExecutablePlan {
    ExecutablePlan {
        plan_id: "increment-the-counter-once".into(),
        name: "Increment the counter once".into(),
        version: PlanFormatVersion { major: 1, minor: 0 },
        source: PlanSource {
            kind: SourceKind::Gherkin,
            source_name: "tests/test-support/fixtures/android-smoke/features/tap_counter.feature"
                .into(),
            compiler_version: "0.1.0".into(),
        },
        target: TargetProfile {
            platform: TargetPlatform::Android,
            device_class: "emulator".into(),
        },
        capabilities_required: CapabilitySet {
            capabilities: vec!["screenshot".into()],
        },
        defaults: ExecutionDefaults::default(),
        steps: vec![
            PlanStep {
                step_id: "increment-the-counter-once-001".into(),
                intent: StepIntent::Setup,
                description: "the app is launched".into(),
                action: ActionKind::LaunchApp {
                    app_id: "app.under.test".into(),
                },
                guards: vec![],
                postconditions: vec![AssertionKind::AppInForeground {
                    app_id: "app.under.test".into(),
                }],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-002".into(),
                intent: StepIntent::Interact,
                description: "the user taps tap button".into(),
                action: ActionKind::Tap {
                    target: Selector::AccessibilityId("tap-button".into()),
                },
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-003".into(),
                intent: StepIntent::Assert,
                description: "count label text is \"Count: 1\"".into(),
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![AssertionKind::TextEquals {
                    target: Selector::AccessibilityId("count-label".into()),
                    value: "Count: 1".into(),
                }],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-004".into(),
                intent: StepIntent::Interact,
                description: "the user takes a screenshot".into(),
                action: ActionKind::TakeScreenshot {
                    name: Some("android-tap-counter".into()),
                },
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
        ],
        metadata: Default::default(),
    }
}

pub(crate) fn install_fake_android_smoke_runner(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let runner = repo_root.join("runner.py");
    fs::write(
        &runner,
        r#"#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", required=True)
parser.add_argument("--plan", required=True)
parser.add_argument("--artifact-dir", required=True)
args = parser.parse_args()

plan = json.loads(Path(args.plan).read_text())
artifact_dir = Path(args.artifact_dir)
artifact_dir.mkdir(parents=True, exist_ok=True)
artifact_path = artifact_dir / "android-tap-counter-1.png"
artifact_path.write_bytes(b"png")

print(json.dumps({
    "run_id": f"android-smoke-{plan['plan_id']}",
    "plan_id": plan["plan_id"],
    "device": {
        "platform": "android",
        "name": "Pixel 8",
        "os_version": "15"
    },
    "started_at": "2026-01-01T00:00:00Z",
    "finished_at": "2026-01-01T00:00:01Z",
    "status": "passed",
    "steps": [
        {
            "step_id": step["step_id"],
            "status": "passed",
            "attempts": 1,
            "failure": None,
            "artifacts": []
        }
        for step in plan["steps"]
    ],
    "artifacts": [
        {
            "artifact_id": "android-tap-counter-1",
            "artifact_type": "screenshot",
            "path": str(artifact_path),
            "sha256": None,
            "step_id": plan["steps"][-1]["step_id"]
        }
    ],
    "diagnostics": []
}))
"#,
    )
    .expect("fake runner should be written");
    let mut permissions = fs::metadata(&runner)
        .expect("runner metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&runner, permissions).expect("runner should be executable");
    runner
}

pub(crate) fn install_fake_adb(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let adb = repo_root.join("fake-adb.py");
    fs::write(
        &adb,
        format!(
            r##"#!/usr/bin/env python3
import json
import sys
from pathlib import Path

STATE_PATH = Path({state_path:?})
BOUNDS = "[100,200][300,320]"


def load_state():
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text())
    return {{"tapped": False, "foreground": False}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state))


def emit_ui(state):
    if not state.get("foreground", False):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.google.android.apps.nexuslauncher" bounds="[0,0][1080,2400]">
    <node index="0" text="Pixel Launcher" resource-id="com.google.android.apps.nexuslauncher:id/home" class="android.widget.FrameLayout" package="com.google.android.apps.nexuslauncher" bounds="[0,0][1080,2400]" />
  </node>
</hierarchy>
'''
        sys.stdout.write(xml)
        return

    count = "Count: 1" if state.get("tapped", False) else "Count: 0"
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="hq.droussel.casgrain.smoke" bounds="[0,0][1080,2400]">
    <node index="0" text="{{count}}" resource-id="hq.droussel.casgrain.smoke:id/count_label" class="android.widget.TextView" package="hq.droussel.casgrain.smoke" content-desc="count-label" bounds="[100,80][500,160]" />
    <node index="1" text="Tap once" resource-id="hq.droussel.casgrain.smoke:id/tap_button" class="android.widget.Button" package="hq.droussel.casgrain.smoke" content-desc="tap-button" bounds="{{BOUNDS}}" />
  </node>
</hierarchy>
'''
    sys.stdout.write(xml)


def main():
    args = sys.argv[1:]
    state = load_state()

    if args == ["wait-for-device"]:
        return 0
    if args == ["get-state"]:
        print("device")
        return 0
    if args == ["shell", "getprop", "sys.boot_completed"]:
        print("1")
        return 0
    if args == ["shell", "getprop", "dev.bootcomplete"]:
        print("1")
        return 0
    if args == ["shell", "pm", "path", "android"]:
        print("package:android")
        return 0
    if args == ["shell", "getprop", "ro.product.model"]:
        print("Pixel 8")
        return 0
    if args == ["shell", "getprop", "ro.build.version.release"]:
        print("15")
        return 0
    if len(args) == 3 and args[0] == "install" and args[1] == "-r":
        print("Success")
        return 0
    if len(args) == 4 and args[:3] == ["shell", "am", "force-stop"]:
        return 0
    if len(args) == 4 and args[:3] == ["shell", "pm", "clear"]:
        state["tapped"] = False
        state["foreground"] = False
        save_state(state)
        print("Success")
        return 0
    if args == ["shell", "am", "start", "-W", "-n", "hq.droussel.casgrain.smoke/.MainActivity"]:
        state["foreground"] = True
        save_state(state)
        print("Status: ok")
        return 0
    if args == ["shell", "dumpsys", "window", "windows"]:
        if state.get("foreground", False):
            print("mCurrentFocus=Window{{42 u0 hq.droussel.casgrain.smoke/hq.droussel.casgrain.smoke.MainActivity}}")
        else:
            print("mCurrentFocus=Window{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}}")
        return 0
    if args == ["shell", "dumpsys", "activity", "activities"]:
        if state.get("foreground", False):
            print("ResumedActivity: ActivityRecord{{42 u0 hq.droussel.casgrain.smoke/.MainActivity t12}}")
        else:
            print("ResumedActivity: ActivityRecord{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}}")
        return 0
    if args[:2] == ["shell", "monkey"]:
        print("Events injected: 1")
        return 0
    if args == ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]:
        print("UI hierchary dumped to: /sdcard/window_dump.xml")
        return 0
    if args == ["exec-out", "cat", "/sdcard/window_dump.xml"]:
        emit_ui(state)
        return 0
    if len(args) == 5 and args[:3] == ["shell", "input", "tap"]:
        state["tapped"] = True
        save_state(state)
        return 0
    if args == ["exec-out", "screencap", "-p"]:
        sys.stdout.buffer.write(b"\x89PNG\r\n\x1a\nFAKE")
        return 0

    print(f"unsupported fake adb command: {{args}}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
"##,
            state_path = repo_root.join("adb-state.json")
        ),
    )
    .expect("fake adb should be written");
    let mut permissions = fs::metadata(&adb)
        .expect("adb metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&adb, permissions).expect("adb should be executable");
    adb
}

pub(crate) fn install_never_foregrounds_adb(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let adb = repo_root.join("never-foreground-adb.py");
    fs::write(
        &adb,
        format!(
            r##"#!/usr/bin/env python3
import json
import sys
from pathlib import Path

STATE_PATH = Path({state_path:?})


def load_state():
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text())
    return {{"foreground": False}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state))


def main():
    args = sys.argv[1:]
    state = load_state()

    if args == ["wait-for-device"]:
        return 0
    if args == ["get-state"]:
        print("device")
        return 0
    if args == ["shell", "getprop", "sys.boot_completed"]:
        print("1")
        return 0
    if args == ["shell", "getprop", "dev.bootcomplete"]:
        print("1")
        return 0
    if args == ["shell", "pm", "path", "android"]:
        print("package:android")
        return 0
    if len(args) == 3 and args[0] == "install" and args[1] == "-r":
        print("Success")
        return 0
    if len(args) == 4 and args[:3] == ["shell", "am", "force-stop"]:
        return 0
    if len(args) == 4 and args[:3] == ["shell", "pm", "clear"]:
        state["foreground"] = False
        save_state(state)
        print("Success")
        return 0
    if args == ["shell", "am", "start", "-W", "-n", "hq.droussel.casgrain.smoke/.MainActivity"]:
        print("Status: ok")
        return 0
    if args == ["shell", "dumpsys", "window", "windows"]:
        print("mCurrentFocus=Window{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}}")
        return 0
    if args == ["shell", "dumpsys", "activity", "activities"]:
        print("ResumedActivity: ActivityRecord{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}}")
        return 0

    print(f"unsupported never-foreground fake adb command: {{args}}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
"##,
            state_path = repo_root.join("never-foreground-adb-state.json")
        ),
    )
    .expect("never-foreground fake adb should be written");
    let mut permissions = fs::metadata(&adb)
        .expect("adb metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&adb, permissions).expect("adb should be executable");
    adb
}

pub(crate) fn install_misleading_foreground_adb(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let adb = repo_root.join("misleading-foreground-adb.py");
    fs::write(
        &adb,
        format!(
            r##"#!/usr/bin/env python3
import json
import sys
from pathlib import Path

STATE_PATH = Path({state_path:?})


def load_state():
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text())
    return {{"launched": False}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state))


def main():
    args = sys.argv[1:]
    state = load_state()

    if args == ["wait-for-device"]:
        return 0
    if args == ["get-state"]:
        print("device")
        return 0
    if args == ["shell", "getprop", "sys.boot_completed"]:
        print("1")
        return 0
    if args == ["shell", "getprop", "dev.bootcomplete"]:
        print("1")
        return 0
    if args == ["shell", "pm", "path", "android"]:
        print("package:android")
        return 0
    if len(args) == 3 and args[0] == "install" and args[1] == "-r":
        print("Success")
        return 0
    if len(args) == 4 and args[:3] == ["shell", "am", "force-stop"]:
        return 0
    if len(args) == 4 and args[:3] == ["shell", "pm", "clear"]:
        state["launched"] = False
        save_state(state)
        print("Success")
        return 0
    if args == ["shell", "am", "start", "-W", "-n", "hq.droussel.casgrain.smoke/.MainActivity"]:
        state["launched"] = True
        save_state(state)
        print("Status: ok")
        return 0
    if args == ["shell", "dumpsys", "window", "windows"]:
        print("mCurrentFocus=Window{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}}")
        return 0
    if args == ["shell", "dumpsys", "activity", "activities"]:
        if state.get("launched", False):
            print("ResumedActivity: ActivityRecord{{42 u0 hq.droussel.casgrain.smoke/.MainActivity t12}}")
        else:
            print("ResumedActivity: ActivityRecord{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}}")
        return 0

    print(f"unsupported misleading-foreground fake adb command: {{args}}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
"##,
            state_path = repo_root.join("misleading-foreground-adb-state.json")
        ),
    )
    .expect("misleading-foreground fake adb should be written");
    let mut permissions = fs::metadata(&adb)
        .expect("adb metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&adb, permissions).expect("adb should be executable");
    adb
}

pub(crate) fn install_foreign_anr_overlay_adb(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let adb = repo_root.join("foreign-anr-overlay-adb.py");
    fs::write(
        &adb,
        format!(
            r##"#!/usr/bin/env python3
import json
import sys
from pathlib import Path

STATE_PATH = Path({state_path:?})
WAIT_BOUNDS = "[70,1300][1010,1426]"
TAP_BOUNDS = "[100,200][300,320]"


def load_state():
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text())
    return {{"foreground": False, "tapped": False, "anr_open": False}}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state))


def emit_ui(state):
    if state.get("anr_open", False):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="android" bounds="[28,983][1052,1489]">
    <node index="0" text="Pixel Launcher isn't responding" resource-id="android:id/alertTitle" class="android.widget.TextView" package="android" bounds="[133,1072][947,1135]" />
    <node index="1" text="Close app" resource-id="android:id/aerr_close" class="android.widget.Button" package="android" clickable="true" bounds="[70,1174][1010,1300]" />
    <node index="2" text="Wait" resource-id="android:id/aerr_wait" class="android.widget.Button" package="android" clickable="true" bounds="[70,1300][1010,1426]" />
  </node>
</hierarchy>
'''
        sys.stdout.write(xml)
        return

    count = "Count: 1" if state.get("tapped", False) else "Count: 0"
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="hq.droussel.casgrain.smoke" bounds="[0,0][1080,2400]">
    <node index="0" text="{{count}}" resource-id="hq.droussel.casgrain.smoke:id/count_label" class="android.widget.TextView" package="hq.droussel.casgrain.smoke" content-desc="count-label" bounds="[100,80][500,160]" />
    <node index="1" text="Tap once" resource-id="hq.droussel.casgrain.smoke:id/tap_button" class="android.widget.Button" package="hq.droussel.casgrain.smoke" content-desc="tap-button" clickable="true" bounds="[100,200][300,320]" />
  </node>
</hierarchy>
'''
    sys.stdout.write(xml)


def main():
    args = sys.argv[1:]
    state = load_state()

    if args == ["wait-for-device"]:
        return 0
    if args == ["get-state"]:
        print("device")
        return 0
    if args == ["shell", "getprop", "sys.boot_completed"]:
        print("1")
        return 0
    if args == ["shell", "getprop", "dev.bootcomplete"]:
        print("1")
        return 0
    if args == ["shell", "pm", "path", "android"]:
        print("package:android")
        return 0
    if args == ["shell", "getprop", "ro.product.model"]:
        print("Pixel 8")
        return 0
    if args == ["shell", "getprop", "ro.build.version.release"]:
        print("15")
        return 0
    if len(args) == 3 and args[0] == "install" and args[1] == "-r":
        print("Success")
        return 0
    if len(args) == 4 and args[:3] == ["shell", "am", "force-stop"]:
        return 0
    if len(args) == 4 and args[:3] == ["shell", "pm", "clear"]:
        state["foreground"] = False
        state["tapped"] = False
        state["anr_open"] = False
        save_state(state)
        print("Success")
        return 0
    if args == ["shell", "am", "start", "-W", "-n", "hq.droussel.casgrain.smoke/.MainActivity"]:
        state["foreground"] = True
        state["anr_open"] = True
        save_state(state)
        print("Status: ok")
        return 0
    if args == ["shell", "dumpsys", "window", "windows"]:
        if state.get("anr_open", False):
            print("mCurrentFocus=Window{{42 u0 Application Not Responding: com.google.android.apps.nexuslauncher}}")
        elif state.get("foreground", False):
            print("mCurrentFocus=Window{{42 u0 hq.droussel.casgrain.smoke/hq.droussel.casgrain.smoke.MainActivity}}")
        else:
            print("mCurrentFocus=Window{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity}}")
        return 0
    if args == ["shell", "dumpsys", "activity", "activities"]:
        if state.get("foreground", False):
            print("ResumedActivity: ActivityRecord{{42 u0 hq.droussel.casgrain.smoke/.MainActivity t12}}")
        else:
            print("ResumedActivity: ActivityRecord{{42 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}}")
        return 0
    if args == ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]:
        print("UI hierchary dumped to: /sdcard/window_dump.xml")
        return 0
    if args == ["exec-out", "cat", "/sdcard/window_dump.xml"]:
        emit_ui(state)
        return 0
    if len(args) == 5 and args[:3] == ["shell", "input", "tap"]:
        if state.get("anr_open", False):
            state["anr_open"] = False
        else:
            state["tapped"] = True
        save_state(state)
        return 0
    if args == ["exec-out", "screencap", "-p"]:
        sys.stdout.buffer.write(b"\x89PNG\r\n\x1a\nFAKE")
        return 0

    print(f"unsupported foreign-anr fake adb command: {{args}}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
"##,
            state_path = repo_root.join("foreign-anr-overlay-adb-state.json")
        ),
    )
    .expect("foreign-anr fake adb should be written");
    let mut permissions = fs::metadata(&adb)
        .expect("adb metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&adb, permissions).expect("adb should be executable");
    adb
}

pub(crate) fn install_slow_wait_adb(repo_root: &Path) -> PathBuf {
    fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
    let adb = repo_root.join("slow-adb.py");
    fs::write(
        &adb,
        r#"#!/usr/bin/env python3
import sys
import time

if sys.argv[1:] == ["wait-for-device"]:
    time.sleep(1)
    raise SystemExit(0)

print(f"unexpected slow fake adb command: {sys.argv[1:]}", file=sys.stderr)
raise SystemExit(1)
"#,
    )
    .expect("slow fake adb should be written");
    let mut permissions = fs::metadata(&adb)
        .expect("adb metadata should exist")
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(&adb, permissions).expect("adb should be executable");
    adb
}

pub(crate) fn temp_path(prefix: &str) -> PathBuf {
    std::env::temp_dir().join(format!(
        "{prefix}-{}",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time should move forward")
            .as_nanos()
    ))
}

pub(crate) fn env_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}
