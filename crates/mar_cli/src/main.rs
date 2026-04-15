use std::{env, fs};

use mar_android::run_smoke_fixture_plan as run_android_smoke_fixture_plan;
use mar_application::{CompileOutput, PlanCompiler};
use mar_compiler::GherkinCompiler;
use mar_domain::{CompilationDiagnostic, ExecutionTrace};
use mar_ios::run_smoke_fixture_plan;
use mar_runner::{mock::MockDeviceEngine, DeterministicRunner};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(args) {
        Ok(output) => println!("{output}"),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}

fn run(args: Vec<String>) -> Result<String, String> {
    let Some(command) = args.first().map(String::as_str) else {
        return Err(usage());
    };

    match command {
        "compile" => {
            let input = args.get(1).ok_or_else(usage)?;
            let source = read_source(input)?;
            let output = compile_source(&source, input)?;
            Ok(serde_json::to_string_pretty(&output.plan).expect("plan should serialize"))
        }
        "run-mock" => run_mock(&args),
        "run-ios-smoke" => run_ios_smoke(&args),
        "run-android-smoke" => run_android_smoke(&args),
        _ => Err(usage()),
    }
}

fn run_mock(args: &[String]) -> Result<String, String> {
    let input = args.get(1).ok_or_else(usage)?;
    let source = read_source(input)?;
    let trace_json = trace_json_requested(args);
    let output = compile_source(&source, input)?;
    let mut engine = MockDeviceEngine::login_fixture();
    let trace = DeterministicRunner::new(format!("mock-{}", output.plan.plan_id))
        .execute(&mut engine, &output.plan);

    render_trace_output("Casgrain mock run", trace_json, &output, &trace)
}

fn run_ios_smoke(args: &[String]) -> Result<String, String> {
    let input = args.get(1).ok_or_else(usage)?;
    let source = read_source(input)?;
    let trace_json = trace_json_requested(args);
    let output = compile_source(&source, input)?;
    let trace = run_smoke_fixture_plan(&output.plan)
        .map_err(|error| format!("failed to run real iOS smoke harness: {error}"))?;

    render_trace_output("Casgrain iOS smoke run", trace_json, &output, &trace)
}

fn run_android_smoke(args: &[String]) -> Result<String, String> {
    let input = args.get(1).ok_or_else(usage)?;
    let source = read_source(input)?;
    let trace_json = trace_json_requested(args);
    let output = compile_source(&source, input)?;
    let trace = run_android_smoke_fixture_plan(&output.plan)
        .map_err(|error| format!("failed to run Android smoke harness: {error}"))?;

    render_trace_output("Casgrain Android smoke run", trace_json, &output, &trace)
}

fn render_trace_output(
    title: &str,
    trace_json: bool,
    output: &CompileOutput,
    trace: &ExecutionTrace,
) -> Result<String, String> {
    if trace_json {
        return Ok(serde_json::to_string_pretty(trace).expect("trace should serialize"));
    }

    Ok(render_run_summary(title, output, trace))
}

fn trace_json_requested(args: &[String]) -> bool {
    args.iter().skip(2).any(|arg| arg == "--trace-json")
}

fn usage() -> String {
    "usage:\n  mar compile <feature-file>\n  mar run-mock <feature-file> [--trace-json]\n  mar run-ios-smoke <feature-file> [--trace-json]\n  mar run-android-smoke <feature-file> [--trace-json]".into()
}

fn read_source(path: &str) -> Result<String, String> {
    fs::read_to_string(path).map_err(|error| format!("failed to read {path}: {error}"))
}

fn compile_source(source: &str, source_name: &str) -> Result<CompileOutput, String> {
    let compiler = GherkinCompiler::default();
    compiler
        .compile(source, source_name)
        .map_err(|diagnostics| render_compile_failure(&diagnostics))
}

fn render_compile_failure(diagnostics: &[CompilationDiagnostic]) -> String {
    let mut lines = vec![String::from("compile failed:")];
    for diagnostic in diagnostics {
        lines.push(render_diagnostic(diagnostic));
    }
    lines.join("\n")
}

fn render_diagnostic(diagnostic: &CompilationDiagnostic) -> String {
    match &diagnostic.location {
        Some(location) => format!(
            "- {:?}: {} ({location})",
            diagnostic.severity, diagnostic.message
        ),
        None => format!("- {:?}: {}", diagnostic.severity, diagnostic.message),
    }
}

