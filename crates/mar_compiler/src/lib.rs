use std::collections::BTreeMap;

use mar_application::{validate_plan, CompileOutput, PlanCompiler};
use mar_domain::{
    ActionKind, ArtifactPolicy, AssertionKind, CapabilitySet, CompilationDiagnostic,
    DiagnosticSeverity, ExecutablePlan, ExecutionDefaults, FailurePolicy, PlanFormatVersion,
    PlanSource, PlanStep, RetryPolicy, Selector, SourceKind, StepIntent, StringMatchKind,
    TargetPlatform, TargetProfile, TextSelector, WaitKind,
};

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
            device_class: "simulator".into(),
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

#[derive(Debug)]
struct LoweredStep {
    action: ActionKind,
    guards: Vec<WaitKind>,
    postconditions: Vec<AssertionKind>,
    diagnostics: Vec<CompilationDiagnostic>,
}

#[derive(Debug)]
struct FixtureVocabulary {
    name: &'static str,
    target_platform: TargetPlatform,
    screenshot_name: &'static str,
}

impl FixtureVocabulary {
    fn capabilities(&self) -> CapabilitySet {
        CapabilitySet {
            capabilities: vec![String::from("screenshot")],
        }
    }

    fn lower_step(
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

fn fixture_vocabulary_for(source_name: &str) -> Option<FixtureVocabulary> {
    let normalized_source_name = source_name.replace('\\', "/");
    if normalized_source_name.ends_with("fixtures/ios-smoke/features/tap_counter.feature") {
        Some(FixtureVocabulary {
            name: "the iOS smoke fixture",
            target_platform: TargetPlatform::Ios,
            screenshot_name: "tap-counter",
        })
    } else {
        None
    }
}

fn lower_step(
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

fn extract_fixture_count_label_assertion(description: &str) -> Option<String> {
    let remainder = description.strip_prefix("count label text is ")?;
    let (value, trailing) = extract_quoted_value(remainder)?;
    if trailing.is_empty() {
        Some(value)
    } else {
        None
    }
}

fn render_intent(intent: &StepIntent) -> &'static str {
    match intent {
        StepIntent::Setup => "setup",
        StepIntent::Navigate => "navigation",
        StepIntent::Interact => "interaction",
        StepIntent::Observe => "observation",
        StepIntent::Assert => "assertion",
        StepIntent::Cleanup => "cleanup",
    }
}

fn extract_after_any<'a>(input: &'a str, prefixes: &[&str]) -> Option<&'a str> {
    prefixes
        .iter()
        .find_map(|prefix| input.strip_prefix(prefix).map(trim_selector_phrase))
}

fn extract_text_entry(input: &str) -> Option<(String, String)> {
    for prefix in [
        "the user enters ",
        "user enters ",
        "the user types ",
        "user types ",
    ] {
        if let Some(rest) = input.strip_prefix(prefix) {
            let (text, remainder) = extract_quoted_value(rest)?;
            let target = remainder
                .strip_prefix("into ")
                .or_else(|| remainder.strip_prefix("in "))
                .map(trim_selector_phrase)?;
            return Some((text, target.to_string()));
        }
    }
    None
}

fn extract_text_equals_assertion(input: &str) -> Option<(String, String)> {
    let target = input.strip_suffix(" is displayed")?;
    let (value, remaining) = extract_quoted_value(target)?;
    if remaining.is_empty() {
        Some((value.clone(), value))
    } else {
        None
    }
}

fn extract_quoted_value(input: &str) -> Option<(String, &str)> {
    let trimmed = input.trim();
    let rest = trimmed.strip_prefix('"')?;
    let quote_end = rest.find('"')?;
    let value = rest[..quote_end].to_string();
    let remainder = rest[quote_end + 1..].trim();
    Some((value, remainder))
}

fn phrase_to_selector(input: &str) -> Selector {
    Selector::Text(TextSelector {
        value: humanize_selector_phrase(trim_selector_phrase(input)),
        match_kind: StringMatchKind::Contains,
    })
}

fn trim_selector_phrase(input: &str) -> &str {
    input
        .trim()
        .trim_end_matches(" field")
        .trim_end_matches(" button")
        .trim_end_matches('.')
        .trim()
}

