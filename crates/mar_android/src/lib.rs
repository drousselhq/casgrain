use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

use mar_domain::{
    ActionKind, AssertionKind, ExecutablePlan, ExecutionTrace, FailureCode, RuntimeFailure,
    Selector, TargetPlatform,
};

const ANDROID_SMOKE_RUNNER_ENV: &str = "CASGRAIN_ANDROID_SMOKE_RUNNER";
const ANDROID_SMOKE_ARTIFACT_DIR_ENV: &str = "CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR";
const REPO_ROOT_ENV: &str = "CASGRAIN_REPO_ROOT";
const DEFAULT_SMOKE_SCRIPT: &str = "scripts/android_smoke_run_plan.py";

pub fn run_smoke_fixture_plan(plan: &ExecutablePlan) -> Result<ExecutionTrace, RuntimeFailure> {
    validate_supported_smoke_plan(plan)?;

    let repo_root = resolve_repo_root()?;
    let artifact_dir = resolve_artifact_dir(&repo_root, &plan.plan_id);
    fs::create_dir_all(&artifact_dir).map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!(
            "failed to create Android smoke artifact directory {}: {error}",
            artifact_dir.display()
        ),
    })?;

    let plan_path = artifact_dir.join("plan.json");
    fs::write(
        &plan_path,
        serde_json::to_vec_pretty(plan).expect("fixture plan should serialize"),
    )
    .map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!(
            "failed to write Android fixture plan {}: {error}",
            plan_path.display()
        ),
    })?;

    let mut command = build_smoke_command(&repo_root, &plan_path, &artifact_dir)?;
    let output = command.output().map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!("failed to launch Android smoke runner: {error}"),
    })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let details = if !stderr.is_empty() {
            stderr
        } else if !stdout.is_empty() {
            stdout
        } else {
            format!("runner exited with status {}", output.status)
        };

        return Err(RuntimeFailure {
            code: FailureCode::EngineError,
            message: format!("Android smoke runner failed: {details}"),
        });
    }

    serde_json::from_slice::<ExecutionTrace>(&output.stdout).map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!("Android smoke runner returned invalid trace JSON: {error}"),
    })
}

fn resolve_repo_root() -> Result<PathBuf, RuntimeFailure> {
    if let Ok(root) = env::var(REPO_ROOT_ENV) {
        return Ok(PathBuf::from(root));
    }

    let current_dir = env::current_dir().map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!("failed to resolve current working directory: {error}"),
    })?;

    for candidate in current_dir.ancestors() {
        if candidate.join("Cargo.toml").is_file() && candidate.join(DEFAULT_SMOKE_SCRIPT).is_file()
        {
            return Ok(candidate.to_path_buf());
        }
    }

    Err(RuntimeFailure {
        code: FailureCode::EngineError,
        message: String::from(
            "failed to locate repository root; set CASGRAIN_REPO_ROOT to a checkout containing scripts/android_smoke_run_plan.py",
        ),
    })
}

fn resolve_artifact_dir(repo_root: &Path, plan_id: &str) -> PathBuf {
    env::var(ANDROID_SMOKE_ARTIFACT_DIR_ENV)
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            repo_root
                .join("artifacts")
                .join("android-smoke-generated")
                .join(plan_id)
        })
}

fn build_smoke_command(
    repo_root: &Path,
    plan_path: &Path,
    artifact_dir: &Path,
) -> Result<Command, RuntimeFailure> {
    if let Ok(runner) = env::var(ANDROID_SMOKE_RUNNER_ENV) {
        let mut command = Command::new(runner);
        command.arg("--repo-root").arg(repo_root);
        command.arg("--plan").arg(plan_path);
        command.arg("--artifact-dir").arg(artifact_dir);
        return Ok(command);
    }

    let script_path = repo_root.join(DEFAULT_SMOKE_SCRIPT);
    if !script_path.is_file() {
        return Err(RuntimeFailure {
            code: FailureCode::EngineError,
            message: format!(
                "missing Android smoke runner script at {}",
                script_path.display()
            ),
        });
    }

    let mut command = Command::new("python3");
    command.arg(script_path);
    command.arg("--repo-root").arg(repo_root);
    command.arg("--plan").arg(plan_path);
    command.arg("--artifact-dir").arg(artifact_dir);
    Ok(command)
}

