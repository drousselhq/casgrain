# CasgrainSmoke fixture app

This directory contains the smallest honest iOS simulator-backed smoke fixture for Casgrain.

What it proves:
- the macOS runner can build and launch an isolated iOS app target
- one UI interaction works end-to-end in the simulator
- one screenshot attachment is captured during the run

Current harness shape:
- one SwiftUI app
- one UI test target
- one tap that increments a visible counter
- one screenshot attachment kept in the xcresult bundle

Product-true vertical-slice source of truth:
- `features/tap_counter.feature` is the canonical scenario for the first Gherkin-to-iOS-fixture slice
- issue #49 pins the exact supported fixture vocabulary to the phrases in that file:
  - `Given the app is launched`
  - `When the user taps tap button`
  - `Then count label text is "Count: 1"`
  - `When the user takes a screenshot`
- the canonical macOS `ios-simulator-smoke` workflow now uses the generated-plan `casgrain run-ios-smoke` path as the primary proof of product behavior
- the handwritten XCTest remains harness plumbing underneath `scripts/ios_smoke.sh`, not the top-level CI proof entrypoint

Run locally on macOS with Xcode command-line tools and iOS Simulator runtimes installed:

```bash
ARTIFACT_DIR=./artifacts/ios-smoke scripts/ios_smoke.sh
```

Compile the canonical fixture feature into a deterministic plan from the repo root:

```bash
cargo run --bin casgrain -- compile fixtures/ios-smoke/features/tap_counter.feature
```

Run the fixture through the first iOS-specific CLI execution path from the repo root:

```bash
cargo run --bin casgrain -- run-ios-smoke fixtures/ios-smoke/features/tap_counter.feature
```

That command writes the compiled plan to the chosen artifact directory as `plan.json`, invokes the real simulator-backed fixture harness through `scripts/ios_smoke_run_plan.py`, and emits structured trace/artifact output for QA and CI archival.

Emit machine-readable trace JSON, including deterministic artifact references, with:

```bash
cargo run --bin casgrain -- run-ios-smoke fixtures/ios-smoke/features/tap_counter.feature --trace-json
```

The harness now fails fast when it is invoked outside macOS or when `python3`, `xcodebuild`, or `xcrun` are unavailable.

When the real simulator-backed path runs on macOS, it preserves the xcresult bundle/logs under the chosen artifact directory and also attempts to export the captured screenshot deterministically to `tap-counter-1.png` for easier inspection.

The script now prefers a small, explicit simulator selection order and supports override env vars for future Xcode/runtime changes:
- `CASGRAIN_SMOKE_RUNTIME_NAME` to pin a specific iOS runtime name or identifier
- `CASGRAIN_SMOKE_DEVICE_NAMES` to provide a semicolon-separated device preference list
- `CASGRAIN_SMOKE_DESTINATION_TIMEOUT` to extend destination matching time if Apple changes simulator startup timing

The workflow uploads the generated `plan.json`, machine-readable `trace.json`, the xcresult bundle, simulator metadata, and xcodebuild logs as artifacts. When the deterministic PNG export succeeds, `tap-counter-1.png` is included in that same artifact directory.
