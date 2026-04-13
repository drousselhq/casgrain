pub mod mock;

use mar_domain::{
    ActionKind, ArtifactRef, AssertionKind, DeviceEngine, DeviceSnapshot, ExecutablePlan,
    ExecutionTrace, FailureCode, FailurePolicy, FailureReport, ObservedElement, RunStatus,
    RuntimeFailure, Selector, StepStatus, StepTrace, StringMatchKind, WaitKind,
};

pub struct DeterministicRunner {
    pub run_id: String,
}

impl DeterministicRunner {
    pub fn new(run_id: impl Into<String>) -> Self {
        Self {
            run_id: run_id.into(),
        }
    }

    pub fn execute<E: DeviceEngine>(
        &self,
        engine: &mut E,
        plan: &ExecutablePlan,
    ) -> ExecutionTrace {
        let mut trace = ExecutionTrace {
            run_id: self.run_id.clone(),
            plan_id: plan.plan_id.clone(),
            device: engine.descriptor(),
            started_at: "now".into(),
            finished_at: None,
            status: RunStatus::Passed,
            steps: Vec::new(),
            artifacts: Vec::new(),
            diagnostics: Vec::new(),
        };

        for step in &plan.steps {
            let mut step_trace = StepTrace {
                step_id: step.step_id.clone(),
                status: StepStatus::Passed,
                attempts: 0,
                failure: None,
                artifacts: Vec::new(),
            };

            let attempts = step.retry.max_attempts.max(1);
            let mut last_failure = None;

            for _attempt in 0..attempts {
                step_trace.attempts += 1;
                match run_step(engine, &step.action, &step.guards, &step.postconditions) {
                    Ok(mut artifacts) => {
                        if step.artifacts.capture_after_step {
                            artifacts.push(ArtifactRef {
                                artifact_id: format!("{}-after", step.step_id),
                                artifact_type: "step_snapshot".into(),
                                path: format!("artifacts/{}-after.json", step.step_id),
                                sha256: None,
                                step_id: Some(step.step_id.clone()),
                            });
                        }
                        trace.artifacts.extend(artifacts.clone());
                        step_trace.artifacts = artifacts;
                        last_failure = None;
                        break;
                    }
                    Err(failure) => {
                        last_failure = Some(FailureReport {
                            code: failure.code,
                            message: failure.message,
                            step_id: step.step_id.clone(),
                        });
                    }
                }
            }

            if let Some(failure) = last_failure {
                step_trace.status = StepStatus::Failed;
                step_trace.failure = Some(failure.clone());

                if step.artifacts.capture_on_failure {
                    let artifact = ArtifactRef {
                        artifact_id: format!("{}-failure", step.step_id),
                        artifact_type: "failure_context".into(),
                        path: format!("artifacts/{}-failure.json", step.step_id),
                        sha256: None,
                        step_id: Some(step.step_id.clone()),
                    };
                    trace.artifacts.push(artifact.clone());
                    step_trace.artifacts.push(artifact);
                }

                trace.status = RunStatus::Failed;
                trace.steps.push(step_trace);
                if matches!(step.on_failure, FailurePolicy::AbortRun) {
                    trace.finished_at = Some("now".into());
                    return trace;
                }
            } else {
                trace.steps.push(step_trace);
            }
        }

        trace.finished_at = Some("now".into());
        trace
    }
}

fn run_step<E: DeviceEngine>(
    engine: &mut E,
    action: &ActionKind,
    guards: &[WaitKind],
    postconditions: &[AssertionKind],
) -> Result<Vec<ArtifactRef>, RuntimeFailure> {
    for guard in guards {
        evaluate_wait(engine, guard)?;
    }

    let mut artifacts = engine.perform_action(action)?;
    let snapshot = engine.snapshot()?;

    for assertion in postconditions {
        evaluate_assertion(&snapshot, assertion)?;
    }

    Ok(std::mem::take(&mut artifacts))
}

fn evaluate_wait<E: DeviceEngine>(engine: &E, wait: &WaitKind) -> Result<(), RuntimeFailure> {
    match wait {
        WaitKind::ForAssertion { assertion } => {
            let snapshot = engine.snapshot()?;
            evaluate_assertion(&snapshot, assertion)
        }
        WaitKind::ForTimeout { .. } => Ok(()),
    }
}

