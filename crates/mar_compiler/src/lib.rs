use std::collections::BTreeMap;

use mar_application::{validate_plan, CompileOutput, PlanCompiler};
use mar_domain::{
    ActionKind, ArtifactPolicy, CapabilitySet, CompilationDiagnostic, DiagnosticSeverity,
    ExecutablePlan, ExecutionDefaults, FailurePolicy, PlanFormatVersion, PlanSource, PlanStep,
    RetryPolicy, SourceKind, StepIntent, TargetPlatform, TargetProfile,
};

pub struct OpenspecCompiler {
    compiler_version: String,
}

impl Default for OpenspecCompiler {
    fn default() -> Self {
        Self {
            compiler_version: env!("CARGO_PKG_VERSION").to_string(),
        }
    }
}

impl PlanCompiler for OpenspecCompiler {
    fn compile(
        &self,
        input: &str,
        source_name: &str,
    ) -> Result<CompileOutput, Vec<CompilationDiagnostic>> {
        compile_openspec(input, source_name, &self.compiler_version)
    }
}

pub fn compile_openspec(
    input: &str,
    source_name: &str,
    compiler_version: &str,
) -> Result<CompileOutput, Vec<CompilationDiagnostic>> {
    let mut feature_name = None;
    let mut current_scenario = None;
    let mut previous_intent = StepIntent::Observe;
    let mut steps = Vec::new();
    let mut diagnostics = Vec::new();

    for (index, raw_line) in input.lines().enumerate() {
        let line_number = index + 1;
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        if let Some(name) = line.strip_prefix("Feature:") {
            feature_name = Some(name.trim().to_string());
            continue;
        }

        if let Some(name) = line.strip_prefix("Scenario:") {
            current_scenario = Some(name.trim().to_string());
            continue;
        }

        let prefixes = ["Given ", "When ", "Then ", "And "];
        let matched = prefixes
            .iter()
            .find_map(|prefix| line.strip_prefix(prefix).map(|rest| (*prefix, rest.trim())));
        if let Some((prefix, description)) = matched {
            let intent = match prefix {
                "Given " => StepIntent::Setup,
                "When " => StepIntent::Interact,
                "Then " => StepIntent::Assert,
                "And " => previous_intent.clone(),
                _ => StepIntent::Observe,
            };
            previous_intent = intent.clone();

            let scenario_name = current_scenario
                .clone()
                .unwrap_or_else(|| "unnamed-scenario".into());
            let step_id = format!("{}-{:03}", slugify(&scenario_name), steps.len() + 1);
            let action = match intent {
                StepIntent::Assert => ActionKind::Noop,
                _ => ActionKind::Noop,
            };

            steps.push(PlanStep {
                step_id,
                intent,
                description: description.to_string(),
                action,
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            });

            continue;
        }

        diagnostics.push(CompilationDiagnostic {
            severity: DiagnosticSeverity::Warning,
            message: format!("unrecognized line ignored: {line}"),
            location: Some(format!("line {line_number}")),
        });
    }

    let plan_name = current_scenario
        .or(feature_name.clone())
        .unwrap_or_else(|| source_name.to_string());

    let plan = ExecutablePlan {
        plan_id: slugify(&plan_name),
        name: plan_name,
        version: PlanFormatVersion { major: 1, minor: 0 },
        source: PlanSource {
            kind: SourceKind::OpenSpec,
            source_name: source_name.into(),
            compiler_version: compiler_version.into(),
        },
        target: TargetProfile {
            platform: TargetPlatform::CrossPlatform,
            device_class: "simulator".into(),
        },
        capabilities_required: CapabilitySet::default(),
        defaults: ExecutionDefaults::default(),
        steps,
        metadata: BTreeMap::from([(
            String::from("feature_name"),
            feature_name.unwrap_or_else(|| String::from("unknown-feature")),
        )]),
    };

    if let Err(mut errors) = validate_plan(&plan) {
        diagnostics.append(&mut errors);
    }

    if diagnostics
        .iter()
        .any(|item| item.severity == DiagnosticSeverity::Error)
    {
        Err(diagnostics)
    } else {
        Ok(CompileOutput { plan, diagnostics })
    }
}

fn slugify(input: &str) -> String {
    let mut output = String::new();
    let mut last_dash = false;
    for c in input.chars().flat_map(|c| c.to_lowercase()) {
        if c.is_ascii_alphanumeric() {
            output.push(c);
            last_dash = false;
        } else if !last_dash {
            output.push('-');
            last_dash = true;
        }
    }
    output.trim_matches('-').to_string()
}

#[cfg(test)]
mod tests {
    use super::compile_openspec;

    #[test]
    fn compiles_openspec_into_stable_plan() {
        let source = r#"
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login
    Then the home screen is visible
"#;

        let first = compile_openspec(source, "login.feature", "0.1.0").unwrap();
        let second = compile_openspec(source, "login.feature", "0.1.0").unwrap();

        assert_eq!(first.plan, second.plan);
        assert_eq!(first.plan.steps.len(), 3);
        assert_eq!(first.plan.steps[0].intent, mar_domain::StepIntent::Setup);
        assert_eq!(first.plan.steps[1].intent, mar_domain::StepIntent::Interact);
        assert_eq!(first.plan.steps[2].intent, mar_domain::StepIntent::Assert);
    }
}
