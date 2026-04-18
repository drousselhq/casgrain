# Android smoke fixture contract

This directory holds the canonical Gherkin source and the minimal real-app substrate for the first Android smoke slice.

Current scope in this slice:
- `features/tap_counter.feature` is the canonical Android tap-counter scenario
- `app/` is the minimal Android fixture app source tree that exposes the canonical `tap-button` and `count-label` accessibility identifiers
- the compiler lowers that feature into an Android-targeted deterministic plan
- `casgrain run-android-smoke` writes the generated `plan.json` and dispatches it through an explicit Android smoke runner boundary
- the default runner script now drives an emulator-backed fixture session through `adb`: install, launch, tap, assert, dump UI hierarchy, and capture a screenshot
- if a foreign Android `Application Not Responding` dialog (for example the launcher) obscures the fixture right after launch, the runner dismisses it with `Wait` and retries the selector poll instead of timing out on the system overlay

Supported vocabulary for the canonical fixture feature:
- `Given the app is launched`
- `When the user taps tap button`
- `Then count label text is "Count: 1"`
- `When the user takes a screenshot`

Compile the canonical Android fixture feature into a deterministic plan from the repo root:

```bash
cargo run --bin casgrain -- compile tests/test-support/fixtures/android-smoke/features/tap_counter.feature
```

Dispatch the Android smoke path from the repo root:

```bash
cargo run --bin casgrain -- run-android-smoke tests/test-support/fixtures/android-smoke/features/tap_counter.feature
```

Runtime prerequisites for the default harness:
- an Android emulator is already booted and reachable via `adb`
- a debug APK for `tests/test-support/fixtures/android-smoke/app/` exists under `tests/test-support/fixtures/android-smoke/app/build/outputs/apk/debug/` (the runner prefers `app-debug.apk` when present and otherwise auto-discovers a single `*.apk` there), or `CASGRAIN_ANDROID_SMOKE_APK` points at the built APK
- optionally set `CASGRAIN_ANDROID_ADB` if `adb` is not on `PATH`
- optionally set `CASGRAIN_ANDROID_SMOKE_APP_ID` to override the default package id `hq.droussel.casgrain.smoke`
- optionally set `CASGRAIN_ANDROID_SMOKE_ACTIVITY` to override the launcher activity component or suffix (defaults to `.MainActivity` for the in-repo fixture app)
- optionally set `CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS` to control how long the runner waits for `adb wait-for-device` before failing fast
- optionally set `CASGRAIN_ANDROID_BOOT_TIMEOUT_SECS` to control how long the runner waits for the emulator to report boot-complete + package-manager readiness before install/launch
- optionally set `CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS` to control how long the runner waits for the fixture app to actually reach the foreground after launch

Artifacts required in the validated success bundle:
- `trace.json`
- `plan.json`
- `evidence-summary.json`
- `android-tap-counter-1.png`
- `emulator.json`
- `ui-before-tap.xml`
- `ui-after-tap.xml`

Artifacts required in the validated runner-managed failure bundle:
- `failure.json`
- `evidence-summary.json`
- `foreground-window.txt`
- `foreground-activity.txt`
- `ui-last.xml`

CI proof path:
- `.github/workflows/android-emulator-smoke.yml` builds the fixture APK on GitHub Actions, enables `/dev/kvm` access on the hosted Ubuntu runner so the x86_64 emulator can boot with hardware acceleration, runs `casgrain run-android-smoke`, validates the emitted artifact contract with `tests/test-support/scripts/validate_android_smoke_artifacts.py`, and uploads the resulting evidence bundle as `casgrain-android-smoke`

The machine-readable `evidence-summary.json` records whether the run produced the success contract (`trace.json` plus the stable sibling artifacts) or the runner-managed failure contract (`failure.json` plus the referenced diagnostics). If the workflow fails before the runner can emit either bundle, the workflow now treats that as an explicit contract breach instead of pretending usable smoke evidence exists.

The runner stays honest about prerequisites: if `adb` is unavailable, no emulator is ready, or the APK is missing, the command fails with a concrete message instead of pretending to execute the smoke slice.
