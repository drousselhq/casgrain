use std::{fs, path::PathBuf};

use domain::{
    ActionKind, AssertionKind, DiagnosticSeverity, Selector, StepIntent, StringMatchKind,
    TargetPlatform, WaitKind,
};
use serde_json::{Value, json};

use crate::compile_gherkin;

fn assert_compiled_plan_matches_golden(
    source: &str,
    source_name: &str,
    golden_relative_path: &str,
) {
    let output = compile_gherkin(source, source_name, "0.1.0")
        .expect("fixture feature should compile to a golden-backed plan");
    let actual = serde_json::to_string_pretty(&output.plan)
        .expect("compiled plan should serialize to pretty json");
    let expected_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(golden_relative_path);
    let expected = fs::read_to_string(&expected_path)
        .unwrap_or_else(|error| panic!("failed to read golden file {expected_path:?}: {error}"));

    assert_eq!(actual, expected);
}

fn compile_fixture_plan_value(source: &str, source_name: &str) -> Value {
    let output = compile_gherkin(source, source_name, "0.1.0")
        .expect("fixture feature should compile to a shared mobile plan");

    serde_json::to_value(&output.plan).expect("compiled plan should serialize to json")
}

fn normalize_shared_mobile_tap_counter_plan(plan: &mut Value) {
    plan["source"]["name"] =
        json!("tests/test-support/fixtures/mobile-smoke/features/tap_counter.feature");
    plan["source"]["source_name"] =
        json!("tests/test-support/fixtures/mobile-smoke/features/tap_counter.feature");
    plan["target"]["platform"] = json!("mobile");
    plan["target"]["device_class"] = json!("shared-mobile-smoke");
    plan["metadata"]["feature_name"] = json!("Shared mobile smoke tap counter");

    let steps = plan["steps"]
        .as_array_mut()
        .expect("compiled plan should expose step array");
    let screenshot_step = steps
        .iter_mut()
        .find(|step| step["action"]["kind"] == "take_screenshot")
        .expect("shared mobile plan should include a screenshot step");
    screenshot_step["action"]["name"] = json!("tap-counter");
}

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
    assert_eq!(first.plan.source.kind, domain::SourceKind::Gherkin);
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
        [AssertionKind::Visible { target: Selector::Text(text) }] if text.value == "home"
    ));
}

#[test]
fn ios_fixture_feature_compiles_to_ios_specific_deterministic_selectors() {
    let source =
        include_str!("../../../tests/test-support/fixtures/ios-smoke/features/tap_counter.feature");

    let output = compile_gherkin(
        source,
        "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature",
        "0.1.0",
    )
    .unwrap();
    let steps = output.plan.steps;

    assert_eq!(output.plan.target.platform, TargetPlatform::Ios);
    assert_eq!(output.plan.target.device_class, "simulator");
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
fn android_fixture_feature_compiles_to_android_specific_deterministic_selectors() {
    let source = include_str!(
        "../../../tests/test-support/fixtures/android-smoke/features/tap_counter.feature"
    );

    let output = compile_gherkin(
        source,
        "tests/test-support/fixtures/android-smoke/features/tap_counter.feature",
        "0.1.0",
    )
    .unwrap();
    let steps = output.plan.steps;

    assert_eq!(output.plan.target.platform, TargetPlatform::Android);
    assert_eq!(output.plan.target.device_class, "emulator");
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
        ActionKind::TakeScreenshot { name: Some(ref name) } if name == "android-tap-counter"
    ));
}

#[test]
fn ios_tap_counter_fixture_matches_the_golden_plan_json() {
    let source =
        include_str!("../../../tests/test-support/fixtures/ios-smoke/features/tap_counter.feature");

    assert_compiled_plan_matches_golden(
        source,
        "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature",
        "tests/test-support/golden/compiler/ios_tap_counter.plan.json",
    );
}

#[test]
fn android_tap_counter_fixture_matches_the_golden_plan_json() {
    let source = include_str!(
        "../../../tests/test-support/fixtures/android-smoke/features/tap_counter.feature"
    );

    assert_compiled_plan_matches_golden(
        source,
        "tests/test-support/fixtures/android-smoke/features/tap_counter.feature",
        "tests/test-support/golden/compiler/android_tap_counter.plan.json",
    );
}

#[test]
fn ios_and_android_tap_counter_fixtures_keep_the_same_shared_mobile_contract() {
    let ios_source =
        include_str!("../../../tests/test-support/fixtures/ios-smoke/features/tap_counter.feature");
    let android_source = include_str!(
        "../../../tests/test-support/fixtures/android-smoke/features/tap_counter.feature"
    );

    let mut ios_plan = compile_fixture_plan_value(
        ios_source,
        "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature",
    );
    let mut android_plan = compile_fixture_plan_value(
        android_source,
        "tests/test-support/fixtures/android-smoke/features/tap_counter.feature",
    );

    normalize_shared_mobile_tap_counter_plan(&mut ios_plan);
    normalize_shared_mobile_tap_counter_plan(&mut android_plan);

    assert_eq!(ios_plan, android_plan);

    let mut selector_drift = android_plan.clone();
    selector_drift["steps"][1]["action"]["target"]["value"] = json!("other-button");
    assert_ne!(
        ios_plan, selector_drift,
        "shared mobile parity guard must fail when selector semantics drift"
    );

    let mut execution_policy_drift = android_plan.clone();
    execution_policy_drift["defaults"]["step_timeout_ms"] = json!(6_000);
    assert_ne!(
        ios_plan, execution_policy_drift,
        "shared mobile parity guard must fail when execution policy drifts"
    );
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
        "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature",
        "0.1.0",
    )
    .expect_err("fixture vocabulary should reject nearby unsupported phrases");

    assert_eq!(errors.len(), 2);
    assert!(
        errors
            .iter()
            .all(|diagnostic| diagnostic.severity == DiagnosticSeverity::Error)
    );
    assert!(errors[0].message.contains("When the user taps tap button"));
    assert!(errors[0].location.as_deref() == Some("line 5"));
    assert!(
        errors[1]
            .message
            .contains("Then count label text is \"Count: 1\"")
    );
    assert!(errors[1].location.as_deref() == Some("line 6"));
}

#[test]
fn android_fixture_rejects_nearby_unsupported_phrases_with_structured_errors() {
    let source = r#"
Feature: Android smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps the tap button
    Then "Count: 1" is displayed
"#;

    let errors = compile_gherkin(
        source,
        "tests/test-support/fixtures/android-smoke/features/tap_counter.feature",
        "0.1.0",
    )
    .expect_err("fixture vocabulary should reject nearby unsupported phrases");

    assert_eq!(errors.len(), 2);
    assert!(
        errors
            .iter()
            .all(|diagnostic| diagnostic.severity == DiagnosticSeverity::Error)
    );
    assert!(
        errors[0]
            .message
            .contains("unsupported interaction step for the Android smoke fixture")
    );
    assert!(errors[0].message.contains("When the user taps tap button"));
    assert!(errors[0].location.as_deref() == Some("line 5"));
    assert!(
        errors[1]
            .message
            .contains("unsupported assertion step for the Android smoke fixture")
    );
    assert!(
        errors[1]
            .message
            .contains("Then count label text is \"Count: 1\"")
    );
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

#[test]
fn demo_login_feature_matches_the_golden_plan_json() {
    let source = include_str!("../../../docs/gherkin/demo-login.feature");

    assert_compiled_plan_matches_golden(
        source,
        "docs/gherkin/demo-login.feature",
        "tests/test-support/golden/compiler/demo_login.plan.json",
    );
}