fn render_run_summary(title: &str, output: &CompileOutput, trace: &ExecutionTrace) -> String {
    let mut lines = Vec::new();
    lines.push(format!("{title}: {}", output.plan.name));
    lines.push(format!("Plan ID: {}", output.plan.plan_id));
    lines.push(format!("Source: {}", output.plan.source.source_name));
    lines.push(format!(
        "Device: {} {} ({:?})",
        trace.device.name, trace.device.os_version, trace.device.platform
    ));
    lines.push(format!("Run status: {:?}", trace.status));
    lines.push(String::new());
    lines.push(String::from("Steps:"));
    for (step, step_trace) in output.plan.steps.iter().zip(&trace.steps) {
        let mut line = format!(
            "- [{}] {} — {} (attempts: {})",
            status_marker(&step_trace.status),
            step.step_id,
            step.description,
            step_trace.attempts
        );
        if let Some(failure) = &step_trace.failure {
            line.push_str(&format!(
                " | failure: {:?} — {}",
                failure.code, failure.message
            ));
        }
        lines.push(line);
    }

    if !output.diagnostics.is_empty() {
        lines.push(String::new());
        lines.push(String::from("Compiler diagnostics:"));
        for diagnostic in &output.diagnostics {
            lines.push(render_diagnostic(diagnostic));
        }
    }

    if !trace.artifacts.is_empty() {
        lines.push(String::new());
        lines.push(String::from("Artifacts:"));
        for artifact in &trace.artifacts {
            lines.push(format!(
                "- {} ({}) -> {}",
                artifact.artifact_id, artifact.artifact_type, artifact.path
            ));
        }
    }

    lines.join("\n")
}

