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
git clone https://github.com/drousselhq/casgrain.git
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
- an explicit statement of which merge-gate checks ran and whether any documented exception applies

Before opening a PR, review:
- `.github/pull_request_template.md`
- `docs/development/automation-agent-operations.md` when the work involves autonomous maintenance or repo-operations roles
- `docs/development/bug-reproduction-evidence-contract.md` when the work involves bug intake, reproduction, or evidence collection
- `docs/development/merge-and-validation-policy.md`
- `docs/development/test-pyramid-and-runtime-contracts.md`
- `docs/validation.md`
- `docs/development/security-automation-plan.md`

## Dependency update automation

Casgrain uses Renovate as the default dependency update lane once the repository has the Renovate GitHub app (or an equivalent approved Renovate runner) enabled.

Current policy:
- the canonical config lives in `renovate.json`
- enabled managers are limited to Cargo, GitHub Actions, and the Gradle files currently present in the Android smoke fixture
- Renovate opens at most 3 concurrent update branches / PRs on a weekly UTC cadence
- major updates require Dependency Dashboard approval before a PR is created
- Renovate PRs should stay in the DevOps lane and keep the `devops` label
- workflow-action or security-sensitive upgrade PRs should keep `security-review-needed` until explicitly cleared

Because app installation is a GitHub settings step, merging the config alone does not activate Renovate. If update PRs do not appear after the config lands, check that the Renovate app is installed for `drousselhq/casgrain` before assuming the config is broken; until then, treat activation as maintainer-owned external follow-up rather than completed in-repo work.

If your change adds fixtures, traces, sample configs, or other content that can resemble credentials, run `gitleaks dir .` locally before opening the PR.
Casgrain keeps the repo policy in `.gitleaks.toml`; prefer a narrow path- or rule-scoped allowlist there instead of weakening the scanner globally.

## External contributions

Casgrain is public, but maintainers may not have bandwidth to actively review unsolicited external pull requests yet.

If you are not already a maintainer, please open an issue first before investing in a larger change. For now, prefer issue discussion over surprise PRs, and assume external PRs may be closed without review if they are off-roadmap or difficult to validate quickly.

## Quality gates

PRs should be green on:
- rustfmt
- clippy with `-D warnings`
- tests
- coverage threshold
- cargo-audit (`cargo-audit` 0.22.1 on the pinned 1.85.0 toolchain)
- gitleaks secret scanning (`gitleaks dir .` using the repo's `.gitleaks.toml` policy)
- cargo-deny license/source policy (`cargo deny check licenses sources` with `cargo-deny` 0.18.3)

Until repository settings can enforce required checks automatically, treat this list as a hard procedural merge gate: do not merge while the relevant checks are still running just because GitHub shows the merge button.

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
