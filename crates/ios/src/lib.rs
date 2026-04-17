use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

use domain::{
    ActionKind, ArtifactRef, AssertionKind, DeviceDescriptor, DeviceEngine, DeviceSnapshot,
    ExecutablePlan, ExecutionTrace, FailureCode, ObservedElement, RuntimeFailure, Selector,
    StringMatchKind, TargetPlatform, UiRole,
};

const IOS_SMOKE_RUNNER_ENV: &str = "CASGRAIN_IOS_SMOKE_RUNNER";
const IOS_SMOKE_ARTIFACT_DIR_ENV: &str = "CASGRAIN_IOS_SMOKE_ARTIFACT_DIR";
const REPO_ROOT_ENV: &str = "CASGRAIN_REPO_ROOT";
const DEFAULT_SMOKE_SCRIPT: &str = "tests/test-support/scripts/ios_smoke_run_plan.py";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IosSimulatorDescriptor {
    pub name: String,
    pub os_version: String,
}

impl IosSimulatorDescriptor {
    pub fn new(name: impl Into<String>, os_version: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            os_version: os_version.into(),
        }
    }

    pub fn iphone_16() -> Self {
        Self::new("iPhone 16", "18.0")
    }

    fn into_device_descriptor(self) -> DeviceDescriptor {
        DeviceDescriptor {
            platform: TargetPlatform::Ios,
            name: self.name,
            os_version: self.os_version,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IosSimulatorSnapshot {
    pub descriptor: DeviceDescriptor,
    pub device_snapshot: DeviceSnapshot,
}

impl IosSimulatorSnapshot {
    pub fn new(descriptor: DeviceDescriptor, device_snapshot: DeviceSnapshot) -> Self {
        Self {
            descriptor,
            device_snapshot,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FixtureMode {
    Login,
    TapCounterSmoke,
}

#[derive(Debug, Clone)]
pub struct IosSimulatorAdapter {
    descriptor: DeviceDescriptor,
    snapshot: DeviceSnapshot,
    screenshot_counter: u32,
    fixture_mode: FixtureMode,
    tap_count: u32,
}

impl IosSimulatorAdapter {
    pub fn new(descriptor: IosSimulatorDescriptor) -> Self {
        Self {
            descriptor: descriptor.into_device_descriptor(),
            snapshot: login_fixture_snapshot(),
            screenshot_counter: 0,
            fixture_mode: FixtureMode::Login,
            tap_count: 0,
        }
    }

    pub fn smoke_fixture(descriptor: IosSimulatorDescriptor) -> Self {
        Self {
            descriptor: descriptor.into_device_descriptor(),
            snapshot: tap_counter_fixture_snapshot(),
            screenshot_counter: 0,
            fixture_mode: FixtureMode::TapCounterSmoke,
            tap_count: 0,
        }
    }

    pub fn snapshot(&self) -> Result<IosSimulatorSnapshot, RuntimeFailure> {
        Ok(IosSimulatorSnapshot::new(
            self.descriptor.clone(),
            self.snapshot.clone(),
        ))
    }

    fn ensure_home_screen(&mut self) {
        let already_present = self
            .snapshot
            .elements
            .iter()
            .any(|element| element.accessibility_id.as_deref() == Some("home_title"));

        if !already_present {
            self.snapshot.elements.push(ObservedElement {
                resource_id: None,
                accessibility_id: Some("home_title".into()),
                role: Some(UiRole::StaticText),
                text: Some("Home".into()),
                label: Some("Home".into()),
                visible: true,
            });
        }
    }

    fn update_tap_counter_label(&mut self) {
        let value = format!("Count: {}", self.tap_count);
        if let Some(element) = self
            .snapshot
            .elements
            .iter_mut()
            .find(|element| element.accessibility_id.as_deref() == Some("count-label"))
        {
            element.text = Some(value.clone());
            element.label = Some(value);
            element.visible = true;
            return;
        }

        self.snapshot.elements.push(ObservedElement {
            resource_id: None,
            accessibility_id: Some("count-label".into()),
            role: Some(UiRole::StaticText),
            text: Some(value.clone()),
            label: Some(value),
            visible: true,
        });
    }
}

pub fn run_smoke_fixture_plan(plan: &ExecutablePlan) -> Result<ExecutionTrace, RuntimeFailure> {
    validate_supported_smoke_plan(plan)?;

    let repo_root = resolve_repo_root()?;
    let artifact_dir = resolve_artifact_dir(&repo_root, &plan.plan_id);
    fs::create_dir_all(&artifact_dir).map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!(
            "failed to create iOS smoke artifact directory {}: {error}",
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
            "failed to write fixture plan {}: {error}",
            plan_path.display()
        ),
    })?;

    let mut command = build_smoke_command(&repo_root, &plan_path, &artifact_dir)?;
    let output = command.output().map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!("failed to launch iOS smoke runner: {error}"),
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
            message: format!("real iOS smoke harness failed: {details}"),
        });
    }

    serde_json::from_slice::<ExecutionTrace>(&output.stdout).map_err(|error| RuntimeFailure {
        code: FailureCode::EngineError,
        message: format!("iOS smoke runner returned invalid trace JSON: {error}"),
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
            "failed to locate repository root; set CASGRAIN_REPO_ROOT to a checkout containing tests/test-support/scripts/ios_smoke_run_plan.py",
        ),
    })
}