fn status_marker(status: &mar_domain::StepStatus) -> &'static str {
    match status {
        mar_domain::StepStatus::Passed => "PASS",
        mar_domain::StepStatus::Failed => "FAIL",
        mar_domain::StepStatus::Skipped => "SKIP",
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

    use serde_json::Value;

    use super::run;

    #[test]
    fn usage_is_returned_for_missing_arguments() {
        let error = run(vec![]).expect_err("expected usage error");
        assert!(error.contains("usage:"));
    }

    #[test]
    fn usage_is_returned_for_unknown_command() {
        let error = run(vec!["wat".into()]).expect_err("expected usage error");
        assert!(error.contains("run-mock"));
        assert!(error.contains("run-ios-smoke"));
        assert!(error.contains("run-android-smoke"));
    }

    #[test]
    fn compile_failure_is_rendered_cleanly() {
        let error = super::compile_source("Feature: Empty\nScenario: Nothing", "inline.feature")
            .expect_err("compile should fail when no steps are present");
        assert!(error.contains("compile failed:"));
        assert!(error.contains("plan must contain at least one step"));
    }

    #[test]
    fn run_mock_reports_successful_flow() {
        let feature = tempfile_feature(
            r#"Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user enters "daniel@example.com" into email field
    When the user taps login button
    Then Home is visible
"#,
            "login.feature",
        );

        let output = run(vec!["run-mock".into(), feature]).expect("run-mock should succeed");
        assert!(output.contains("Casgrain mock run: Successful login"));
        assert!(output.contains("Run status: Passed"));
        assert!(output.contains("[PASS]"));
    }

    #[test]
    fn run_ios_smoke_reports_successful_tap_counter_flow() {
        let feature = tempfile_feature(
            r#"Feature: iOS smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
"#,
            "fixtures/ios-smoke/features/tap_counter.feature",
        );
        let repo_root = temp_path("casgrain-cli-repo");
        let artifact_dir = temp_path("casgrain-cli-artifacts");
        let runner = install_fake_ios_smoke_runner(&repo_root);
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::set_var("CASGRAIN_IOS_SMOKE_RUNNER", &runner);
            std::env::set_var("CASGRAIN_IOS_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let output =
            run(vec!["run-ios-smoke".into(), feature]).expect("run-ios-smoke should succeed");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_IOS_SMOKE_RUNNER");
            std::env::remove_var("CASGRAIN_IOS_SMOKE_ARTIFACT_DIR");
        }

        assert!(output.contains("Casgrain iOS smoke run: Increment the counter once"));
        assert!(output.contains("Device: iPhone 16 18.0 (Ios)"));
        assert!(output.contains("Run status: Passed"));
        assert!(output.contains("tap-counter-1 (screenshot) ->"));
    }

    #[test]
    fn run_ios_smoke_trace_json_is_machine_readable() {
        let feature = tempfile_feature(
            r#"Feature: iOS smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
"#,
            "fixtures/ios-smoke/features/tap_counter.feature",
        );
        let repo_root = temp_path("casgrain-cli-repo");
        let artifact_dir = temp_path("casgrain-cli-artifacts");
        let runner = install_fake_ios_smoke_runner(&repo_root);
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::set_var("CASGRAIN_IOS_SMOKE_RUNNER", &runner);
            std::env::set_var("CASGRAIN_IOS_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let output = run(vec!["run-ios-smoke".into(), feature, "--trace-json".into()])
            .expect("run-ios-smoke json output should succeed");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_IOS_SMOKE_RUNNER");
            std::env::remove_var("CASGRAIN_IOS_SMOKE_ARTIFACT_DIR");
        }
        let json: Value = serde_json::from_str(&output).expect("output should be valid json");

        assert_eq!(json["run_id"], "ios-smoke-increment-the-counter-once");
        assert_eq!(json["device"]["platform"], "ios");
        assert_eq!(json["status"], "passed");
        assert!(json["artifacts"][0]["path"]
            .as_str()
            .expect("artifact path should be a string")
            .ends_with("tap-counter-1.png"));
    }

    #[test]
    fn run_android_smoke_reports_successful_tap_counter_flow() {
        let feature = tempfile_feature(
            r#"Feature: Android smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
"#,
            "fixtures/android-smoke/features/tap_counter.feature",
        );
        let repo_root = temp_path("casgrain-cli-repo");
        let artifact_dir = temp_path("casgrain-cli-artifacts");
        let runner = install_fake_android_smoke_runner(&repo_root);
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_RUNNER", &runner);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let output = run(vec!["run-android-smoke".into(), feature])
            .expect("run-android-smoke should succeed");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        }

        assert!(output.contains("Casgrain Android smoke run: Increment the counter once"));
        assert!(output.contains("Device: Pixel 8 15 (Android)"));
        assert!(output.contains("Run status: Passed"));
        assert!(output.contains("android-tap-counter-1 (screenshot) ->"));
    }

    #[test]
    fn run_android_smoke_trace_json_is_machine_readable() {
        let feature = tempfile_feature(
            r#"Feature: Android smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
"#,
            "fixtures/android-smoke/features/tap_counter.feature",
        );
        let repo_root = temp_path("casgrain-cli-repo");
        let artifact_dir = temp_path("casgrain-cli-artifacts");
        let runner = install_fake_android_smoke_runner(&repo_root);
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_RUNNER", &runner);
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let output = run(vec![
            "run-android-smoke".into(),
            feature,
            "--trace-json".into(),
        ])
        .expect("run-android-smoke json output should succeed");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        }
        let json: Value = serde_json::from_str(&output).expect("output should be valid json");

        assert_eq!(json["run_id"], "android-smoke-increment-the-counter-once");
        assert_eq!(json["device"]["platform"], "android");
        assert_eq!(json["status"], "passed");
        assert!(json["artifacts"][0]["path"]
            .as_str()
            .expect("artifact path should be a string")
            .ends_with("android-tap-counter-1.png"));
    }

    #[test]
    fn run_android_smoke_without_injected_runner_fails_honestly() {
        let feature = tempfile_feature(
            r#"Feature: Android smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
"#,
            "fixtures/android-smoke/features/tap_counter.feature",
        );
        let artifact_dir = temp_path("casgrain-cli-artifacts");
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("workspace root should exist")
            .to_path_buf();
        let _guard = env_lock()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());

        unsafe {
            std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
            std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        }

        let error = run(vec!["run-android-smoke".into(), feature])
            .expect_err("default android smoke script should fail until emulator harness lands");

        unsafe {
            std::env::remove_var("CASGRAIN_REPO_ROOT");
            std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        }

        assert!(error.contains("validates the generated plan contract only"));
        assert!(artifact_dir.join("plan.json").is_file());
    }

    fn install_fake_ios_smoke_runner(repo_root: &std::path::Path) -> PathBuf {
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
artifact_path = artifact_dir / "tap-counter-1.png"
artifact_path.write_bytes(b"png")

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

    fn install_fake_android_smoke_runner(repo_root: &std::path::Path) -> PathBuf {
        fs::create_dir_all(repo_root.join("scripts")).expect("repo root should be created");
        let runner = repo_root.join("android-runner.py");
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

    fn tempfile_feature(contents: &str, relative_name: &str) -> String {
        let root = std::env::temp_dir().join(format!(
            "casgrain-cli-test-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("time should move forward")
                .as_nanos()
        ));
        let path = root.join(PathBuf::from(relative_name));
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).expect("temp feature directory should be created");
        }
        std::fs::write(&path, contents).expect("temp feature should be written");
        path.to_string_lossy().to_string()
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
