use domain::{
    ActionKind, AssertionKind, ExecutablePlan, FailureCode, RuntimeFailure, Selector,
    TargetPlatform,
};

pub(crate) fn validate_supported_smoke_plan(plan: &ExecutablePlan) -> Result<(), RuntimeFailure> {
    if plan.target.platform != TargetPlatform::Ios {
        return Err(unsupported_fixture_plan(
            "fixture bridge only supports iOS-targeted plans",
        ));
    }

    let [launch_step, tap_step, assert_step, screenshot_step] = plan.steps.as_slice() else {
        return Err(unsupported_fixture_plan(
            "fixture bridge currently supports exactly four tap-counter steps",
        ));
    };

    match &launch_step.action {
        ActionKind::LaunchApp { app_id } if app_id == "app.under.test" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "first smoke step must launch the fixture app",
            ));
        }
    }

    match launch_step.postconditions.as_slice() {
        [AssertionKind::AppInForeground { app_id }] if app_id == "app.under.test" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "launch step must assert the fixture app is in the foreground",
            ));
        }
    }

    match &tap_step.action {
        ActionKind::Tap {
            target: Selector::AccessibilityId(value),
        } if value == "tap-button" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "second smoke step must tap accessibility id tap-button",
            ));
        }
    }

    if !tap_step.postconditions.is_empty() {
        return Err(unsupported_fixture_plan(
            "tap step must rely on the later assertion instead of extra postconditions",
        ));
    }

    if !matches!(assert_step.action, ActionKind::Noop) {
        return Err(unsupported_fixture_plan(
            "third smoke step must be an assertion-only noop action",
        ));
    }

    match assert_step.postconditions.as_slice() {
        [
            AssertionKind::TextEquals {
                target: Selector::AccessibilityId(value),
                value: expected_text,
            },
        ] if value == "count-label" && expected_text == "Count: 1" => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "assert step must verify accessibility id count-label equals Count: 1",
            ));
        }
    }

    match &screenshot_step.action {
        ActionKind::TakeScreenshot { name } if name.as_deref() == Some("tap-counter") => {}
        _ => {
            return Err(unsupported_fixture_plan(
                "final smoke step must capture screenshot tap-counter",
            ));
        }
    }

    Ok(())
}

fn unsupported_fixture_plan(message: &str) -> RuntimeFailure {
    RuntimeFailure {
        code: FailureCode::UnsupportedAction,
        message: message.into(),
    }
}
