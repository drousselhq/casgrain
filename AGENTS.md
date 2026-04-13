# AGENTS.md

Guidance for coding agents and contributors using agentic tools on the Casgrain codebase.

This file is intentionally written for both:
- autonomous or semi-autonomous coding agents
- humans supervising or collaborating with them

## Project summary

Casgrain is an open-source mobile automation runtime for iOS simulators and Android emulators.

Primary product goals:
- deterministic CI/CD execution
- strong local developer ergonomics
- first-class agent workflows for exploration, authoring, and repair

## Non-negotiable architectural rule

LLMs are not part of the deterministic execution path.

Allowed roles for agents and models:
- authoring
- exploration assistance
- repair proposals
- summarization
- spec drafting

Forbidden role:
- deciding runtime actions during deterministic replay

If a proposed change weakens this boundary, stop and rethink the approach.

## Current implementation shape

Important crates:
- `crates/mar_domain`
- `crates/mar_application`
- `crates/mar_compiler`
- `crates/mar_runner`
- `crates/mar_cli`

Important docs:
- `README.md`
- `CONTRIBUTING.md`
- `docs/architecture/clean-architecture.md`
- `docs/prd/product-requirements.md`
- `docs/architecture/product-naming-and-ui-governance.md`

## Local commands

Build:

```bash
cargo build --workspace
```

Validation:

```bash
cargo fmt --all --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo llvm-cov --workspace --all-features --fail-under-lines 75 --summary-only
```

Current CLI example:

```bash
cargo run -p mar_cli -- compile docs/openspec/engine-and-compilation.feature
```

## How agents should work in this repo

Prefer this order of operations:
1. inspect docs and relevant crate boundaries first
2. make the smallest architecture-consistent change
3. add or update tests
4. run validation locally
5. update docs if project behavior or direction changed
6. record real follow-up work in GitHub issues

## What to optimize for

Optimize for:
- forward progress
- cheap validation before expensive exploration
- deterministic behavior
- explicit artifacts and traceability
- small PRs

Do not optimize for:
- flashy but weakly grounded implementations
- speculative large refactors without validation
- token-heavy exploration where cheap evidence would do

## Naming and product identity

Chosen product name:
- Casgrain

The old repository placeholder name may still appear in historical docs or internal identifiers. Treat Casgrain as the actual software name unless a maintainer explicitly reopens the naming decision.

## UI governance

Current main surfaces are CLI and CI.

If future non-CLI/CI product UIs are introduced, a design system must be defined before UI implementation begins.

Agents should not introduce ad hoc UI systems or screen-by-screen design patterns without that prerequisite.

## Open-source and licensing

Project license:
- Apache License 2.0

When adding new files, preserve compatible licensing assumptions and avoid copying code from incompatible sources.

## If you are unsure

When trade-offs are unclear, prefer:
- clearer architecture
- more explicit tests
- smaller scope
- better docs
- cheaper validation first
