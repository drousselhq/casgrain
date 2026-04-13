use std::{env, fs};

use mar_application::{CompileOutput, PlanCompiler};
use mar_compiler::GherkinCompiler;
use mar_domain::{CompilationDiagnostic, ExecutionTrace};
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
        "run-mock" => {
            let input = args.get(1).ok_or_else(usage)?;
            let source = read_source(input)?;
            let trace_json = args.iter().skip(2).any(|arg| arg == "--trace-json");
            let output = compile_source(&source, input)?;
            let mut engine = MockDeviceEngine::login_fixture();
            let trace = DeterministicRunner::new(format!("mock-{}", output.plan.plan_id))
                .execute(&mut engine, &output.plan);

            if trace_json {
                return Ok(serde_json::to_string_pretty(&trace).expect("trace should serialize"));
            }

            Ok(render_run_summary(&output, &trace))
        }
        _ => Err(usage()),
    }
}

fn usage() -> String {
    "usage:\n  mar compile <feature-file>\n  mar run-mock <feature-file> [--trace-json]".into()
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

fn render_run_summary(output: &CompileOutput, trace: &ExecutionTrace) -> String {
    let mut lines = Vec::new();
    lines.push(format!("Casgrain mock run: {}", output.plan.name));
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
        );

        let output = run(vec!["run-mock".into(), feature]).expect("run-mock should succeed");
        assert!(output.contains("Casgrain mock run: Successful login"));
        assert!(output.contains("Run status: Passed"));
        assert!(output.contains("[PASS]"));
    }

    fn tempfile_feature(contents: &str) -> String {
        let path = std::env::temp_dir().join(format!(
            "casgrain-cli-test-{}.feature",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("time should move forward")
                .as_nanos()
        ));
        std::fs::write(&path, contents).expect("temp feature should be written");
        path.to_string_lossy().to_string()
    }
}
