use domain::{
    ActionKind, AssertionKind, CompilationDiagnostic, DiagnosticSeverity, StepIntent, WaitKind,
};

use crate::fixture_vocabulary::FixtureVocabulary;
use crate::phrase_helpers::{
    extract_after_any, extract_text_entry, extract_text_equals_assertion, normalize_phrase,
    phrase_to_selector,
};

#[derive(Debug)]
pub(crate) struct LoweredStep {
    pub(crate) action: ActionKind,
    pub(crate) guards: Vec<WaitKind>,
    pub(crate) postconditions: Vec<AssertionKind>,
    pub(crate) diagnostics: Vec<CompilationDiagnostic>,
}

pub(crate) fn lower_step(
    intent: &StepIntent,
    description: &str,
    line_number: usize,
    fixture_vocabulary: Option<&FixtureVocabulary>,
) -> LoweredStep {
    if let Some(vocabulary) = fixture_vocabulary {
        return vocabulary.lower_step(intent, description, line_number);
    }

    let normalized = normalize_phrase(description);

    if matches!(intent, StepIntent::Setup)
        && (normalized.contains("app is launched")
            || normalized.contains("application is launched"))
    {
        return LoweredStep {
            action: ActionKind::LaunchApp {
                app_id: "app.under.test".into(),
            },
            guards: vec![],
            postconditions: vec![AssertionKind::AppInForeground {
                app_id: "app.under.test".into(),
            }],
            diagnostics: vec![],
        };
    }

    if matches!(intent, StepIntent::Interact) {
        if let Some(target) = extract_after_any(&normalized, &["the user taps ", "user taps "]) {
            return LoweredStep {
                action: ActionKind::Tap {
                    target: phrase_to_selector(target),
                },
                guards: vec![],
                postconditions: vec![],
                diagnostics: vec![],
            };
        }

        if let Some((text, target)) = extract_text_entry(&normalized) {
            return LoweredStep {
                action: ActionKind::TypeText {
                    target: phrase_to_selector(&target),
                    text,
                },
                guards: vec![],
                postconditions: vec![],
                diagnostics: vec![],
            };
        }

        if normalized.contains("take a screenshot") || normalized.contains("takes a screenshot") {
            return LoweredStep {
                action: ActionKind::TakeScreenshot { name: None },
                guards: vec![],
                postconditions: vec![],
                diagnostics: vec![],
            };
        }
    }

    if matches!(intent, StepIntent::Assert) {
        if let Some(target) = normalized.strip_suffix(" is visible") {
            let selector = phrase_to_selector(target);
            return LoweredStep {
                action: ActionKind::Noop,
                guards: vec![WaitKind::ForAssertion {
                    assertion: AssertionKind::Visible {
                        target: selector.clone(),
                    },
                }],
                postconditions: vec![AssertionKind::Visible { target: selector }],
                diagnostics: vec![],
            };
        }

        if let Some(target) = normalized.strip_suffix(" exists") {
            let selector = phrase_to_selector(target);
            return LoweredStep {
                action: ActionKind::Noop,
                guards: vec![WaitKind::ForAssertion {
                    assertion: AssertionKind::Exists {
                        target: selector.clone(),
                    },
                }],
                postconditions: vec![AssertionKind::Exists { target: selector }],
                diagnostics: vec![],
            };
        }

        if let Some((target, value)) = extract_text_equals_assertion(&normalized) {
            let selector = phrase_to_selector(&target);
            return LoweredStep {
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![AssertionKind::TextEquals {
                    target: selector,
                    value,
                }],
                diagnostics: vec![],
            };
        }

        if normalized.contains("app is launched") || normalized.contains("app is in foreground") {
            return LoweredStep {
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![AssertionKind::AppInForeground {
                    app_id: "app.under.test".into(),
                }],
                diagnostics: vec![],
            };
        }
    }

    LoweredStep {
        action: ActionKind::Noop,
        guards: vec![],
        postconditions: vec![],
        diagnostics: vec![CompilationDiagnostic {
            severity: DiagnosticSeverity::Warning,
            message: format!(
                "step lowered to noop because no deterministic lowering rule matched: {description}"
            ),
            location: Some(format!("line {line_number}")),
        }],
    }
}

pub(crate) fn render_intent(intent: &StepIntent) -> &'static str {
    match intent {
        StepIntent::Setup => "setup",
        StepIntent::Navigate => "navigation",
        StepIntent::Interact => "interaction",
        StepIntent::Observe => "observation",
        StepIntent::Assert => "assertion",
        StepIntent::Cleanup => "cleanup",
    }
}