fn evaluate_assertion(
    snapshot: &DeviceSnapshot,
    assertion: &AssertionKind,
) -> Result<(), RuntimeFailure> {
    match assertion {
        AssertionKind::Exists { target } | AssertionKind::Visible { target } => {
            if find_element(snapshot, target).is_some() {
                Ok(())
            } else {
                Err(RuntimeFailure {
                    code: FailureCode::UnresolvedSelector,
                    message: format!("selector was not found: {target:?}"),
                })
            }
        }
        AssertionKind::TextEquals { target, value } => {
            let element = find_element(snapshot, target).ok_or(RuntimeFailure {
                code: FailureCode::UnresolvedSelector,
                message: format!("selector was not found: {target:?}"),
            })?;
            if element.text.as_deref() == Some(value.as_str()) {
                Ok(())
            } else {
                Err(RuntimeFailure {
                    code: FailureCode::AssertionFailed,
                    message: format!("expected text {value:?}, got {:?}", element.text),
                })
            }
        }
        AssertionKind::AppInForeground { app_id } => {
            if snapshot.foreground_app.as_deref() == Some(app_id.as_str()) {
                Ok(())
            } else {
                Err(RuntimeFailure {
                    code: FailureCode::AssertionFailed,
                    message: format!("expected foreground app {app_id}"),
                })
            }
        }
    }
}

pub(crate) fn find_element<'a>(
    snapshot: &'a DeviceSnapshot,
    selector: &Selector,
) -> Option<&'a ObservedElement> {
    snapshot
        .elements
        .iter()
        .find(|element| element_matches_selector(element, selector))
}

