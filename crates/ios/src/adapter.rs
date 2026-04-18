use domain::{
    ActionKind, ArtifactRef, DeviceDescriptor, DeviceEngine, DeviceSnapshot, FailureCode,
    ObservedElement, RuntimeFailure, Selector, StringMatchKind, TargetPlatform, UiRole,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IosSimulatorDescriptor {
    pub name: String,
    pub os_version: String,
}

impl IosSimulatorDescriptor {
    pub fn new(name: impl Into<String>, os_version: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            os_version: os_version.into(),
        }
    }

    pub fn iphone_16() -> Self {
        Self::new("iPhone 16", "18.0")
    }

    fn into_device_descriptor(self) -> DeviceDescriptor {
        DeviceDescriptor {
            platform: TargetPlatform::Ios,
            name: self.name,
            os_version: self.os_version,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IosSimulatorSnapshot {
    pub descriptor: DeviceDescriptor,
    pub device_snapshot: DeviceSnapshot,
}

impl IosSimulatorSnapshot {
    pub fn new(descriptor: DeviceDescriptor, device_snapshot: DeviceSnapshot) -> Self {
        Self {
            descriptor,
            device_snapshot,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FixtureMode {
    Login,
    TapCounterSmoke,
}

#[derive(Debug, Clone)]
pub struct IosSimulatorAdapter {
    descriptor: DeviceDescriptor,
    snapshot: DeviceSnapshot,
    screenshot_counter: u32,
    fixture_mode: FixtureMode,
    tap_count: u32,
}

impl IosSimulatorAdapter {
    pub fn new(descriptor: IosSimulatorDescriptor) -> Self {
        Self {
            descriptor: descriptor.into_device_descriptor(),
            snapshot: login_fixture_snapshot(),
            screenshot_counter: 0,
            fixture_mode: FixtureMode::Login,
            tap_count: 0,
        }
    }

    pub fn smoke_fixture(descriptor: IosSimulatorDescriptor) -> Self {
        Self {
            descriptor: descriptor.into_device_descriptor(),
            snapshot: tap_counter_fixture_snapshot(),
            screenshot_counter: 0,
            fixture_mode: FixtureMode::TapCounterSmoke,
            tap_count: 0,
        }
    }

    pub fn snapshot(&self) -> Result<IosSimulatorSnapshot, RuntimeFailure> {
        Ok(IosSimulatorSnapshot::new(
            self.descriptor.clone(),
            self.snapshot.clone(),
        ))
    }

    fn ensure_home_screen(&mut self) {
        let already_present = self
            .snapshot
            .elements
            .iter()
            .any(|element| element.accessibility_id.as_deref() == Some("home_title"));

        if !already_present {
            self.snapshot.elements.push(ObservedElement {
                resource_id: None,
                accessibility_id: Some("home_title".into()),
                role: Some(UiRole::StaticText),
                text: Some("Home".into()),
                label: Some("Home".into()),
                visible: true,
            });
        }
    }

    fn update_tap_counter_label(&mut self) {
        let value = format!("Count: {}", self.tap_count);
        if let Some(element) = self
            .snapshot
            .elements
            .iter_mut()
            .find(|element| element.accessibility_id.as_deref() == Some("count-label"))
        {
            element.text = Some(value.clone());
            element.label = Some(value);
            element.visible = true;
            return;
        }

        self.snapshot.elements.push(ObservedElement {
            resource_id: None,
            accessibility_id: Some("count-label".into()),
            role: Some(UiRole::StaticText),
            text: Some(value.clone()),
            label: Some(value),
            visible: true,
        });
    }
}

impl DeviceEngine for IosSimulatorAdapter {
    fn descriptor(&self) -> DeviceDescriptor {
        self.descriptor.clone()
    }

    fn perform_action(&mut self, action: &ActionKind) -> Result<Vec<ArtifactRef>, RuntimeFailure> {
        match action {
            ActionKind::Noop => Ok(Vec::new()),
            ActionKind::LaunchApp { app_id } => {
                self.snapshot.foreground_app = Some(app_id.clone());
                Ok(Vec::new())
            }
            ActionKind::OpenDeepLink { url } => {
                self.snapshot.foreground_app = Some("app.under.test".into());
                if url.to_lowercase().contains("home") {
                    self.ensure_home_screen();
                }
                Ok(Vec::new())
            }
            ActionKind::Tap { target } => {
                let tapped_element =
                    find_element(&self.snapshot, target)
                        .cloned()
                        .ok_or(RuntimeFailure {
                            code: FailureCode::UnresolvedSelector,
                            message: format!("selector was not found: {target:?}"),
                        })?;
                let tapped_label = tapped_element
                    .label
                    .clone()
                    .or_else(|| tapped_element.text.clone())
                    .unwrap_or_default();

                if tapped_label.to_lowercase().contains("login") {
                    self.ensure_home_screen();
                }

                if self.fixture_mode == FixtureMode::TapCounterSmoke
                    && tapped_element.accessibility_id.as_deref() == Some("tap-button")
                {
                    self.tap_count += 1;
                    self.update_tap_counter_label();
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
            ActionKind::TakeScreenshot { name } => {
                self.screenshot_counter += 1;
                let base = sanitize_artifact_name(name.as_deref());
                Ok(vec![ArtifactRef {
                    artifact_id: format!("{base}-{}", self.screenshot_counter),
                    artifact_type: "screenshot".into(),
                    path: format!("artifacts/{base}-{}.png", self.screenshot_counter),
                    sha256: None,
                    step_id: None,
                }])
            }
        }
    }

    fn snapshot(&self) -> Result<DeviceSnapshot, RuntimeFailure> {
        Ok(self.snapshot.clone())
    }
}

fn login_fixture_snapshot() -> DeviceSnapshot {
    DeviceSnapshot {
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
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("password_field".into()),
                role: Some(UiRole::TextField),
                text: Some(String::new()),
                label: Some("Password".into()),
                visible: true,
            },
        ],
        foreground_app: None,
    }
}

fn tap_counter_fixture_snapshot() -> DeviceSnapshot {
    DeviceSnapshot {
        elements: vec![
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("tap-button".into()),
                role: Some(UiRole::Button),
                text: Some("Tap".into()),
                label: Some("Tap".into()),
                visible: true,
            },
            ObservedElement {
                resource_id: None,
                accessibility_id: Some("count-label".into()),
                role: Some(UiRole::StaticText),
                text: Some("Count: 0".into()),
                label: Some("Count: 0".into()),
                visible: true,
            },
        ],
        foreground_app: None,
    }
}

fn sanitize_artifact_name(name: Option<&str>) -> String {
    let sanitized = name
        .unwrap_or("screenshot")
        .trim()
        .chars()
        .map(|character| match character {
            'a'..='z' | 'A'..='Z' | '0'..='9' | '-' | '_' => character,
            _ => '-',
        })
        .collect::<String>()
        .trim_matches('-')
        .to_string();

    if sanitized.is_empty() {
        String::from("screenshot")
    } else {
        sanitized
    }
}

fn find_element<'a>(
    snapshot: &'a DeviceSnapshot,
    selector: &Selector,
) -> Option<&'a ObservedElement> {
    snapshot
        .elements
        .iter()
        .find(|element| element_matches_selector(element, selector))
}

fn element_matches_selector(element: &ObservedElement, selector: &Selector) -> bool {
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
