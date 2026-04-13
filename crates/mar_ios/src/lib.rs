use mar_domain::{
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

#[derive(Debug, Clone)]
pub struct IosSimulatorAdapter {
    descriptor: DeviceDescriptor,
    snapshot: DeviceSnapshot,
    screenshot_counter: u32,
}

impl IosSimulatorAdapter {
    pub fn new(descriptor: IosSimulatorDescriptor) -> Self {
        Self {
            descriptor: descriptor.into_device_descriptor(),
            snapshot: login_fixture_snapshot(),
            screenshot_counter: 0,
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
                let tapped_label = find_element(&self.snapshot, target)
                    .and_then(|element| element.label.clone().or_else(|| element.text.clone()))
                    .ok_or(RuntimeFailure {
                        code: FailureCode::UnresolvedSelector,
                        message: format!("selector was not found: {target:?}"),
                    })?;

                if tapped_label.to_lowercase().contains("login") {
                    self.ensure_home_screen();
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

#[cfg(test)]
mod tests {
    use mar_domain::{ActionKind, DeviceEngine, FailureCode, Selector, TargetPlatform};

    use super::{IosSimulatorAdapter, IosSimulatorDescriptor};

    #[test]
    fn ios_adapter_exposes_descriptor_and_snapshot() {
        let adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());
        let descriptor = adapter.descriptor();
        assert_eq!(descriptor.platform, TargetPlatform::Ios);

        let snapshot = adapter.snapshot().expect("snapshot should succeed");
        assert_eq!(snapshot.descriptor.platform, TargetPlatform::Ios);
    }

    #[test]
    fn ios_adapter_handles_core_actions() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        adapter
            .perform_action(&ActionKind::LaunchApp {
                app_id: "app.under.test".into(),
            })
            .expect("launch should succeed");

        adapter
            .perform_action(&ActionKind::Tap {
                target: Selector::AccessibilityId("login_button".into()),
            })
            .expect("tap should succeed");

        adapter
            .perform_action(&ActionKind::TypeText {
                target: Selector::AccessibilityId("email_field".into()),
                text: "tester@example.com".into(),
            })
            .expect("type should succeed");

        let artifacts = adapter
            .perform_action(&ActionKind::TakeScreenshot {
                name: Some("login".into()),
            })
            .expect("screenshot should succeed");
        assert_eq!(artifacts.len(), 1);
        assert_eq!(artifacts[0].artifact_type, "screenshot");

        let snapshot = adapter.snapshot().expect("snapshot should succeed");
        assert_eq!(snapshot.descriptor.platform, TargetPlatform::Ios);
        assert!(snapshot
            .device_snapshot
            .elements
            .iter()
            .any(
                |element| element.accessibility_id.as_deref() == Some("email_field")
                    && element.text.as_deref() == Some("tester@example.com")
            ));
    }

    #[test]
    fn ios_adapter_sanitizes_screenshot_names() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        let artifacts = adapter
            .perform_action(&ActionKind::TakeScreenshot {
                name: Some("../nested/login capture.png".into()),
            })
            .expect("screenshot should succeed");

        assert_eq!(artifacts[0].artifact_id, "nested-login-capture-png-1");
        assert_eq!(
            artifacts[0].path,
            "artifacts/nested-login-capture-png-1.png"
        );
    }

    #[test]
    fn ios_adapter_reports_unresolved_selectors() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        let error = adapter
            .perform_action(&ActionKind::Tap {
                target: Selector::AccessibilityId("missing_button".into()),
            })
            .expect_err("missing selector should fail");

        assert_eq!(error.code, FailureCode::UnresolvedSelector);
    }

    #[test]
    fn ios_adapter_open_deep_link_reveals_home_screen() {
        let mut adapter = IosSimulatorAdapter::new(IosSimulatorDescriptor::iphone_16());

        adapter
            .perform_action(&ActionKind::OpenDeepLink {
                url: "casgrain://home".into(),
            })
            .expect("deep link should succeed");

        let snapshot = DeviceEngine::snapshot(&adapter).expect("snapshot should succeed");
        assert_eq!(snapshot.foreground_app.as_deref(), Some("app.under.test"));
        assert!(snapshot
            .elements
            .iter()
            .any(|element| element.accessibility_id.as_deref() == Some("home_title")));
    }
}
