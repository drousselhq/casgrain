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

Run locally on macOS with:

```bash
ARTIFACT_DIR=./artifacts/ios-smoke scripts/ios_smoke.sh
```

The workflow uploads the xcresult bundle and logs as artifacts.
