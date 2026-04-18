use std::{
    collections::BTreeMap,
    path::PathBuf,
    sync::{Mutex, OnceLock},
    time::{SystemTime, UNIX_EPOCH},
};

use domain::{
    ActionKind, ArtifactPolicy, AssertionKind, CapabilitySet, ExecutablePlan, ExecutionDefaults,
    FailurePolicy, PlanFormatVersion, PlanSource, PlanStep, RetryPolicy, Selector, SourceKind,
    StepIntent, TargetPlatform, TargetProfile,
};

pub(crate) fn smoke_fixture_plan() -> ExecutablePlan {
    ExecutablePlan {
        plan_id: "increment-the-counter-once".into(),
        name: "Increment the counter once".into(),
        version: PlanFormatVersion { major: 1, minor: 0 },
        source: PlanSource {
            kind: SourceKind::Gherkin,
            source_name: "tests/test-support/fixtures/ios-smoke/features/tap_counter.feature"
                .into(),
            compiler_version: "0.1.0".into(),
        },
        target: TargetProfile {
            platform: TargetPlatform::Ios,
            device_class: "simulator".into(),
        },
        capabilities_required: CapabilitySet {
            capabilities: vec!["screenshot".into()],
        },
        defaults: ExecutionDefaults::default(),
        steps: vec![
            PlanStep {
                step_id: "increment-the-counter-once-001".into(),
                intent: StepIntent::Setup,
                description: "the app is launched".into(),
                action: ActionKind::LaunchApp {
                    app_id: "app.under.test".into(),
                },
                guards: vec![],
                postconditions: vec![AssertionKind::AppInForeground {
                    app_id: "app.under.test".into(),
                }],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-002".into(),
                intent: StepIntent::Interact,
                description: "the user taps tap button".into(),
                action: ActionKind::Tap {
                    target: Selector::AccessibilityId("tap-button".into()),
                },
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-003".into(),
                intent: StepIntent::Assert,
                description: "count label text is \"Count: 1\"".into(),
                action: ActionKind::Noop,
                guards: vec![],
                postconditions: vec![AssertionKind::TextEquals {
                    target: Selector::AccessibilityId("count-label".into()),
                    value: "Count: 1".into(),
                }],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
            PlanStep {
                step_id: "increment-the-counter-once-004".into(),
                intent: StepIntent::Interact,
                description: "the user takes a screenshot".into(),
                action: ActionKind::TakeScreenshot {
                    name: Some("tap-counter".into()),
                },
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            },
        ],
        metadata: BTreeMap::new(),
    }
}

pub(crate) fn temp_path(prefix: &str) -> PathBuf {
    std::env::temp_dir().join(format!(
        "{prefix}-{}",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock should move forward")
            .as_nanos()
    ))
}

pub(crate) fn env_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}