fn validate_supported_smoke_plan(plan: &ExecutablePlan) -> Result<(), RuntimeFailure> {
    if plan.target.platform != TargetPlatform::Android {
        return Err(unsupported_fixture_plan(
            "fixture bridge only supports Android-targeted plans",
        ));
    }

    if plan.target.device_class != "emulator" {
        return Err(unsupported_fixture_plan(
            "fixture bridge currently supports emulator-targeted plans only",
        ));
    }

    let [launch_step, tap_step, assert_step, screenshot_step] = plan.steps.as_slice() else {
        return Err(unsupported_fixture_plan(
            "fixture bridge currently supports exactly four tap-counter steps",
        ));
    };

    match &launch_step.action {
        ActionKind::LaunchApp { app_id } if app_id == "app.under.test" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "first smoke step must launch the fixture app",
            ));
        }
    }

    match launch_step.postconditions.as_slice() {
        [AssertionKind::AppInForeground { app_id }] if app_id == "app.under.test" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "launch step must assert the fixture app is in the foreground",
            ));
        }
    }

    match &tap_step.action {
        ActionKind::Tap {
            target: Selector::AccessibilityId(value),
        } if value == "tap-button" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "second smoke step must tap accessibility id tap-button",
            ));
        }
    }

    if !tap_step.postconditions.is_empty() {
        return Err(unsupported_fixture_plan(
            "tap step must rely on the later assertion instead of extra postconditions",
        ));
    }

    if !matches!(assert_step.action, ActionKind::Noop) {
        return Err(unsupported_fixture_plan(
            "third smoke step must be an assertion-only noop action",
        ));
    }

    match assert_step.postconditions.as_slice() {
        [AssertionKind::TextEquals {
            target: Selector::AccessibilityId(value),
            value: expected_text,
        }] if value == "count-label" && expected_text == "Count: 1" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "assert step must verify accessibility id count-label equals Count: 1",
            ));
        }
    }

    match &screenshot_step.action {
        ActionKind::TakeScreenshot { name } if name.as_deref() == Some("android-tap-counter") => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "final smoke step must capture screenshot android-tap-counter",
            ));
        }
    }

    Ok(())
}

