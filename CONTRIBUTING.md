# Contributing to Casgrain

Thanks for contributing to Casgrain.

This document is meant to get both human contributors and agent-assisted contributors productive quickly.

## Project goals

Casgrain is building a deterministic mobile automation runtime for:
- CI/CD
- local developer workflows
- agent-native exploration, authoring, and repair

The most important architectural rule is:
- LLMs may help create or repair tests
- LLMs must not be required to execute deterministic plans

## First-time setup

### 1. Clone the repository

```bash
git clone https://github.com/drousselbot/casgrain.git
cd casgrain
```

### 2. Install Rust

Recommended:

```bash
curl https://sh.rustup.rs -sSf | sh
rustup toolchain install 1.85.0
rustup default 1.85.0
rustup component add rustfmt clippy llvm-tools-preview
cargo install cargo-llvm-cov --version 0.6.15 --locked
cargo install cargo-audit --version 0.22.1 --locked
cargo install cargo-deny --version 0.18.3 --locked
```

Casgrain pins its validation toolchain in `rust-toolchain.toml` and currently requires Rust 1.85.0 / MSRV 1.85.
Use a `rustup`-managed toolchain for local development; distro `cargo`/`rustc` packages do not automatically honor `rust-toolchain.toml` and can drift from CI.

### 3. Build the workspace

```bash
cargo build --workspace
```

### 4. Run local checks

See `docs/validation.md` for the canonical validation gate.

## Where to start in the codebase

- `crates/mar_domain` — start here for the canonical execution model
- `crates/mar_compiler` — spec lowering
- `crates/mar_runner` — deterministic execution
- `docs/architecture/` — architecture and governance
- `docs/prd/` — product intent and constraints
- `docs/specs/` — canonical product behavior specs

## Contribution expectations

Please prefer:
- small, reviewable pull requests
- tests with behavior changes
- architecture-aligned changes over quick hacks
- explicit docs updates when changing project direction

Please avoid:
- introducing LLM dependence into the runtime execution path
- weakening determinism for convenience
- UI work without a design system if the work goes beyond CLI/CI

## Pull request guidance

A good PR should include:
- a clear problem statement
- the smallest practical implementation that solves it
- tests or validation updates where relevant
- notes about follow-up work if the implementation is intentionally incomplete

Before opening a PR, review:
- `.github/pull_request_template.md`
- `docs/development/merge-and-validation-policy.md`
- `docs/development/test-pyramid-and-runtime-contracts.md`
- `docs/validation.md`
- `docs/development/security-automation-plan.md`

If your change adds fixtures, traces, sample configs, or other content that can resemble credentials, run `gitleaks dir .` locally before opening the PR.
Casgrain keeps the repo policy in `.gitleaks.toml`; prefer a narrow path- or rule-scoped allowlist there instead of weakening the scanner globally.

## Quality gates

PRs should be green on:
- rustfmt
- clippy with `-D warnings`
- tests
- coverage threshold
- cargo-audit (`cargo-audit` 0.22.1 on the pinned 1.85.0 toolchain)
- gitleaks secret scanning (`gitleaks dir .` using the repo's `.gitleaks.toml` policy)
- cargo-deny license/source policy (`cargo deny check licenses sources` with `cargo-deny` 0.18.3)

## Issues and backlog

We use GitHub issues to track:
- bugs
- follow-up work
- validation gaps
- security and automation improvements

If you discover a real limitation or bug during development, open or update an issue rather than letting it disappear into PR comments.

When filing a bug, use the GitHub bug report form and include:
- the smallest reproducible sequence
- whether the failure is deterministic or flaky
- the affected platform or execution target
- the Casgrain version, branch, or commit SHA
- traces, logs, artifacts, and failing commands
- OS, Rust version, simulator/emulator details, and other relevant environment data

## Contributors using coding agents

If you are using tools such as:
- Claude Code
- Codex CLI
- GitHub Copilot
- Hermes
- other coding agents

read `AGENTS.md` before making substantial changes.

## License

By contributing, you agree that your contributions will be licensed under Apache License 2.0.
