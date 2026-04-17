<h1 align="center">Casgrain</h1>

<p align="center">
  <strong>An open-source mobile automation runtime for deterministic execution, structured traces, and agent-assisted repair.</strong><br/>
  Compile Gherkin into explicit execution plans, run them locally or in CI, and keep LLMs out of the runtime path.
</p>

<p align="center">
  <a href="https://github.com/drousselhq/casgrain/stargazers">
    <img src="https://img.shields.io/github/stars/drousselhq/casgrain?style=flat" alt="GitHub stars" />
  </a>
  <a href="https://github.com/drousselhq/casgrain/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/drousselhq/casgrain?style=flat" alt="License" />
  </a>
  <a href="https://github.com/drousselhq/casgrain/actions/workflows/rust-ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/drousselhq/casgrain/rust-ci.yml?branch=main&label=rust-ci" alt="Rust CI workflow" />
  </a>
  <a href="https://github.com/drousselhq/casgrain/actions/workflows/security.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/drousselhq/casgrain/security.yml?branch=main&label=security" alt="Security workflow" />
  </a>
</p>

<p align="center">
  <a href="#why-casgrain">Why</a> •
  <a href="#how-casgrain-differs">How it differs</a> •
  <a href="#what-casgrain-does-today">What it does today</a> •
  <a href="#quick-start">Quick start</a> •
  <a href="#architecture-at-a-glance">Architecture</a> •
  <a href="#contributing">Contributing</a>
</p>

Casgrain is an open-source mobile automation runtime for iOS simulators and Android emulators.

It is being built for three first-class use cases from day one:
- CI/CD pipelines that need deterministic, replayable mobile tests
- local developers who want a fast CLI for exploration and debugging
- coding agents that need structured interfaces for exploration, authoring, and repair

The project is named in honour of Thérèse Casgrain.

> [!IMPORTANT]
> Casgrain is early, but it is no longer docs-only.
> The repo already contains a Rust workspace, a canonical `ExecutablePlan` IR, a Gherkin-to-plan compiler scaffold, a deterministic mock runner, and an iOS smoke CLI slice that emits structured trace/artifact output.
> It is best understood today as an actively built foundation, not yet as a production-ready replacement for Appium or Maestro.

## Table of Contents

