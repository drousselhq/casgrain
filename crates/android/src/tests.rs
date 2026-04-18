use std::{fs, path::PathBuf};

use domain::{FailureCode, TargetPlatform};

use crate::{
    plan_validation::validate_supported_smoke_plan,
    run_smoke_fixture_plan,
    test_support::{
        env_lock, install_fake_adb, install_fake_android_smoke_runner,
        install_foreign_anr_overlay_adb, install_misleading_foreground_adb,
        install_never_foregrounds_adb, install_slow_wait_adb, supported_smoke_plan, temp_path,
    },
};

#[test]
fn run_smoke_fixture_plan_writes_plan_and_reads_trace() {
    let repo_root = temp_path("casgrain-android-repo");
    let artifact_dir = temp_path("casgrain-android-artifacts");
    let runner = install_fake_android_smoke_runner(&repo_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_RUNNER", &runner);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
    }

    let trace = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect("android smoke plan should execute through injected runner");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
    }

    assert_eq!(trace.run_id, "android-smoke-increment-the-counter-once");
    assert_eq!(trace.device.platform, TargetPlatform::Android);
    assert_eq!(trace.artifacts[0].artifact_type, "screenshot");
    assert!(artifact_dir.join("plan.json").is_file());
}

#[test]
fn smoke_plan_validation_rejects_non_android_target() {
    let mut plan = supported_smoke_plan();
    plan.target.platform = TargetPlatform::Ios;
    let error = validate_supported_smoke_plan(&plan).expect_err("non-android plan should fail");
    assert_eq!(error.code, FailureCode::UnsupportedAction);
    assert!(error.message.contains("Android-targeted"));
}

#[test]
fn smoke_plan_validation_rejects_non_emulator_target() {
    let mut plan = supported_smoke_plan();
    plan.target.device_class = "simulator".into();
    let error = validate_supported_smoke_plan(&plan).expect_err("non-emulator plan should fail");
    assert_eq!(error.code, FailureCode::UnsupportedAction);
    assert!(error.message.contains("emulator-targeted"));
}

#[test]
fn default_script_executes_fixture_plan_via_fake_adb() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-default-script-artifacts");
    let apk_path = temp_path("casgrain-android-fixture-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-fake-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_fake_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    let trace = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect("default script should execute through fake adb harness");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    assert_eq!(trace.run_id, "android-smoke-increment-the-counter-once");
    assert_eq!(trace.device.platform, TargetPlatform::Android);
    assert_eq!(trace.device.name, "Pixel 8");
    assert_eq!(trace.device.os_version, "15");
    assert!(artifact_dir.join("plan.json").is_file());
    assert!(artifact_dir.join("android-tap-counter-1.png").is_file());
    assert!(artifact_dir.join("emulator.json").is_file());
    assert!(artifact_dir.join("ui-before-tap.xml").is_file());
    assert!(artifact_dir.join("ui-after-tap.xml").is_file());
    assert_eq!(trace.artifacts[0].artifact_type, "screenshot");
}

#[test]
fn default_script_is_repeatable_against_the_same_fake_adb_state() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir_one = temp_path("casgrain-android-repeat-artifacts-one");
    let artifact_dir_two = temp_path("casgrain-android-repeat-artifacts-two");
    let apk_path = temp_path("casgrain-android-repeat-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-repeat-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_fake_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir_one);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    run_smoke_fixture_plan(&supported_smoke_plan()).expect("first fake adb run should succeed");

    unsafe {
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir_two);
    }

    let second_trace = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect("second fake adb run should also succeed after state reset");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    assert_eq!(second_trace.status, domain::RunStatus::Passed);
    assert!(artifact_dir_one.join("android-tap-counter-1.png").is_file());
    assert!(artifact_dir_two.join("android-tap-counter-1.png").is_file());
}

#[test]
fn default_script_fails_fast_when_device_never_becomes_ready() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-timeout-artifacts");
    let apk_path = temp_path("casgrain-android-timeout-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-timeout-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_slow_wait_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::set_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS", "0.1");
        std::env::set_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS", "0.1");
    }

    let error = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect_err("default script should fail fast when no device becomes ready");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        std::env::remove_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS");
    }

    assert_eq!(error.code, FailureCode::EngineError);
    assert!(error.message.contains("wait-for-device timed out"));
}

