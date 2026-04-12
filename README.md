# Mobile Agent Runtime

Agent-native mobile runtime for iOS simulators and Android emulators, designed for three first-class use cases from day one:

1. CI/CD execution of deterministic mobile tests
2. Local developer workflows on laptops/desktops
3. LLM-agent workflows for exploration, authoring, repair, and autonomous execution

## Vision

Build a cleanly architected platform where:
- deterministic execution is trustworthy enough for CI
- specs remain documented and reviewable at all times
- agents can explore, author, and repair tests without becoming part of the deterministic execution path

## Principles

- Deterministic engine first
- Specs before implementation
- Clean architecture and strict separation of concerns
- JSON/structured interfaces for machine consumers
- Human-readable documentation and traceability for team adoption
- Cross-platform where honest, platform-specific where necessary
- Favor performant, safe implementation languages for the core runtime

## Working implementation direction

Current architectural direction:
- Rust for the core engine, compiler, execution, trace, and artifact layers
- Swift for iOS-specific adapter/glue where native integration is beneficial
- Kotlin/Java for Android-specific adapter/glue where native integration is beneficial

This is intended to maximize:
- safety
- maintainability
- testability
- local CLI performance
- long-term suitability for mobile-focused engineering teams

## Repository structure

- `docs/architecture/` — architecture and bounded-context documents
- `docs/prd/` — product requirements and scope
- `docs/openspec/` — executable intent/specification source files
- `docs/plans/` — implementation plans and execution notes
- `tasks/` — backlog and planning artifacts
- `crates/mar_domain` — canonical executable plan, selector, trace, and runtime contracts
- `crates/mar_application` — plan validation and application-layer contracts
- `crates/mar_compiler` — OpenSpec-to-plan compilation entrypoint
- `crates/mar_runner` — deterministic runner against abstract `DeviceEngine`
- `crates/mar_cli` — machine-friendly CLI scaffold
- `.github/workflows/` — CI and security validation workflows

## Initial scope

The first phase focuses on:
- domain architecture
- execution-plan model
- selector strategy
- agent-facing workflows
- CI/local/agent interface design
- OpenSpec-driven documentation

## Current implemented foundation

The repo now contains an initial Rust workspace with:
- a JSON-serializable `ExecutablePlan` IR
- selector, action, assertion, wait, artifact, and trace domain types
- a plan validation layer
- a minimal deterministic OpenSpec compiler scaffold
- a fake deterministic runner with unit tests
- CI and security workflow scaffolding

## Local verification

```bash
cargo fmt --all --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```