- [Why Casgrain](#why-casgrain)
- [How Casgrain differs](#how-casgrain-differs)
- [What Casgrain does today](#what-casgrain-does-today)
- [Quick start](#quick-start)
- [Current project status](#current-project-status)
- [Architecture at a glance](#architecture-at-a-glance)
- [Repository guide](#repository-guide)
- [Future UI rule](#future-ui-rule)
- [Contributing](#contributing)
- [License](#license)

## Why Casgrain

Casgrain turns mobile automation into something teams can actually trust:
- deterministic execution for local runs and CI
- explicit execution plans instead of hidden runtime decisions
- structured traces and artifacts for debugging and repair
- agent-friendly workflows without putting an LLM in the runtime path

## How Casgrain differs

Casgrain is built around a simple idea: author or derive a scenario, compile it into an explicit plan, run it deterministically, and keep the evidence.

That means readable inputs, predictable execution, and machine-consumable outputs — all in the same system.

## What Casgrain does today

Today, the repository already demonstrates the core shape of that approach:

- a Rust workspace with domain, compiler, runner, application, and CLI crates
- a canonical `ExecutablePlan` IR
- selector, action, assertion, wait, artifact, and trace domain models
- a minimal Gherkin-to-test-plan compiler scaffold
- a deterministic mock runner
- a real iOS smoke CLI path that writes `plan.json` and emits structured trace/artifact output
- a first Android smoke CLI contract path that lowers the canonical Android fixture feature into an Android-targeted plan and dispatches it through an explicit runner boundary
- CI validation, security scanning, and coverage gating

Conceptually, Casgrain works like this:
1. author or generate a scenario
2. compile it into a deterministic execution plan
3. run the plan on a simulator or emulator
4. collect traces, artifacts, and structured results
5. use those results for debugging, repair, or regression testing

## Quick start

### Prerequisites

Current development prerequisites:
- Rust stable toolchain
- Git
- GitHub account if you want to contribute through pull requests

Recommended Rust setup:

```bash
curl https://sh.rustup.rs -sSf | sh
rustup toolchain install 1.85.0
rustup default 1.85.0
rustup component add rustfmt clippy llvm-tools-preview
cargo install cargo-llvm-cov --version 0.6.15 --locked
cargo install cargo-audit --version 0.22.1 --locked
cargo install cargo-deny --version 0.18.3 --locked
```

### Build

```bash
git clone https://github.com/drousselhq/casgrain.git
cd casgrain
cargo build --workspace
```

### Try the CLI

The user-facing command is `casgrain`.

From the repo root, use it like this while developing:

```bash
cargo run --bin casgrain -- --help
```

If you want a built binary first:

```bash
cargo build --bin casgrain
./target/debug/casgrain --help
```

#### Fastest way to see something work on any machine

This path does not need a simulator or emulator. It compiles and runs the built-in mock example:

```bash
cargo run --bin casgrain -- compile docs/specs/casgrain-product-spec.md
cargo run --bin casgrain -- run-mock docs/specs/casgrain-product-spec.md
```

If you want JSON instead of the human summary:

```bash
cargo run --bin casgrain -- run-mock docs/specs/casgrain-product-spec.md --trace-json
```

#### Run the built-in iOS fixture app

Use the included tap-counter fixture if you are on macOS with Xcode command-line tools and iOS Simulator runtimes installed:

```bash
cargo run --bin casgrain -- compile tests/test-support/fixtures/ios-smoke/features/tap_counter.feature
cargo run --bin casgrain -- run-ios-smoke tests/test-support/fixtures/ios-smoke/features/tap_counter.feature
```

JSON trace output:

```bash
cargo run --bin casgrain -- run-ios-smoke tests/test-support/fixtures/ios-smoke/features/tap_counter.feature --trace-json
```

#### Run the built-in Android fixture app

Use the included Android tap-counter fixture when you have an emulator available through `adb`.

Build the fixture APK:

```bash
gradle -p tests/test-support/fixtures/android-smoke/app assembleDebug
```

Then compile and run the fixture scenario:

```bash
cargo run --bin casgrain -- compile tests/test-support/fixtures/android-smoke/features/tap_counter.feature
cargo run --bin casgrain -- run-android-smoke tests/test-support/fixtures/android-smoke/features/tap_counter.feature
```

The default Android smoke path drives a real `adb`/emulator-backed fixture session when its prerequisites are available. In CI, `.github/workflows/android-emulator-smoke.yml` builds the fixture APK, boots an Android emulator, runs the generated-plan smoke flow, validates the artifact contract, and uploads a bundle that includes `trace.json`/`plan.json` on success or a runner-managed `failure.json` plus the referenced diagnostics when the smoke runner reaches a structured failure path, along with a machine-readable `evidence-summary.json` for debugging. If neither bundle exists, the workflow now fails explicitly instead of silently uploading partial evidence.

#### Try your own scenario

Today, the easiest way to start with your own input is to write a small `.feature` file and compile it:

```gherkin
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login button
    When the user enters "daniel@example.com" into email field
    Then the home screen is visible
```

Save that as `my.feature`, then run:

```bash
cargo run --bin casgrain -- compile my.feature
```

Honest status: the built-in fixture apps are the easiest end-to-end way to play with Casgrain today. General bring-your-own-app execution is still early beyond those fixture-backed smoke paths.

### Example authoring shape

Given an input like:

```gherkin
Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user taps login button
    When the user enters "daniel@example.com" into email field
    Then the home screen is visible
```

Casgrain's intended shape is:
- keep the feature readable at the authoring layer
- lower it into an explicit plan with stable step IDs, actions, waits, and assertions
- run that plan deterministically
- preserve structured evidence from the run

## Current project status

Implemented foundation already in the repo:
- Rust workspace with domain, compiler, runner, application, and CLI crates
- canonical `ExecutablePlan` IR
- selector, action, assertion, wait, artifact, and trace domain models
- minimal Gherkin-to-test-plan compiler scaffold
- fake deterministic runner with unit tests
- CI validation, security scanning, and coverage gating
- first fixture-specific iOS smoke path through `casgrain run-ios-smoke`

Not implemented yet:
- real general-purpose iOS simulator adapter
- real general-purpose Android emulator adapter beyond the fixture-specific smoke path
- fixture-app-backed end-to-end breadth beyond the current smoke slice
- stable public CLI/API surface

So today, Casgrain is best understood as an actively built foundation rather than a production-ready mobile runner.

## Architecture at a glance

Core direction:
- Rust for deterministic core logic
- Swift for iOS-native adapter work where needed
- Kotlin/Java for Android-native adapter work where needed

Layering:
- `domain` — canonical execution-plan and runtime contracts
- `application` — use-case boundaries and validation
- `compiler` — spec lowering into executable plans
- `runner` — deterministic execution against a `DeviceEngine`
- `casgrain` — internal Rust crate that powers the `casgrain` CLI binary

Important constraint:
- LLMs may assist with authoring, exploration, or repair
- LLMs are not part of the deterministic execution path

## Repository guide

Important files and directories:
- `README.md` — project overview and quick start
- `CONTRIBUTING.md` — how to get set up and contribute
- `AGENTS.md` — guidance for coding agents and contributors using agentic tools
- `CODEOWNERS` — default review ownership
- `.github/pull_request_template.md` — PR checklist and merge notes
- `.github/ISSUE_TEMPLATE/` — bug and feature intake
- `docs/architecture/` — architecture and governance documents
- `docs/development/automation-agent-operations.md` — repository maintenance agent roles and boundaries
- `docs/development/merge-and-validation-policy.md` — merge classes and validation expectations
- `docs/development/rust-coding-guide.md` — practical Rust defaults and repo-specific coding expectations
- `docs/development/test-pyramid-and-runtime-contracts.md` — test layers and runtime contract strategy
- `docs/validation.md` — canonical validation gate and reporting expectations
- `docs/development/security-automation-plan.md` — security scanning baseline and follow-up roadmap
- `deny.toml` — cargo-deny license and dependency-source policy
- `docs/prd/` — product requirements
- `docs/branding/` — naming exploration and product naming context
- `docs/plans/current-plan.md` — live execution plan
- `docs/specs/casgrain-product-spec.md` — canonical product behavior spec
- `tests/test-support/fixtures/ios-smoke/` — smallest honest iOS simulator-backed smoke slice
- `crates/` — Rust implementation
- `.github/workflows/` — CI and security automation

## Future UI rule

Current primary surfaces are CLI and CI.

If Casgrain later grows non-CLI/CI product UIs, a design system must be defined before UI implementation begins.

## Contributing

Contributions are welcome.

Start here:
- `CONTRIBUTING.md`
- `docs/development/rust-coding-guide.md`
- `AGENTS.md`

If you are contributing through Claude Code, Codex CLI, Copilot, or similar tools, read `AGENTS.md` first.

## License

Casgrain is open source under the Apache License 2.0.

See:
- `LICENSE`
- `NOTICE`
