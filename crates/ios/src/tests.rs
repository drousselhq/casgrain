use std::{fs, os::unix::fs::PermissionsExt};

use domain::{ActionKind, DeviceEngine, FailureCode, Selector, TargetPlatform};

use crate::{
    IosSimulatorAdapter, IosSimulatorDescriptor,
    paths::{IOS_SMOKE_ARTIFACT_DIR_ENV, IOS_SMOKE_RUNNER_ENV, REPO_ROOT_ENV},
    plan_validation::validate_supported_smoke_plan,
    run_smoke_fixture_plan,
    test_support::{env_lock, smoke_fixture_plan, temp_path},
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
    assert!(snapshot.device_snapshot.elements.iter().any(|element| {
        element.accessibility_id.as_deref() == Some("email_field")
            && element.text.as_deref() == Some("tester@example.com")
    }));
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
    assert!(
        snapshot
            .elements
            .iter()
            .any(
                |element| element.accessibility_id.as_deref() == Some("count-label")
                    && element.text.as_deref() == Some("Count: 1")
            )
    );
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
    assert!(
        snapshot
            .elements
            .iter()
            .any(|element| element.accessibility_id.as_deref() == Some("home_title"))
    );
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
