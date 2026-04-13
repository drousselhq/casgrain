# Execution Plan Foundation Implementation Plan

> For Hermes: continue implementing this plan task-by-task with traceable commits and GitHub issues for follow-on work.

Goal: establish the first executable Rust workspace for the mobile runtime, centered on a deterministic execution-plan IR, a minimal compiler, a fake deterministic runner, and CI/security validation scaffolding.

Architecture:
- mar_domain owns the canonical plan, selector, action, wait, assertion, trace, and engine contracts.
- mar_application owns validation and use-case boundaries.
- mar_compiler lowers OpenSpec/Gherkin-ish text into the canonical plan.
- mar_runner executes plans against a DeviceEngine deterministically.
- mar_cli exposes a machine-friendly compile surface.

Planned verification:
- cargo fmt --all --check
- cargo clippy --workspace --all-targets -- -D warnings
- cargo test --workspace
- CI coverage gate with minimum line coverage threshold

Follow-on issues expected:
- richer selector lowering
- assertions/waits expansion from OpenSpec prose
- fixture app and integration matrix
- cargo audit/CodeQL hardening
