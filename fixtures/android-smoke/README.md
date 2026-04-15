# Android smoke fixture contract

This directory holds the canonical Gherkin source for the first Android product-true smoke slice.

Current scope in this slice:
- `features/tap_counter.feature` is the canonical Android tap-counter scenario
- the compiler lowers that feature into an Android-targeted deterministic plan
- `mar run-android-smoke` writes the generated `plan.json` and dispatches it through an explicit Android smoke runner boundary
- the default runner script currently validates the plan contract and fails fast until a real emulator-backed harness lands

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

At the moment, that command is intentionally honest: without an injected `CASGRAIN_ANDROID_SMOKE_RUNNER`, it validates the generated plan and exits with a message that the real emulator-backed harness is still pending.
