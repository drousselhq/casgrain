use std::fs;

use domain::{ExecutablePlan, ExecutionTrace, FailureCode, RuntimeFailure};

use crate::{
    command::build_smoke_command,
    paths::{resolve_artifact_dir, resolve_repo_root},
    plan_validation::validate_supported_smoke_plan,
};

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