pub(crate) fn element_matches_selector(element: &ObservedElement, selector: &Selector) -> bool {
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
    use mar_domain::{
        ArtifactPolicy, CapabilitySet, DeviceDescriptor, DeviceSnapshot, ExecutablePlan,
        ExecutionDefaults, FailurePolicy, ObservedElement, PlanFormatVersion, PlanSource, PlanStep,
        RetryPolicy, Selector, SourceKind, StepIntent, StringMatchKind, TargetPlatform,
        TargetProfile, TextSelector, UiRole,
    };

    use super::*;

    #[derive(Clone)]
    struct FakeEngine {
        snapshot: DeviceSnapshot,
    }

    impl DeviceEngine for FakeEngine {
        fn descriptor(&self) -> DeviceDescriptor {
            DeviceDescriptor {
                platform: TargetPlatform::Ios,
                name: "iPhone 16".into(),
                os_version: "18.0".into(),
            }
        }

        fn perform_action(
            &mut self,
            action: &ActionKind,
        ) -> Result<Vec<ArtifactRef>, RuntimeFailure> {
            match action {
                ActionKind::Noop => Ok(Vec::new()),
                ActionKind::LaunchApp { app_id } => {
                    self.snapshot.foreground_app = Some(app_id.clone());
                    Ok(Vec::new())
                }
                ActionKind::Tap { target } => {
                    let tapped_label = find_element(&self.snapshot, target)
                        .and_then(|element| element.label.clone().or_else(|| element.text.clone()))
                        .ok_or(RuntimeFailure {
                            code: FailureCode::UnresolvedSelector,
                            message: format!("selector was not found: {target:?}"),
                        })?;
                    if tapped_label.to_lowercase().contains("login") {
                        self.snapshot.elements.push(ObservedElement {
                            resource_id: None,
                            accessibility_id: Some("home_title".into()),
                            role: Some(UiRole::StaticText),
                            text: Some("Home".into()),
                            label: Some("Home".into()),
                            visible: true,
                        });
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
                _ => Err(RuntimeFailure {
                    code: FailureCode::UnsupportedAction,
                    message: "fake engine does not support this action yet".into(),
                }),
            }
        }

        fn snapshot(&self) -> Result<DeviceSnapshot, RuntimeFailure> {
            Ok(self.snapshot.clone())
        }
    }

    fn sample_plan(assertion: AssertionKind) -> ExecutablePlan {
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
                intent: StepIntent::Assert,
                description: "assert login button exists".into(),
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![assertion],
                timeout_ms: 1_000,
                retry: RetryPolicy { max_attempts: 1 },
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            }],
            metadata: Default::default(),
        }
    }

    #[test]
    fn runner_passes_for_matching_selector() {
        let mut engine = FakeEngine {
            snapshot: DeviceSnapshot {
                elements: vec![ObservedElement {
                    resource_id: None,
                    accessibility_id: Some("login_button".into()),
                    role: Some(UiRole::Button),
                    text: Some("Login".into()),
                    label: Some("Login".into()),
                    visible: true,
                }],
                foreground_app: Some("com.example.app".into()),
            },
        };
        let plan = sample_plan(AssertionKind::Exists {
            target: Selector::Text(TextSelector {
                value: "Login".into(),
                match_kind: StringMatchKind::Exact,
            }),
        });

        let trace = DeterministicRunner::new("run-1").execute(&mut engine, &plan);
        assert_eq!(trace.status, RunStatus::Passed);
        assert_eq!(trace.steps[0].status, StepStatus::Passed);
    }

    #[test]
    fn runner_fails_for_missing_selector() {
        let mut engine = FakeEngine {
            snapshot: DeviceSnapshot::default(),
        };
        let plan = sample_plan(AssertionKind::Exists {
            target: Selector::AccessibilityId("missing".into()),
        });

        let trace = DeterministicRunner::new("run-2").execute(&mut engine, &plan);
        assert_eq!(trace.status, RunStatus::Failed);
        assert_eq!(trace.steps[0].status, StepStatus::Failed);
        assert_eq!(
            trace.steps[0].failure.as_ref().map(|f| &f.code),
            Some(&FailureCode::UnresolvedSelector)
        );
    }

    #[test]
    fn runner_can_execute_small_login_like_flow() {
        let mut engine = FakeEngine {
            snapshot: DeviceSnapshot {
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
                ],
                foreground_app: None,
            },
        };

        let plan = ExecutablePlan {
            plan_id: "plan-login".into(),
            name: "Login".into(),
            version: PlanFormatVersion { major: 1, minor: 0 },
            source: PlanSource {
                kind: SourceKind::OpenSpec,
                source_name: "login.feature".into(),
                compiler_version: "0.1.0".into(),
            },
            target: TargetProfile {
                platform: TargetPlatform::CrossPlatform,
                device_class: "simulator".into(),
            },
            capabilities_required: CapabilitySet::default(),
            defaults: ExecutionDefaults::default(),
            steps: vec![
                PlanStep {
                    step_id: "launch".into(),
                    intent: StepIntent::Setup,
                    description: "launch app".into(),
                    action: ActionKind::LaunchApp {
                        app_id: "app.under.test".into(),
                    },
                    guards: vec![],
                    postconditions: vec![AssertionKind::AppInForeground {
                        app_id: "app.under.test".into(),
                    }],
                    timeout_ms: 1_000,
                    retry: RetryPolicy::default(),
                    on_failure: FailurePolicy::AbortRun,
                    artifacts: ArtifactPolicy::default(),
                },
                PlanStep {
                    step_id: "type-email".into(),
                    intent: StepIntent::Interact,
                    description: "type email".into(),
                    action: ActionKind::TypeText {
                        target: Selector::Text(TextSelector {
                            value: "Email".into(),
                            match_kind: StringMatchKind::Contains,
                        }),
                        text: "daniel@example.com".into(),
                    },
                    guards: vec![],
                    postconditions: vec![AssertionKind::TextEquals {
                        target: Selector::Text(TextSelector {
                            value: "daniel@example.com".into(),
                            match_kind: StringMatchKind::Exact,
                        }),
                        value: "daniel@example.com".into(),
                    }],
                    timeout_ms: 1_000,
                    retry: RetryPolicy::default(),
                    on_failure: FailurePolicy::AbortRun,
                    artifacts: ArtifactPolicy::default(),
                },
                PlanStep {
                    step_id: "tap-login".into(),
                    intent: StepIntent::Interact,
                    description: "tap login".into(),
                    action: ActionKind::Tap {
                        target: Selector::Text(TextSelector {
                            value: "Login".into(),
                            match_kind: StringMatchKind::Contains,
                        }),
                    },
                    guards: vec![],
                    postconditions: vec![AssertionKind::Visible {
                        target: Selector::Text(TextSelector {
                            value: "Home".into(),
                            match_kind: StringMatchKind::Contains,
                        }),
                    }],
                    timeout_ms: 1_000,
                    retry: RetryPolicy::default(),
                    on_failure: FailurePolicy::AbortRun,
                    artifacts: ArtifactPolicy::default(),
                },
            ],
            metadata: Default::default(),
        };

        let trace = DeterministicRunner::new("run-login").execute(&mut engine, &plan);
        assert_eq!(trace.status, RunStatus::Passed);
        assert_eq!(trace.steps.len(), 3);
        assert!(trace
            .steps
            .iter()
            .all(|step| step.status == StepStatus::Passed));
    }
}