fn resolve_artifact_dir(repo_root: &Path, plan_id: &str) -> PathBuf {
    env::var(IOS_SMOKE_ARTIFACT_DIR_ENV)
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            repo_root
                .join("artifacts")
                .join("ios-smoke-generated")
                .join(plan_id)
        })
}

fn build_smoke_command(
    repo_root: &Path,
    plan_path: &Path,
    artifact_dir: &Path,
) -> Result<Command, RuntimeFailure> {
    if let Ok(runner) = env::var(IOS_SMOKE_RUNNER_ENV) {
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
                "missing iOS smoke runner script at {}",
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
    if plan.target.platform != TargetPlatform::Ios {
        return Err(unsupported_fixture_plan(
            "fixture bridge only supports iOS-targeted plans",
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
        ActionKind::TakeScreenshot { name } if name.as_deref() == Some("tap-counter") => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "final smoke step must capture screenshot tap-counter",
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

impl DeviceEngine for IosSimulatorAdapter {
    fn descriptor(&self) -> DeviceDescriptor {
        self.descriptor.clone()
    }

    fn perform_action(&mut self, action: &ActionKind) -> Result<Vec<ArtifactRef>, RuntimeFailure> {
        match action {
            ActionKind::Noop => Ok(Vec::new()),
            ActionKind::LaunchApp { app_id } => {
                self.snapshot.foreground_app = Some(app_id.clone());
                Ok(Vec::new())
            }
            ActionKind::OpenDeepLink { url } => {
                self.snapshot.foreground_app = Some("app.under.test".into());
                if url.to_lowercase().contains("home") {
                    self.ensure_home_screen();
                }
                Ok(Vec::new())
            }
            ActionKind::Tap { target } => {
                let tapped_element =
                    find_element(&self.snapshot, target)
                        .cloned()
                        .ok_or(RuntimeFailure {
                            code: FailureCode::UnresolvedSelector,
                            message: format!("selector was not found: {target:?}"),
                        })?;
                let tapped_label = tapped_element
                    .label
                    .clone()
                    .or_else(|| tapped_element.text.clone())
                    .unwrap_or_default();

                if tapped_label.to_lowercase().contains("login") {
                    self.ensure_home_screen();
                }

                if self.fixture_mode == FixtureMode::TapCounterSmoke
                    && tapped_element.accessibility_id.as_deref() == Some("tap-button")
                {
                    self.tap_count += 1;
                    self.update_tap_counter_label();
                }

                Ok(Vec::new())
            }
            ActionKind::TypeText { target, text } => {
                let element = self
                    .snapshot
                    .elements
                    .iter_mut()
                    .find(|element| element_matches_selector(element, target))
                    .ok_or(RuntimeFailure {
                        code: FailureCode::UnresolvedSelector,
                        message: format!("selector was not found: {target:?}"),
                    })?;
                element.text = Some(text.clone());
                Ok(Vec::new())
            }
            ActionKind::TakeScreenshot { name } => {
                self.screenshot_counter += 1;
                let base = sanitize_artifact_name(name.as_deref());
                Ok(vec![ArtifactRef {
                    artifact_id: format!("{base}-{}", self.screenshot_counter),
                    artifact_type: "screenshot".into(),
                    path: format!("artifacts/{base}-{}.png", self.screenshot_counter),
                    sha256: None,
                    step_id: None,
                }])
            }
        }
    }

    fn snapshot(&self) -> Result<DeviceSnapshot, RuntimeFailure> {
        Ok(self.snapshot.clone())
    }
}

fn login_fixture_snapshot() -> DeviceSnapshot {
    DeviceSnapshot {
        elements: vec![
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("login_button".into()),
                role: Some(UiRole::Button),
                text: Some("Login".into()),
                label: Some("Login".into()),
                visible: true,
            },
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("email_field".into()),
                role: Some(UiRole::TextField),
                text: Some(String::new()),
                label: Some("Email".into()),
                visible: true,
            },
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("password_field".into()),
                role: Some(UiRole::TextField),
                text: Some(String::new()),
                label: Some("Password".into()),
                visible: true,
            },
        ],
        foreground_app: None,
    }
}

fn tap_counter_fixture_snapshot() -> DeviceSnapshot {
    DeviceSnapshot {
        elements: vec![
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("tap-button".into()),
                role: Some(UiRole::Button),
                text: Some("Tap".into()),
                label: Some("Tap".into()),
                visible: true,
            },
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("count-label".into()),
                role: Some(UiRole::StaticText),
                text: Some("Count: 0".into()),
                label: Some("Count: 0".into()),
                visible: true,
            },
        ],
        foreground_app: None,
    }
}

