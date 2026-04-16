# Execution Plan Foundation Implementation Plan

> For Hermes: continue implementing this plan task-by-task with traceable commits and GitHub issues for follow-on work.

Goal: establish the first executable Rust workspace for the mobile runtime, centered on a deterministic execution-plan IR, a minimal compiler, a fake deterministic runner, and CI/security validation scaffolding.

Architecture:
- domain owns the canonical plan, selector, action, wait, assertion, trace, and engine contracts.
- application owns validation and use-case boundaries.
- compiler lowers Gherkin feature text into the canonical plan.
- runner executes plans against a DeviceEngine deterministically.
- casgrain exposes a machine-friendly compile surface.

Planned verification:
- cargo fmt --all --check
- cargo clippy --workspace --all-targets -- -D warnings
- cargo test --workspace
- CI coverage gate with minimum line coverage threshold

Follow-on issues expected:
- richer selector lowering
- assertions/waits expansion from Gherkin prose
- fixture app and integration matrix
- cargo audit/CodeQL hardening
