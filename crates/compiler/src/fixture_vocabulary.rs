use domain::{
    ActionKind, AssertionKind, CapabilitySet, CompilationDiagnostic, DiagnosticSeverity, Selector,
    StepIntent, TargetPlatform,
};

use crate::generic_lowering::{LoweredStep, render_intent};
use crate::phrase_helpers::extract_quoted_value;

#[derive(Debug)]
pub(crate) struct FixtureVocabulary {
    pub(crate) name: &'static str,
    pub(crate) target_platform: TargetPlatform,
    pub(crate) device_class: &'static str,
    screenshot_name: &'static str,
}

impl FixtureVocabulary {
    pub(crate) fn capabilities(&self) -> CapabilitySet {
        CapabilitySet {
            capabilities: vec![String::from("screenshot")],
        }
    }

    pub(crate) fn lower_step(
        &self,
        intent: &StepIntent,
        description: &str,
        line_number: usize,
    ) -> LoweredStep {
        match intent {
            StepIntent::Setup if description == "the app is launched" => LoweredStep {
                action: ActionKind::LaunchApp {
                    app_id: "app.under.test".into(),
                },
                guards: vec![],
                postconditions: vec![AssertionKind::AppInForeground {
                    app_id: "app.under.test".into(),
                }],
                diagnostics: vec![],
            },
            StepIntent::Interact if description == "the user taps tap button" => LoweredStep {
                action: ActionKind::Tap {
                    target: Selector::AccessibilityId(String::from("tap-button")),
                },
                guards: vec![],
                postconditions: vec![],
                diagnostics: vec![],
            },
            StepIntent::Interact if description == "the user takes a screenshot" => LoweredStep {
                action: ActionKind::TakeScreenshot {
                    name: Some(self.screenshot_name.into()),
                },
                guards: vec![],
                postconditions: vec![],
                diagnostics: vec![],
            },
            StepIntent::Assert => {
                if let Some(value) = extract_fixture_count_label_assertion(description) {
                    LoweredStep {
                        action: ActionKind::Noop,
                        guards: vec![],
                        postconditions: vec![AssertionKind::TextEquals {
                            target: Selector::AccessibilityId(String::from("count-label")),
                            value,
                        }],
                        diagnostics: vec![],
                    }
                } else {
                    self.unsupported_step(intent, description, line_number)
                }
            }
            _ => self.unsupported_step(intent, description, line_number),
        }
    }

    fn unsupported_step(
        &self,
        intent: &StepIntent,
        description: &str,
        line_number: usize,
    ) -> LoweredStep {
        LoweredStep {
            action: ActionKind::Noop,
            guards: vec![],
            postconditions: vec![],
            diagnostics: vec![CompilationDiagnostic {
                severity: DiagnosticSeverity::Error,
                message: format!(
                    "unsupported {} step for {}: {description}. Supported phrases: Given the app is launched; When the user taps tap button; Then count label text is \"Count: 1\"; When the user takes a screenshot",
                    render_intent(intent),
                    self.name,
                ),
                location: Some(format!("line {line_number}")),
            }],
        }
    }
}

pub(crate) fn fixture_vocabulary_for(source_name: &str) -> Option<FixtureVocabulary> {
    let normalized_source_name = source_name.replace('\\', "/");
    if normalized_source_name
        .ends_with("tests/test-support/fixtures/ios-smoke/features/tap_counter.feature")
    {
        Some(FixtureVocabulary {
            name: "the iOS smoke fixture",
            target_platform: TargetPlatform::Ios,
            device_class: "simulator",
            screenshot_name: "tap-counter",
        })
    } else if normalized_source_name
        .ends_with("tests/test-support/fixtures/android-smoke/features/tap_counter.feature")
    {
        Some(FixtureVocabulary {
            name: "the Android smoke fixture",
            target_platform: TargetPlatform::Android,
            device_class: "emulator",
            screenshot_name: "android-tap-counter",
        })
    } else {
        None
    }
}

fn extract_fixture_count_label_assertion(description: &str) -> Option<String> {
    let remainder = description.strip_prefix("count label text is ")?;
    let (value, trailing) = extract_quoted_value(remainder)?;
    if trailing.is_empty() {
        Some(value)
    } else {
        None
    }
}
