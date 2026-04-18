use std::{env, path::Path, process::Command};

use domain::{FailureCode, RuntimeFailure};

use crate::paths::{IOS_SMOKE_RUNNER_ENV, smoke_script_path};

pub(crate) fn build_smoke_command(
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

    let script_path = smoke_script_path(repo_root);
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