fn sanitize_artifact_name(name: Option<&str>) -> String {
    let sanitized = name
        .unwrap_or("screenshot")
        .trim()
        .chars()
        .map(|character| match character {
            'a'..='z' | 'A'..='Z' | '0'..='9' | '-' | '_' => character,
            _ => '-',
        })
        .collect::<String>()
        .trim_matches('-')
        .to_string();

    if sanitized.is_empty() {
        String::from("screenshot")
    } else {
        sanitized
    }
}

fn find_element<'a>(
    snapshot: &'a DeviceSnapshot,
    selector: &Selector,
) -> Option<&'a ObservedElement> {
    snapshot
        .elements
        .iter()
        .find(|element| element_matches_selector(element, selector))
}

fn element_matches_selector(element: &ObservedElement, selector: &Selector) -> bool {
    match selector {
        Selector::ResourceId(value) => element.resource_id.as_deref() == Some(value.as_str()),
        Selector::AccessibilityId(value) => {
            element.accessibility_id.as_deref() == Some(value.as_str())
        }
        Selector::Text(text) => match text.match_kind {
            StringMatchKind::Exact => element.text.as_deref() == Some(text.value.as_str()),
            StringMatchKind::Contains => {
                let needle = text.value.to_lowercase();
                element
                    .text
                    .as_deref()
                    .map(|candidate| candidate.to_lowercase().contains(&needle))
                    .unwrap_or(false)
                    || element
                        .label
                        .as_deref()
                        .map(|candidate| candidate.to_lowercase().contains(&needle))
                        .unwrap_or(false)
            }
        },
        Selector::Role(role) => {
            element.role.as_ref() == Some(&role.role)
                && role
                    .label
                    .as_ref()
                    .map(|label| element.label.as_deref() == Some(label.as_str()))
                    .unwrap_or(true)
        }
        Selector::Label(value) => element.label.as_deref() == Some(value.as_str()),
        Selector::AnyOf(items) => items
            .iter()
            .any(|item| element_matches_selector(element, item)),
        Selector::Placeholder(_)
        | Selector::Hint(_)
        | Selector::Trait(_)
        | Selector::Path(_)
        | Selector::Coordinate(_)
        | Selector::Platform(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use std::{
        collections::BTreeMap,
        fs,
        os::unix::fs::PermissionsExt,
        path::PathBuf,
        sync::{Mutex, OnceLock},
        time::{SystemTime, UNIX_EPOCH},
    };

    use domain::{
        ActionKind, ArtifactPolicy, AssertionKind, CapabilitySet, DeviceEngine, ExecutablePlan,
        ExecutionDefaults, FailureCode, FailurePolicy, PlanFormatVersion, PlanSource, PlanStep,
        RetryPolicy, Selector, SourceKind, StepIntent, TargetPlatform, TargetProfile,
    };

    use super::{
        run_smoke_fixture_plan, validate_supported_smoke_plan, IosSimulatorAdapter,
        IosSimulatorDescriptor, IOS_SMOKE_ARTIFACT_DIR_ENV, IOS_SMOKE_RUNNER_ENV, REPO_ROOT_ENV,
    };

    #[test]
    fn ios_adapter_exposes_descriptor_and_snapshot() {
        let adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());
        let descriptor = adapter.descriptor();
        assert_eq!(descriptor.platform, TargetPlatform::Ios);

        let snapshot = adapter.snapshot().expect("snapshot should succeed");
        assert_eq!(snapshot.descriptor.platform, TargetPlatform::Ios);
    }

    #[test]
    fn ios_adapter_handles_core_actions() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        adapter
            .perform_action(&ActionKind::LaunchApp {
                app_id: "app.under.test".into(),
            })
            .expect("launch should succeed");

        adapter
            .perform_action(&ActionKind::Tap {
                target: Selector::AccessibilityId("login_button".into()),
            })
            .expect("tap should succeed");

        adapter
            .perform_action(&ActionKind::TypeText {
                target: Selector::AccessibilityId("email_field".into()),
                text: "tester@example.com".into(),
            })
            .expect("type should succeed");

        let artifacts = adapter
            .perform_action(&ActionKind::TakeScreenshot {
                name: Some("login".into()),
            })
            .expect("screenshot should succeed");
        assert_eq!(artifacts.len(), 1);
        assert_eq!(artifacts[0].artifact_type, "screenshot");

        let snapshot = adapter.snapshot().expect("snapshot should succeed");
        assert_eq!(snapshot.descriptor.platform, TargetPlatform::Ios);
        assert!(snapshot
            .device_snapshot
            .elements
            .iter()
            .any(
                |element| element.accessibility_id.as_deref() == Some("email_field")
                    && element.text.as_deref() == Some("tester@example.com")
            ));
    }

    #[test]
    fn ios_smoke_fixture_tap_updates_counter_label() {
        let mut adapter = IosSimulatorAdapter::smoke_fixture(IosSimulatorDescriptor::iphone_16());

        adapter
            .perform_action(&ActionKind::LaunchApp {
                app_id: "app.under.test".into(),
            })
            .expect("launch should succeed");
        adapter
            .perform_action(&ActionKind::Tap {
                target: Selector::AccessibilityId("tap-button".into()),
            })
            .expect("tap should succeed");

        let snapshot = DeviceEngine::snapshot(&adapter).expect("snapshot should succeed");
        assert_eq!(snapshot.foreground_app.as_deref(), Some("app.under.test"));
        assert!(snapshot
            .elements
            .iter()
            .any(
                |element| element.accessibility_id.as_deref() == Some("count-label")
                    && element.text.as_deref() == Some("Count: 1")
            ));
    }

    #[test]
    fn ios_adapter_sanitizes_screenshot_names() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        let artifacts = adapter
            .perform_action(&ActionKind::TakeScreenshot {
                name: Some("../nested/login capture.png".into()),
            })
            .expect("screenshot should succeed");

        assert_eq!(artifacts[0].artifact_id, "nested-login-capture-png-1");
        assert_eq!(
            artifacts[0].path,
            "artifacts/nested-login-capture-png-1.png"
        );
    }

    #[test]
    fn ios_adapter_reports_unresolved_selectors() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        let error = adapter
            .perform_action(&ActionKind::Tap {
                target: Selector::AccessibilityId("missing_button".into()),
            })
            .expect_err("missing selector should fail");

        assert_eq!(error.code, FailureCode::UnresolvedSelector);
    }

    #[test]
    fn ios_adapter_open_deep_link_reveals_home_screen() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        adapter
            .perform_action(&ActionKind::OpenDeepLink {
                url: "casgrain://home".into(),
            })
            .expect("deep link should succeed");

        let snapshot = DeviceEngine::snapshot(&adapter).expect("snapshot should succeed");
        assert_eq!(snapshot.foreground_app.as_deref(), Some("app.under.test"));
        assert!(snapshot
            .elements
            .iter()
            .any(|element| element.accessibility_id.as_deref() == Some("home_title")));
    }

    #[test]
    fn smoke_fixture_plan_validation_accepts_canonical_shape() {
        validate_supported_smoke_plan(&smoke_fixture_plan())
            .expect("canonical tap-counter plan should be accepted");
    }

    #[test]
    fn smoke_fixture_plan_validation_rejects_non_canonical_shape() {
        let mut plan = smoke_fixture_plan();
        plan.steps.push(plan.steps[0].clone());

        let error = validate_supported_smoke_plan(&plan)
            .expect_err("extra step should be rejected for the fixture bridge");
        assert_eq!(error.code, FailureCode::UnsupportedAction);
        assert!(error.message.contains("exactly four"));
    }

    #[test]
    fn run_smoke_fixture_plan_uses_external_runner_override() {
        let repo_root = temp_path("casgrain-mar-ios-repo");
        let artifact_dir = temp_path("casgrain-mar-ios-artifacts");
        fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
        let _guard = env_lock().lock().expect("env lock should not be poisoned");

        let runner_path = repo_root.join("runner.py");
        fs::write(
            &runner_path,
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
(artifact_dir / "tap-counter-1.png").write_bytes(b"png")

print(json.dumps({
    "run_id": f"ios-smoke-{plan['plan_id']}",
    "plan_id": plan["plan_id"],
    "device": {
        "platform": "ios",
        "name": "iPhone 16",
        "os_version": "18.0"
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
            "artifact_id": "tap-counter-1",
            "artifact_type": "screenshot",
            "path": str(artifact_dir / "tap-counter-1.png"),
            "sha256": None,
            "step_id": plan["steps"][-1]["step_id"]
        }
    ],
    "diagnostics": []
}))
"#,
        )
        .expect("fake runner should be written");
        let mut permissions = fs::metadata(&runner_path)
            .expect("runner metadata should exist")
            .permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&runner_path, permissions).expect("runner should be executable");

        unsafe {
            std::env::set_var(REPO_ROOT_ENV, &repo_root);
            std::env::set_var(IOS_SMOKE_RUNNER_ENV, &runner_path);
            std::env::set_var(IOS_SMOKE_ARTIFACT_DIR_ENV, &artifact_dir);
        }

        let trace = run_smoke_fixture_plan(&smoke_fixture_plan())
            .expect("fake external runner should return trace JSON");

        unsafe {
            std::env::remove_var(REPO_ROOT_ENV);
            std::env::remove_var(IOS_SMOKE_RUNNER_ENV);
            std::env::remove_var(IOS_SMOKE_ARTIFACT_DIR_ENV);
        }

        assert_eq!(trace.plan_id, "increment-the-counter-once");
        assert_eq!(trace.status, domain::RunStatus::Passed);
        assert_eq!(trace.artifacts[0].artifact_type, "screenshot");
        assert!(artifact_dir.join("plan.json").is_file());
    }

    fn smoke_fixture_plan() -> ExecutablePlan {
        ExecutablePlan {
            plan_id: "increment-the-counter-once".into(),
            name: "Increment the counter once".into(),
            version: PlanFormatVersion { major: 1, minor: 0 },
            source: PlanSource {
                kind: SourceKind::Gherkin,
                source_name: "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature"
                    .into(),
                compiler_version: "0.1.0".into(),
            },
            target: TargetProfile {
                platform: TargetPlatform::Ios,
                device_class: "simulator".into(),
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
                        name: Some("tap-counter".into()),
                    },
                    guards: vec![],
                    postconditions: vec![],
                    timeout_ms: 5_000,
                    retry: RetryPolicy::default(),
                    on_failure: FailurePolicy::AbortRun,
                    artifacts: ArtifactPolicy::default(),
                },
            ],
            metadata: BTreeMap::new(),
        }
    }

    fn temp_path(prefix: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "{prefix}-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock should move forward")
                .as_nanos()
        ))
    }

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }
}