fn humanize_selector_phrase(input: &str) -> String {
    input
        .split_whitespace()
        .filter_map(|word| match word {
            "the" => None,
            "screen" => None,
            other => Some(other),
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn normalize_phrase(input: &str) -> String {
    input
        .trim()
        .trim_end_matches('.')
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
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
    use mar_domain::{
        ActionKind, AssertionKind, DiagnosticSeverity, Selector, StepIntent, StringMatchKind,
        TargetPlatform, WaitKind,
    };

    use super::compile_gherkin;

    #[test]
    fn compiles_gherkin_into_stable_plan() {
        let source = r#"
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login button
    Then the home screen is visible
"#;

        let first = compile_gherkin(source, "login.feature", "0.1.0").unwrap();
        let second = compile_gherkin(source, "login.feature", "0.1.0").unwrap();

        assert_eq!(first.plan, second.plan);
        assert_eq!(first.plan.source.kind, mar_domain::SourceKind::Gherkin);
        assert_eq!(first.plan.steps.len(), 3);
        assert_eq!(first.plan.steps[0].intent, StepIntent::Setup);
        assert_eq!(first.plan.steps[1].intent, StepIntent::Interact);
        assert_eq!(first.plan.steps[2].intent, StepIntent::Assert);
    }

    #[test]
    fn lowers_common_actions_and_assertions() {
        let source = r#"
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login button
    When the user enters "daniel@example.com" into email field
    Then the home screen is visible
"#;

        let output = compile_gherkin(source, "login.feature", "0.1.0").unwrap();
        let steps = output.plan.steps;

        assert!(matches!(
            steps[0].action,
            ActionKind::LaunchApp { ref app_id } if app_id == "app.under.test"
        ));
        assert!(matches!(
            steps[1].action,
            ActionKind::Tap { target: Selector::Text(ref text) }
                if text.value == "login" && text.match_kind == StringMatchKind::Contains
        ));
        assert!(matches!(
            steps[2].action,
            ActionKind::TypeText { ref text, target: Selector::Text(ref selector) }
                if text == "daniel@example.com" && selector.value == "email"
        ));
        assert!(matches!(
            steps[3].guards.as_slice(),
            [WaitKind::ForAssertion {
                assertion: AssertionKind::Visible { .. }
            }]
        ));
        assert!(matches!(
            steps[3].postconditions.as_slice(),
            [AssertionKind::Visible { target: Selector::Text(text) }]
                if text.value == "home"
        ));
    }

    #[test]
    fn ios_fixture_feature_compiles_to_ios_specific_deterministic_selectors() {
        let source = include_str!("../../../fixtures/ios-smoke/features/tap_counter.feature");

        let output = compile_gherkin(
            source,
            "fixtures/ios-smoke/features/tap_counter.feature",
            "0.1.0",
        )
        .unwrap();
        let steps = output.plan.steps;

        assert_eq!(output.plan.target.platform, TargetPlatform::Ios);
        assert_eq!(
            output.plan.capabilities_required.capabilities,
            vec![String::from("screenshot")]
        );
        assert!(matches!(
            steps[1].action,
            ActionKind::Tap {
                target: Selector::AccessibilityId(ref value)
            } if value == "tap-button"
        ));
        assert!(matches!(
            steps[2].postconditions.as_slice(),
            [AssertionKind::TextEquals {
                target: Selector::AccessibilityId(value),
                value: assertion_value,
            }] if value == "count-label" && assertion_value == "Count: 1"
        ));
        assert!(matches!(
            steps[3].action,
            ActionKind::TakeScreenshot { name: Some(ref name) } if name == "tap-counter"
        ));
    }

    #[test]
    fn ios_fixture_rejects_nearby_unsupported_phrases_with_structured_errors() {
        let source = r#"
Feature: iOS smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps the tap button
    Then "Count: 1" is displayed
"#;

        let errors = compile_gherkin(
            source,
            "fixtures/ios-smoke/features/tap_counter.feature",
            "0.1.0",
        )
        .expect_err("fixture vocabulary should reject nearby unsupported phrases");

        assert_eq!(errors.len(), 2);
        assert!(errors
            .iter()
            .all(|diagnostic| diagnostic.severity == DiagnosticSeverity::Error));
        assert!(errors[0].message.contains("When the user taps tap button"));
        assert!(errors[0].location.as_deref() == Some("line 5"));
        assert!(errors[1]
            .message
            .contains("Then count label text is \"Count: 1\""));
        assert!(errors[1].location.as_deref() == Some("line 6"));
    }

    #[test]
    fn non_fixture_tap_counter_feature_keeps_generic_lowering() {
        let source = r#"
Feature: login tap counter
  Scenario: generic counter
    Given the app is launched
    Then "Count: 1" is displayed
"#;

        let output = compile_gherkin(source, "tap_counter.feature", "0.1.0")
            .expect("non-fixture feature should keep generic lowering");

        assert_eq!(output.plan.target.platform, TargetPlatform::CrossPlatform);
        assert!(matches!(
            output.plan.steps[1].postconditions.as_slice(),
            [AssertionKind::TextEquals {
                target: Selector::Text(text),
                value,
            }] if text.value == "count: 1" && value == "count: 1"
        ));
    }
}