fn unsupported_fixture_plan(message: &str) -> RuntimeFailure {
    RuntimeFailure {
        code: FailureCode::UnsupportedAction,
        message: message.into(),
    }
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        os::unix::fs::PermissionsExt,
        path::PathBuf,
        sync::{Mutex, OnceLock},
        time::{SystemTime, UNIX_EPOCH},
    };

    use super::*;
    use mar_domain::{
        ArtifactPolicy, CapabilitySet, ExecutionDefaults, FailurePolicy, PlanFormatVersion,
        PlanSource, PlanStep, RetryPolicy, SourceKind, StepIntent, TargetProfile,
    };

    #[test]
    fn run_smoke_fixture_plan_writes_plan_and_reads_trace() {
        let repo_root = temp_path("casgrain-android-repo");
        let artifact_dir = temp_path("casgrain-android-artifacts");
        let runner = install_fake_android_smoke_runner(&repo_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_RUNNER", &runner);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let trace = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect("android smoke plan should execute through injected runner");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        }

        assert_eq!(trace.run_id, "android-smoke-increment-the-counter-once");
        assert_eq!(trace.device.platform, TargetPlatform::Android);
        assert_eq!(trace.artifacts[0].artifact_type, "screenshot");
        assert!(artifact_dir.join("plan.json").is_file());
    }

    #[test]
    fn smoke_plan_validation_rejects_non_android_target() {
        let mut plan = supported_smoke_plan();
        plan.target.platform = TargetPlatform::Ios;
        let error = validate_supported_smoke_plan(&plan).expect_err("non-android plan should fail");
        assert_eq!(error.code, FailureCode::UnsupportedAction);
        assert!(error.message.contains("Android-targeted"));
    }

    #[test]
    fn smoke_plan_validation_rejects_non_emulator_target() {
        let mut plan = supported_smoke_plan();
        plan.target.device_class = "simulator".into();
        let error =
            validate_supported_smoke_plan(&plan).expect_err("non-emulator plan should fail");
        assert_eq!(error.code, FailureCode::UnsupportedAction);
        assert!(error.message.contains("emulator-targeted"));
    }

    #[test]
    fn default_script_executes_fixture_plan_via_fake_adb() {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let artifact_dir = temp_path("casgrain-android-default-script-artifacts");
        let apk_path = temp_path("casgrain-android-fixture-apk").with_extension("apk");
        let fake_adb_root = temp_path("casgrain-android-fake-adb");
        fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
        fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
        let adb = install_fake_adb(&fake_adb_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
            std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        let trace = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect("default script should execute through fake adb harness");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
            std::env::remove_var("CASGRAIN_ANDROID_ADB");
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        assert_eq!(trace.run_id, "android-smoke-increment-the-counter-once");
        assert_eq!(trace.device.platform, TargetPlatform::Android);
        assert_eq!(trace.device.name, "Pixel 8");
        assert_eq!(trace.device.os_version, "15");
        assert!(artifact_dir.join("plan.json").is_file());
        assert!(artifact_dir.join("android-tap-counter-1.png").is_file());
        assert!(artifact_dir.join("emulator.json").is_file());
        assert!(artifact_dir.join("ui-before-tap.xml").is_file());
        assert!(artifact_dir.join("ui-after-tap.xml").is_file());
        assert_eq!(trace.artifacts[0].artifact_type, "screenshot");
    }

    #[test]
    fn default_script_is_repeatable_against_the_same_fake_adb_state() {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let artifact_dir_one = temp_path("casgrain-android-repeat-artifacts-one");
        let artifact_dir_two = temp_path("casgrain-android-repeat-artifacts-two");
        let apk_path = temp_path("casgrain-android-repeat-apk").with_extension("apk");
        let fake_adb_root = temp_path("casgrain-android-repeat-adb");
        fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
        fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
        let adb = install_fake_adb(&fake_adb_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir_one);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
            std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        run_smoke_fixture_plan(&supported_smoke_plan()).expect("first fake adb run should succeed");

        unsafe {
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir_two);
        }

        let second_trace = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect("second fake adb run should also succeed after state reset");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
            std::env::remove_var("CASGRAIN_ANDROID_ADB");
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        assert_eq!(second_trace.status, mar_domain::RunStatus::Passed);
        assert!(artifact_dir_one.join("android-tap-counter-1.png").is_file());
        assert!(artifact_dir_two.join("android-tap-counter-1.png").is_file());
    }

    #[test]
    fn default_script_fails_fast_when_device_never_becomes_ready() {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let artifact_dir = temp_path("casgrain-android-timeout-artifacts");
        let apk_path = temp_path("casgrain-android-timeout-apk").with_extension("apk");
        let fake_adb_root = temp_path("casgrain-android-timeout-adb");
        fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
        fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
        let adb = install_slow_wait_adb(&fake_adb_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
            std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
            std::env::set_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS", "0.1");
        }

        let error = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect_err("default script should fail fast when no device becomes ready");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
            std::env::remove_var("CASGRAIN_ANDROID_ADB");
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        assert_eq!(error.code, FailureCode::EngineError);
        assert!(error.message.contains("wait-for-device timed out"));
    }

    #[test]
    fn default_script_fails_when_fixture_app_never_reaches_foreground() {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let artifact_dir = temp_path("casgrain-android-foreground-timeout-artifacts");
        let apk_path = temp_path("casgrain-android-foreground-timeout-apk").with_extension("apk");
        let fake_adb_root = temp_path("casgrain-android-foreground-timeout-adb");
        fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
        fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
        let adb = install_never_foregrounds_adb(&fake_adb_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
            std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
            std::env::set_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS", "0.1");
        }

        let error = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect_err("default script should fail when the fixture app never becomes foreground");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
            std::env::remove_var("CASGRAIN_ANDROID_ADB");
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        assert_eq!(error.code, FailureCode::EngineError);
        assert!(error.message.contains("did not reach the foreground"));
        assert!(error.message.contains("mCurrentFocus"));
        assert!(error
            .message
            .contains("com.google.android.apps.nexuslauncher"));
    }

    #[test]
    fn default_script_honors_explicit_activity_component_override() {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let artifact_dir = temp_path("casgrain-android-explicit-activity-artifacts");
        let apk_path = temp_path("casgrain-android-explicit-activity-apk").with_extension("apk");
        let fake_adb_root = temp_path("casgrain-android-explicit-activity-adb");
        fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
        fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
        let adb = install_fake_adb(&fake_adb_root);
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
            std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
            std::env::set_var(
                "CASGRAIN_ANDROID_SMOKE_ACTIVITY",
                "hq.droussel.casgrain.smoke/.MainActivity",
            );
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        let trace = run_smoke_fixture_plan(&supported_smoke_plan())
            .expect("default script should accept an explicit launch component override");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
            std::env::remove_var("CASGRAIN_ANDROID_ADB");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ACTIVITY");
            std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        }

        assert_eq!(trace.status, mar_domain::RunStatus::Passed);
    }

    fn supported_smoke_plan() -> ExecutablePlan {
        ExecutablePlan {
            plan_id: "increment-the-counter-once".into(),
            name: "Increment the counter once".into(),
            version: PlanFormatVersion { major: 1, minor: 0 },
            source: PlanSource {
                kind: SourceKind::Gherkin,
                source_name: "fixtures/android-smoke/features/tap_counter.feature".into(),
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

    fn install_fake_android_smoke_runner(repo_root: &Path) -> PathBuf {
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

    fn install_fake_adb(repo_root: &Path) -> PathBuf {
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

    fn install_never_foregrounds_adb(repo_root: &Path) -> PathBuf {
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

    fn install_slow_wait_adb(repo_root: &Path) -> PathBuf {
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

    fn temp_path(prefix: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "{prefix}-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("time should move forward")
                .as_nanos()
        ))
    }

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }
}
