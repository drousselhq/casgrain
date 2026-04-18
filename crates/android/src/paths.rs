use std::{
    env,
    path::{Path, PathBuf},
};

use domain::{FailureCode, RuntimeFailure};

pub(crate) const ANDROID_SMOKE_RUNNER_ENV: &str = "CASGRAIN_ANDROID_SMOKE_RUNNER";
pub(crate) const ANDROID_SMOKE_ARTIFACT_DIR_ENV: &str = "CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR";
const REPO_ROOT_ENV: &str = "CASGRAIN_REPO_ROOT";
const DEFAULT_SMOKE_SCRIPT: &str = "tests/test-support/scripts/android_smoke_run_plan.py";

pub(crate) fn resolve_repo_root() -> Result<PathBuf, RuntimeFailure> {
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
            "failed to locate repository root; set CASGRAIN_REPO_ROOT to a checkout containing tests/test-support/scripts/android_smoke_run_plan.py",
        ),
    })
}

pub(crate) fn resolve_artifact_dir(repo_root: &Path, plan_id: &str) -> PathBuf {
    env::var(ANDROID_SMOKE_ARTIFACT_DIR_ENV)
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            repo_root
                .join("artifacts")
                .join("android-smoke-generated")
                .join(plan_id)
        })
}

pub(crate) fn smoke_script_path(repo_root: &Path) -> PathBuf {
    repo_root.join(DEFAULT_SMOKE_SCRIPT)
}
