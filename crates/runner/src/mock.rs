use domain::{
    ActionKind, ArtifactRef, DeviceDescriptor, DeviceEngine, DeviceSnapshot, FailureCode,
    ObservedElement, RuntimeFailure, TargetPlatform, UiRole,
};

use crate::{element_matches_selector, find_element};

#[derive(Clone)]
pub struct MockDeviceEngine {
    descriptor: DeviceDescriptor,
    snapshot: DeviceSnapshot,
    screenshot_counter: u32,
}

impl MockDeviceEngine {
    pub fn new(descriptor: DeviceDescriptor, snapshot: DeviceSnapshot) -> Self {
        Self {
            descriptor,
            snapshot,
            screenshot_counter: 0,
        }
    }

    pub fn login_fixture() -> Self {
        Self::new(
            DeviceDescriptor {
                platform: TargetPlatform::Ios,
                name: "iPhone 16".into(),
                os_version: "18.0".into(),
            },
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
            },
        )
    }

    pub fn snapshot_state(&self) -> &DeviceSnapshot {
        &self.snapshot
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

impl DeviceEngine for MockDeviceEngine {
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
                let base = name
                    .as_deref()
                    .filter(|value| !value.trim().is_empty())
                    .unwrap_or("screenshot");
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

#[cfg(test)]
mod tests {
    use domain::{ActionKind, DeviceEngine, Selector, StringMatchKind, TextSelector};

    use super::MockDeviceEngine;

    #[test]
    fn login_fixture_contains_expected_controls() {
        let engine = MockDeviceEngine::login_fixture();
        let snapshot = engine.snapshot().expect("snapshot should succeed");
        assert!(
            snapshot
                .elements
                .iter()
                .any(|element| element.accessibility_id.as_deref() == Some("login_button"))
        );
        assert!(
            snapshot
                .elements
                .iter()
                .any(|element| element.accessibility_id.as_deref() == Some("email_field"))
        );
    }

    #[test]
    fn tapping_login_reveals_home_screen() {
        let mut engine = MockDeviceEngine::login_fixture();
        engine
            .perform_action(&ActionKind::Tap {
                target: Selector::Text(TextSelector {
                    value: "Login".into(),
                    match_kind: StringMatchKind::Contains,
                }),
            })
            .expect("tap should succeed");

        let snapshot = engine.snapshot().expect("snapshot should succeed");
        let visible_home = snapshot.elements.iter().any(|element| {
            element.text.as_deref() == Some("Home") || element.label.as_deref() == Some("Home")
        });
        assert!(visible_home);
    }

    #[test]
    fn screenshot_action_emits_artifact() {
        let mut engine = MockDeviceEngine::login_fixture();
        let artifacts = engine
            .perform_action(&ActionKind::TakeScreenshot {
                name: Some("demo-login".into()),
            })
            .expect("screenshot should succeed");
        assert_eq!(artifacts.len(), 1);
        assert_eq!(artifacts[0].artifact_type, "screenshot");
        assert!(artifacts[0].path.contains("demo-login-1.png"));
    }
}
