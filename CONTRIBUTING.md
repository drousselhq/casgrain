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
rustup component add rustfmt clippy llvm-tools-preview
cargo install cargo-llvm-cov
```

### 3. Build the workspace

```bash
cargo build --workspace
```

### 4. Run local checks

```bash
cargo fmt --all --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only
```

## Where to start in the codebase

- `crates/mar_domain` — start here for the canonical execution model
- `crates/mar_compiler` — spec lowering
- `crates/mar_runner` — deterministic execution
- `docs/architecture/` — architecture and governance
- `docs/prd/` — product intent and constraints

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

## Quality gates

PRs should be green on:
- rustfmt
- clippy with `-D warnings`
- tests
- coverage threshold
- cargo-audit

## Issues and backlog

We use GitHub issues to track:
- bugs
- follow-up work
- validation gaps
- security and automation improvements

If you discover a real limitation or bug during development, open or update an issue rather than letting it disappear into PR comments.

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
