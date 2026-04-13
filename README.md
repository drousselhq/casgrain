# Casgrain

Casgrain is an open-source mobile automation runtime for iOS simulators and Android emulators.

It is being built for three first-class use cases from day one:
- CI/CD pipelines that need deterministic, replayable mobile tests
- local developers who want a fast CLI for exploration and debugging
- coding agents that need structured interfaces for exploration, authoring, and repair

The project is named in honour of Thérèse Casgrain.

## Why Casgrain exists

Existing mobile automation tools often force a trade-off:
- good for CI, but painful for local developers
- good for manual authoring, but weak for autonomous agents
- easy to start, but hard to trust when tests become important

Casgrain aims to be different:
- deterministic execution for CI trust
- agent-native interfaces without putting an LLM in the execution path
- clean architecture from the start
- artifact-rich traces for debugging and repair

## What Casgrain does

Casgrain is intended to compile high-level specifications into explicit executable plans, then run those plans against mobile targets through platform adapters.

Conceptually:
1. author or generate a spec
2. compile it into a deterministic execution plan
3. run the plan on a simulator or emulator
4. collect traces, artifacts, and structured results
5. use those results for debugging, repair, or regression testing

## Current project status

Casgrain is early, but no longer docs-only.

Implemented foundation already in the repo:
- Rust workspace with domain, compiler, runner, application, and CLI crates
- canonical `ExecutablePlan` IR
- selector, action, assertion, wait, artifact, and trace domain models
- minimal OpenSpec-to-plan compiler scaffold
- fake deterministic runner with unit tests
- CI validation, security scanning, and coverage gating

Not implemented yet:
- real iOS simulator adapter
- real Android emulator adapter
- fixture-app-backed end-to-end integration tests
- stable public CLI/API surface

So today, Casgrain is best understood as an actively built foundation rather than a production-ready mobile runner.

## Architecture at a glance

Core direction:
- Rust for deterministic core logic
- Swift for iOS-native adapter work where needed
- Kotlin/Java for Android-native adapter work where needed

Layering:
- `mar_domain` — canonical execution-plan and runtime contracts
- `mar_application` — use-case boundaries and validation
- `mar_compiler` — spec lowering into executable plans
- `mar_runner` — deterministic execution against a `DeviceEngine`
- `mar_cli` — CLI entrypoints

Important constraint:
- LLMs may assist with authoring, exploration, or repair
- LLMs are not part of the deterministic execution path

## Quick start

### Prerequisites

Current development prerequisites:
- Rust stable toolchain
- Git
- GitHub account if you want to contribute through pull requests

Recommended Rust setup:

```bash
curl https://sh.rustup.rs -sSf | sh
rustup component add rustfmt clippy llvm-tools-preview
cargo install cargo-llvm-cov
```

## Build

```bash
git clone https://github.com/drousselbot/casgrain.git
cd casgrain
cargo build --workspace
```

## Run the current CLI scaffold

Compile an OpenSpec-style feature file into the current JSON plan format:

```bash
cargo run -p mar_cli -- compile docs/openspec/engine-and-compilation.feature
```

## Example output flow

Given an input like:

```gherkin
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login button
    When the user enters "daniel@example.com" into email field
    Then the home screen is visible
```

The current compiler scaffold lowers that into a structured JSON plan with explicit steps, actions, waits, and assertions.

## Development workflow

Run the local validation suite before opening or merging a PR:

```bash
cargo fmt --all --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only
```

## CI quality gates

Current CI checks are designed to stay cheap enough for fast iteration while still catching obvious regressions.

Every PR should be green on:
- formatting (`rustfmt`)
- linting (`clippy -D warnings`)
- workspace tests
- line coverage threshold
- `cargo audit`

## Install strategy

Casgrain is not yet packaged as a stable released binary.

For now, installation means cloning the repository and building from source:

```bash
git clone https://github.com/drousselbot/casgrain.git
cd casgrain
cargo build --release
```

Future install targets may include:
- `cargo install`
- Homebrew
- prebuilt binaries
- CI-friendly container images

## Repository guide

Important files and directories:
- `README.md` — project overview and quick start
- `CONTRIBUTING.md` — how to get set up and contribute
- `AGENTS.md` — guidance for coding agents and contributors using agentic tools
- `CODEOWNERS` — default review ownership
- `.github/pull_request_template.md` — PR checklist and merge notes
- `.github/ISSUE_TEMPLATE/` — bug and feature intake
- `docs/architecture/` — architecture and governance documents
- `docs/development/merge-and-validation-policy.md` — merge classes and validation expectations
- `docs/prd/` — product requirements
- `docs/openspec/` — specification examples
- `crates/` — Rust implementation
- `.github/workflows/` — CI and security automation

## Future UI rule

Current primary surfaces are CLI and CI.

If Casgrain later grows non-CLI/CI product UIs, a design system must be defined before UI implementation begins.

## Contributing

Contributions are welcome.

Start here:
- `CONTRIBUTING.md`
- `AGENTS.md`

If you are contributing through Claude Code, Codex CLI, Copilot, or similar tools, read `AGENTS.md` first.

## License

Casgrain is open source under the Apache License 2.0.

See:
- `LICENSE`
- `NOTICE`
