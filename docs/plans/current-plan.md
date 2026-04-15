# Current Plan

This is the live execution plan for Casgrain.

## Operating rule
- Backlog items live in GitHub Issues.
- This file stays small and focused on the current active direction.
- Archive old plans only when the live plan becomes too complex to read quickly.

## Current project direction
- Keep the deterministic core strong and explicit.
- Prioritize the first product-true iOS vertical slice: Gherkin -> deterministic executable artifact -> real simulator execution against the fixture app.
- Keep the scope intentionally tiny: one fixture app, one scenario, one tap, one visible state change, one screenshot artifact.
- Reuse the existing iOS smoke harness only as enabling infrastructure, not as the final proof.
- Keep docs, validation, and governance aligned with the codebase.
- Maintain a cheap always-on security baseline for public PRs; prefer Linux-hosted checks for default enforcement and keep macOS simulator runs scoped to real simulator-impacting changes.
- Keep `ios-simulator-smoke` as a required PR check, but let it self-skip on PRs that do not touch iOS or shared runtime surfaces.
- Keep `android-emulator-smoke` auto-running for Android/shared-runtime changes and on a nightly schedule until it is stable enough to promote into the required merge gate.

## Near-term priorities
1. Deliver the minimal full Gherkin-to-iOS-fixture vertical slice.
2. Narrow the supported Gherkin and selector surface to only what the first slice needs.
3. Route the compiled/generated artifact through the real iOS fixture execution path in CI.
4. Extend runner and trace validation around this first product-true adapter path.
5. Keep product, architecture, and validation docs current.

## Planning discipline
- Work one bounded slice at a time.
- Update this plan when priorities change.
- Convert discovered follow-up work into GitHub Issues.
- Do not let this file become a long history log.
