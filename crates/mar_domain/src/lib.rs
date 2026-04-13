use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use thiserror::Error;

pub type Timestamp = String;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutablePlan {
    pub plan_id: String,
    pub name: String,
    pub version: PlanFormatVersion,
    pub source: PlanSource,
    pub target: TargetProfile,
    pub capabilities_required: CapabilitySet,
    pub defaults: ExecutionDefaults,
    pub steps: Vec<PlanStep>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanFormatVersion {
    pub major: u16,
    pub minor: u16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanSource {
    pub kind: SourceKind,
    pub source_name: String,
    pub compiler_version: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    OpenSpec,
    Json,
    AgentDraft,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TargetProfile {
    pub platform: TargetPlatform,
    pub device_class: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TargetPlatform {
    Ios,
    Android,
    CrossPlatform,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct CapabilitySet {
    #[serde(default)]
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionDefaults {
    pub step_timeout_ms: u64,
    pub poll_interval_ms: u64,
    pub artifact_mode: ArtifactCaptureMode,
}

impl Default for ExecutionDefaults {
    fn default() -> Self {
        Self {
            step_timeout_ms: 5_000,
            poll_interval_ms: 250,
            artifact_mode: ArtifactCaptureMode::FailureOnly,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactCaptureMode {
    Never,
    FailureOnly,
    Always,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanStep {
    pub step_id: String,
    pub intent: StepIntent,
    pub description: String,
    pub action: ActionKind,
    #[serde(default)]
    pub guards: Vec<WaitKind>,
    #[serde(default)]
    pub postconditions: Vec<AssertionKind>,
    pub timeout_ms: u64,
    pub retry: RetryPolicy,
    pub on_failure: FailurePolicy,
    pub artifacts: ArtifactPolicy,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StepIntent {
    Setup,
    Navigate,
    Interact,
    Observe,
    Assert,
    Cleanup,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RetryPolicy {
    pub max_attempts: u8,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self { max_attempts: 1 }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailurePolicy {
    AbortRun,
    Continue,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArtifactPolicy {
    pub capture_on_failure: bool,
    pub capture_after_step: bool,
}

impl Default for ArtifactPolicy {
    fn default() -> Self {
        Self {
            capture_on_failure: true,
            capture_after_step: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind", content = "value")]
pub enum Selector {
    ResourceId(String),
    AccessibilityId(String),
    Text(TextSelector),
    Role(RoleSelector),
    Label(String),
    Placeholder(String),
    Hint(String),
    Trait(UiTrait),
    Path(UiPath),
    Coordinate(CoordinateSelector),
    Platform(PlatformSelector),
    AnyOf(Vec<Selector>),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TextSelector {
    pub value: String,
    pub match_kind: StringMatchKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoleSelector {
    pub role: UiRole,
    pub label: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UiRole {
    Button,
    TextField,
    StaticText,
    Image,
    Switch,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UiTrait {
    SecureInput,
    Selected,
    Header,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UiPath {
    pub segments: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoordinateSelector {
    pub x: i32,
    pub y: i32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlatformSelector {
    pub platform: TargetPlatform,
    pub expression: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StringMatchKind {
    Exact,
    Contains,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum ActionKind {
    LaunchApp { app_id: String },
    OpenDeepLink { url: String },
    Tap { target: Selector },
    TypeText { target: Selector, text: String },
    TakeScreenshot { name: Option<String> },
    Noop,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum AssertionKind {
    Exists { target: Selector },
    Visible { target: Selector },
    TextEquals { target: Selector, value: String },
    AppInForeground { app_id: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum WaitKind {
    ForAssertion { assertion: AssertionKind },
    ForTimeout { duration_ms: u64 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionTrace {
    pub run_id: String,
    pub plan_id: String,
    pub device: DeviceDescriptor,
    pub started_at: Timestamp,
    pub finished_at: Option<Timestamp>,
    pub status: RunStatus,
    pub steps: Vec<StepTrace>,
    #[serde(default)]
    pub artifacts: Vec<ArtifactRef>,
    #[serde(default)]
    pub diagnostics: Vec<CompilationDiagnostic>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunStatus {
    Passed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StepTrace {
    pub step_id: String,
    pub status: StepStatus,
    pub attempts: u8,
    pub failure: Option<FailureReport>,
    #[serde(default)]
    pub artifacts: Vec<ArtifactRef>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StepStatus {
    Passed,
    Failed,
    Skipped,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArtifactRef {
    pub artifact_id: String,
    pub artifact_type: String,
    pub path: String,
    pub sha256: Option<String>,
    pub step_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FailureReport {
    pub code: FailureCode,
    pub message: String,
    pub step_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureCode {
    UnsupportedAction,
    UnresolvedSelector,
    AssertionFailed,
    EngineError,
    CompilerError,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompilationDiagnostic {
    pub severity: DiagnosticSeverity,
    pub message: String,
    pub location: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticSeverity {
    Warning,
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DeviceDescriptor {
    pub platform: TargetPlatform,
    pub name: String,
    pub os_version: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct DeviceSnapshot {
    #[serde(default)]
    pub elements: Vec<ObservedElement>,
    pub foreground_app: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObservedElement {
    pub resource_id: Option<String>,
    pub accessibility_id: Option<String>,
    pub role: Option<UiRole>,
    pub text: Option<String>,
    pub label: Option<String>,
    pub visible: bool,
}

pub trait DeviceEngine {
    fn descriptor(&self) -> DeviceDescriptor;
    fn perform_action(&mut self, action: &ActionKind) -> Result<Vec<ArtifactRef>, RuntimeFailure>;
    fn snapshot(&self) -> Result<DeviceSnapshot, RuntimeFailure>;
}

#[derive(Debug, Clone, PartialEq, Eq, Error)]
#[error("{code:?}: {message}")]
pub struct RuntimeFailure {
    pub code: FailureCode,
    pub message: String,
}

pub fn plan_is_serialization_stable(plan: &ExecutablePlan) -> bool {
    let first = serde_json::to_string(plan).expect("plan should serialize");
    let second = serde_json::to_string(plan).expect("plan should serialize twice");
    first == second
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn executable_plan_round_trips_to_json() {
        let plan = ExecutablePlan {
            plan_id: "plan-login".into(),
            name: "Login Flow".into(),
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
            capabilities_required: CapabilitySet {
                capabilities: vec!["screenshot".into()],
            },
            defaults: ExecutionDefaults::default(),
            steps: vec![PlanStep {
                step_id: "step-1".into(),
                intent: StepIntent::Interact,
                description: "Tap login".into(),
                action: ActionKind::Tap {
                    target: Selector::Text(TextSelector {
                        value: "Login".into(),
                        match_kind: StringMatchKind::Exact,
                    }),
                },
                guards: vec![],
                postconditions: vec![],
                timeout_ms: 5_000,
                retry: RetryPolicy::default(),
                on_failure: FailurePolicy::AbortRun,
                artifacts: ArtifactPolicy::default(),
            }],
            metadata: BTreeMap::from([(String::from("source_lineage"), String::from("openspec"))]),
        };

        let json = serde_json::to_string_pretty(&plan).unwrap();
        let decoded: ExecutablePlan = serde_json::from_str(&json).unwrap();

        assert_eq!(plan, decoded);
        assert!(plan_is_serialization_stable(&decoded));
    }
}
