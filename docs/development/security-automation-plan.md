# Security Automation Plan

## Goal

Define a cheap, architecture-consistent security baseline for Casgrain before real simulator/emulator adapters and credentials-adjacent workflows land.

This plan focuses on pull-request automation that is easy to maintain in a small Rust workspace while still giving contributors clear signals when they introduce risk.

## Current baseline

Casgrain already enforces one security check in CI:

- `cargo audit` in `.github/workflows/security.yml`

That baseline is intentionally narrow, but it already gives the repository a deterministic dependency-vulnerability signal on both pull requests and pushes to `main`.

## Principles

Prefer:
- low-maintenance checks that contributors can reproduce locally
- PR-visible failures rather than security work hidden in chat or tribal knowledge
- Rust-native tooling where it materially reduces setup and false positives
- staged hardening, starting with cheap evidence before broader automation

Avoid:
- heavy security automation with unclear signal quality
- workflow sprawl before the repository has enough runtime surface area to justify it
- policies that contributors cannot understand or reproduce locally

## Threat areas to cover

### 1. Dependency vulnerabilities

**Decision:** keep `cargo audit` as the baseline required check now.

Why:
- low setup cost for a Rust workspace
- directly maps to known Rust advisory data
- already integrated locally and in CI

Trade-offs:
- catches known vulnerable crates, not unsafe code patterns
- does not enforce license policy
- may occasionally require advisory exceptions when the ecosystem lags

Failure surfacing:
- required GitHub Actions check on PRs
- contributors should run `cargo audit` locally before opening a PR when changing dependencies

## 2. Committed secrets

**Decision:** add a dedicated secret-scanning policy next.

Why:
- the project will eventually handle traces, device artifacts, and credentials-adjacent automation
- repository history is the cheapest place to catch accidental secret leakage

Tool direction:
- prefer a purpose-built committed-secret scanner rather than overloading Rust tooling
- keep the first step focused on repository contents and PR diffs, not runtime log inspection

Trade-offs:
- secret scanners can produce fixture/test false positives
- allowlisting policy must be documented so contributors know how to resolve noise

Failure surfacing:
- PR check should fail on newly introduced secrets
- suppression/allowlist process must be explicit in repo docs

Tracked follow-up:
- #20 Add secret-scanning policy and CI guardrails

## 3. Supply-chain and license policy

**Decision:** evaluate a Rust-native policy gate after the secret-scanning baseline is documented.

Why:
- `cargo audit` is not enough for license policy, crate-source restrictions, or advisory exceptions management
- Apache-2.0 projects should be explicit about acceptable transitive licenses before the dependency graph grows

Tool direction:
- evaluate `cargo-deny` first because it covers advisories, licenses, and source policy in one Rust-native workflow

Trade-offs:
- stronger policy files take maintenance effort while the dependency graph is still changing rapidly
- strict license enforcement can create churn if introduced without a documented allowlist

Failure surfacing:
- ideally as a separate PR-visible check so dependency-policy failures are obvious
- contributor docs should explain how to update policy files intentionally

Tracked follow-up:
- #22 Add supply-chain and license policy checks for Rust dependencies

## 4. Static analysis

**Decision:** document the baseline now, but treat CodeQL adoption as an explicit follow-up decision rather than silently assuming it belongs in the first wave.

Why:
- the current repository is still small and largely scaffolding-oriented
- CodeQL may become more valuable once simulator/emulator adapters and richer filesystem/process interactions land

Preferred approach:
- evaluate GitHub CodeQL against the current Rust workspace
- adopt it if the signal quality and maintenance burden are acceptable
- otherwise document a concrete trigger for revisiting it, such as the first real device adapter or non-trivial host integration layer

Trade-offs:
- stronger static analysis can catch classes of bugs `cargo audit` never will
- it also adds workflow time and review overhead, especially if alerts are noisy for a fast-moving early codebase

Failure surfacing:
- if adopted, alerts should appear in GitHub Security and via PR checks
- if deferred, the rationale should remain documented in the issue backlog rather than implied

Tracked follow-up:
- #21 Evaluate static analysis coverage with CodeQL or an equivalent baseline

## PR workflow expectations

Current required security-related behavior for contributors:
- keep `cargo audit` green
- treat security-check failures as blocking for merge
- record real validation gaps or security gaps in GitHub issues

As the next phases land, the expected PR security surface should become:
1. dependency vulnerability scan (`cargo audit`)
2. secret scanning on repo content and PR diffs
3. supply-chain/license policy checks
4. optional CodeQL or equivalent static analysis if adopted

## Recommended implementation order

1. keep the existing `cargo audit` workflow as the baseline
2. implement secret scanning because it closes the highest-likelihood repository hygiene gap
3. add supply-chain/license policy checks once the policy file can be maintained sanely
4. decide on CodeQL after measuring current codebase value versus maintenance cost

## Done state for issue #3

Issue #3 is satisfied once this plan is documented and the implementation work is tracked explicitly in follow-up issues:
- #20 secret scanning policy and CI guardrails
- #21 CodeQL/static-analysis evaluation
- #22 supply-chain and license policy checks