#[test]
fn default_script_fails_when_fixture_app_never_reaches_foreground() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-foreground-timeout-artifacts");
    let apk_path = temp_path("casgrain-android-foreground-timeout-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-foreground-timeout-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_never_foregrounds_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::set_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS", "0.1");
        std::env::set_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS", "0.1");
    }

    let error = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect_err("default script should fail when the fixture app never becomes foreground");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        std::env::remove_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS");
    }

    assert_eq!(error.code, FailureCode::EngineError);
    assert!(error.message.contains("did not reach the foreground"));
    assert!(error.message.contains("mCurrentFocus"));
    assert!(
        error
            .message
            .contains("com.google.android.apps.nexuslauncher")
    );
}

#[test]
fn default_script_rejects_misleading_activity_history_when_launcher_keeps_focus() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-misleading-foreground-artifacts");
    let apk_path = temp_path("casgrain-android-misleading-foreground-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-misleading-foreground-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_misleading_foreground_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::set_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS", "0.1");
        std::env::set_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS", "0.1");
    }

    let error = run_smoke_fixture_plan(&supported_smoke_plan()).expect_err(
        "default script should not treat stale activity history as proof that the app is foreground",
    );

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        std::env::remove_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS");
    }

    assert_eq!(error.code, FailureCode::EngineError);
    assert!(error.message.contains("did not reach the foreground"));
    assert!(
        error
            .message
            .contains("com.google.android.apps.nexuslauncher/.NexusLauncherActivity")
    );
    assert!(
        error
            .message
            .contains("hq.droussel.casgrain.smoke/.MainActivity")
    );
}

#[test]
fn default_script_dismisses_foreign_anr_overlay_and_completes_smoke_run() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-foreign-anr-artifacts");
    let apk_path = temp_path("casgrain-android-foreign-anr-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-foreign-anr-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_foreign_anr_overlay_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        std::env::remove_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS");
    }

    let trace = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect("default script should dismiss a foreign ANR overlay and continue");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
        std::env::remove_var("CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS");
    }

    assert_eq!(trace.status, domain::RunStatus::Passed);
    assert!(artifact_dir.join("ui-before-tap.xml").is_file());
    assert!(artifact_dir.join("ui-after-tap.xml").is_file());
}

#[test]
fn default_script_honors_explicit_activity_component_override() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|path| path.parent())
        .expect("workspace root should exist")
        .to_path_buf();
    let artifact_dir = temp_path("casgrain-android-explicit-activity-artifacts");
    let apk_path = temp_path("casgrain-android-explicit-activity-apk").with_extension("apk");
    let fake_adb_root = temp_path("casgrain-android-explicit-activity-adb");
    fs::create_dir_all(&fake_adb_root).expect("fake adb root should exist");
    fs::write(&apk_path, b"fake-apk").expect("fake apk should be written");
    let adb = install_fake_adb(&fake_adb_root);
    let _guard = env_lock().lock().expect("env lock should not be poisoned");

    unsafe {
        std::env::set_var("CASGRAIN_REPO_ROOT", &repo_root);
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_RUNNER");
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR", &artifact_dir);
        std::env::set_var("CASGRAIN_ANDROID_SMOKE_APK", &apk_path);
        std::env::set_var("CASGRAIN_ANDROID_ADB", &adb);
        std::env::set_var(
            "CASGRAIN_ANDROID_SMOKE_ACTIVITY",
            "hq.droussel.casgrain.smoke/.MainActivity",
        );
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    let trace = run_smoke_fixture_plan(&supported_smoke_plan())
        .expect("default script should accept an explicit launch component override");

    unsafe {
        std::env::remove_var("CASGRAIN_REPO_ROOT");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ARTIFACT_DIR");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_APK");
        std::env::remove_var("CASGRAIN_ANDROID_ADB");
        std::env::remove_var("CASGRAIN_ANDROID_SMOKE_ACTIVITY");
        std::env::remove_var("CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS");
    }

    assert_eq!(trace.status, domain::RunStatus::Passed);
}
