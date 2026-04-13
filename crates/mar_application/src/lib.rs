use std::collections::BTreeSet;

use mar_domain::{CompilationDiagnostic, DiagnosticSeverity, ExecutablePlan};

pub trait PlanCompiler {
    fn compile(
        &self,
        input: &str,
        source_name: &str,
    ) -> Result<CompileOutput, Vec<CompilationDiagnostic>>;
}

#[derive(Debug, Clone)]
pub struct CompileOutput {
    pub plan: ExecutablePlan,
    pub diagnostics: Vec<CompilationDiagnostic>,
}

pub fn validate_plan(plan: &ExecutablePlan) -> Result<(), Vec<CompilationDiagnostic>> {
    let mut diagnostics = Vec::new();

    if plan.steps.is_empty() {
        diagnostics.push(CompilationDiagnostic {
            severity: DiagnosticSeverity::Error,
            message: "plan must contain at least one step".into(),
            location: None,
        });
    }

    let mut seen = BTreeSet::new();
    for step in &plan.steps {
        if !seen.insert(step.step_id.clone()) {
            diagnostics.push(CompilationDiagnostic {
                severity: DiagnosticSeverity::Error,
                message: format!("duplicate step_id detected: {}", step.step_id),
                location: Some(step.step_id.clone()),
            });
        }
    }

    if diagnostics
        .iter()
        .any(|item| item.severity == DiagnosticSeverity::Error)
    {
        Err(diagnostics)
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use mar_domain::{
        ActionKind, ArtifactPolicy, CapabilitySet, ExecutablePlan, ExecutionDefaults,
        FailurePolicy, PlanFormatVersion, PlanSource, PlanStep, RetryPolicy, SourceKind,
        StepIntent, TargetPlatform, TargetProfile,
    };

    use super::validate_plan;

    fn sample_plan() -> ExecutablePlan {
        ExecutablePlan {
            plan_id: "plan-1".into(),
            name: "Sample".into(),
            version: PlanFormatVersion { major: 1, minor: 0 },
            source: PlanSource {
                kind: SourceKind::OpenSpec,
                source_name: "sample.feature".into(),
                compiler_version: "0.1.0".into(),
            },
            target: TargetProfile {
                platform: TargetPlatform::CrossPlatform,
                device_class: "simulator".into(),
            },
            capabilities_required: CapabilitySet::default(),
            defaults: ExecutionDefaults::default(),
            steps: vec![PlanStep {
                step_id: "step-1".into(),
                intent: StepIntent::Observe,
                description: "observe".into(),
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 1_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            }],
            metadata: Default::default(),
        }
    }

    #[test]
    fn validate_plan_rejects_duplicate_step_ids() {
        let mut plan = sample_plan();
        let duplicate = plan.steps[0].clone();
        plan.steps.push(duplicate);

        let errors = validate_plan(&plan).unwrap_err();
        assert_eq!(errors.len(), 1);
        assert!(errors[0].message.contains("duplicate step_id"));
    }
}
