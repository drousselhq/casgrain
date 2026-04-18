use std::collections::BTreeMap;

use application::{CompileOutput, PlanCompiler, validate_plan};
use domain::{
    ArtifactPolicy, CompilationDiagnostic, DiagnosticSeverity, ExecutablePlan, ExecutionDefaults,
    FailurePolicy, PlanFormatVersion, PlanSource, PlanStep, RetryPolicy, SourceKind, StepIntent,
    TargetPlatform, TargetProfile,
};

use crate::fixture_vocabulary::fixture_vocabulary_for;
use crate::generic_lowering::lower_step;
use crate::phrase_helpers::slugify;

pub struct GherkinCompiler {
    compiler_version: String,
}

impl Default for GherkinCompiler {
    fn default() -> Self {
        Self {
            compiler_version: env!("CARGO_PKG_VERSION").to_string(),
        }
    }
}

impl PlanCompiler for GherkinCompiler {
    fn compile(
        &self,
        input: &str,
        source_name: &str,
    ) -> Result<CompileOutput, Vec<CompilationDiagnostic>> {
        compile_gherkin(input, source_name, &self.compiler_version)
    }
}

pub fn compile_gherkin(
    input: &str,
    source_name: &str,
    compiler_version: &str,
) -> Result<CompileOutput, Vec<CompilationDiagnostic>> {
    let fixture_vocabulary = fixture_vocabulary_for(source_name);
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
            let lowering = lower_step(
                &intent,
                description,
                line_number,
                fixture_vocabulary.as_ref(),
            );
            diagnostics.extend(lowering.diagnostics);

            steps.push(PlanStep {
                step_id,
                intent,
                description: description.to_string(),
                action: lowering.action,
                guards: lowering.guards,
                postconditions: lowering.postconditions,
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
            kind: SourceKind::Gherkin,
            source_name: source_name.into(),
            compiler_version: compiler_version.into(),
        },
        target: TargetProfile {
            platform: fixture_vocabulary
                .as_ref()
                .map(|vocabulary| vocabulary.target_platform.clone())
                .unwrap_or(TargetPlatform::CrossPlatform),
            device_class: fixture_vocabulary
                .as_ref()
                .map(|vocabulary| vocabulary.device_class.to_string())
                .unwrap_or_else(|| "simulator".into()),
        },
        capabilities_required: fixture_vocabulary
            .as_ref()
            .map(|vocabulary| vocabulary.capabilities())
            .unwrap_or_default(),
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
