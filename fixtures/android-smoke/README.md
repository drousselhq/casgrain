# Android smoke fixture contract

This directory holds the canonical Gherkin source and the minimal real-app substrate for the first Android smoke slice.

Current scope in this slice:
- `features/tap_counter.feature` is the canonical Android tap-counter scenario
- `app/` is the minimal Android fixture app source tree that exposes the canonical `tap-button` and `count-label` accessibility identifiers
- the compiler lowers that feature into an Android-targeted deterministic plan
- `mar run-android-smoke` writes the generated `plan.json` and dispatches it through an explicit Android smoke runner boundary
- the default runner script now drives an emulator-backed fixture session through `adb`: install, launch, tap, assert, dump UI hierarchy, and capture a screenshot

Supported vocabulary for the canonical fixture feature:
- `Given the app is launched`
- `When the user taps tap button`
- `Then count label text is "Count: 1"`
- `When the user takes a screenshot`

Compile the canonical Android fixture feature into a deterministic plan from the repo root:

```bash
cargo run -p mar_cli -- compile fixtures/android-smoke/features/tap_counter.feature
```

Dispatch the Android smoke path from the repo root:

```bash
cargo run -p mar_cli -- run-android-smoke fixtures/android-smoke/features/tap_counter.feature
```

Runtime prerequisites for the default harness:
- an Android emulator is already booted and reachable via `adb`
- a debug APK for `fixtures/android-smoke/app/` exists under `fixtures/android-smoke/app/build/outputs/apk/debug/` (the runner prefers `app-debug.apk` when present and otherwise auto-discovers a single `*.apk` there), or `CASGRAIN_ANDROID_SMOKE_APK` points at the built APK
- optionally set `CASGRAIN_ANDROID_ADB` if `adb` is not on `PATH`
- optionally set `CASGRAIN_ANDROID_SMOKE_APP_ID` to override the default package id `hq.droussel.casgrain.smoke`
- optionally set `CASGRAIN_ANDROID_SMOKE_ACTIVITY` to override the launcher activity component or suffix (defaults to `.MainActivity` for the in-repo fixture app)
- optionally set `CASGRAIN_ANDROID_DEVICE_TIMEOUT_SECS` to control how long the runner waits for `adb wait-for-device` before failing fast
- optionally set `CASGRAIN_ANDROID_LAUNCH_TIMEOUT_SECS` to control how long the runner waits for the fixture app to actually reach the foreground after launch

Artifacts emitted by the default harness:
- `plan.json`
- `android-tap-counter-1.png`
- `emulator.json`
- `ui-before-tap.xml`
- `ui-after-tap.xml`

Failure diagnostics emitted when the real emulator path cannot find the expected selector/state:
- `failure.json`
- `foreground-window.txt`
- `foreground-activity.txt`
- `ui-last.xml`

CI proof path:
- `.github/workflows/android-emulator-smoke.yml` builds the fixture APK on GitHub Actions, enables `/dev/kvm` access on the hosted Ubuntu runner so the x86_64 emulator can boot with hardware acceleration, runs `mar run-android-smoke`, and uploads the emitted artifacts as `casgrain-android-smoke`

The runner stays honest about prerequisites: if `adb` is unavailable, no emulator is ready, or the APK is missing, the command fails with a concrete message instead of pretending to execute the smoke slice.
