# Security Automation Plan

## Goal

Define a cheap, architecture-consistent security baseline for Casgrain before real simulator/emulator adapters and credentials-adjacent workflows land.

This plan focuses on pull-request automation that is easy to maintain in a small Rust workspace while still giving contributors clear signals when they introduce risk.

For the repo-wide OWASP-aligned audit checklist and CVE-triage operating baseline, see `docs/development/security-owasp-baseline.md`.

## Current baseline

Casgrain already enforces these security checks in CI:

- `cargo audit` in `.github/workflows/security.yml`
- `gitleaks` committed-secret scanning in `.github/workflows/security.yml`

That baseline stays intentionally lightweight, but it already gives the repository deterministic dependency-vulnerability and committed-secret signals on both pull requests and pushes to `main`.

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
- the weekly `cve-watch` workflow keeps a separate managed findings issue for Rust dependency advisories so newly published RustSec CVEs do not rely only on PR-time execution

Scheduled watch expansion:
- the same `cve-watch` workflow now also queries GitHub-native Dependabot alerts for the repo's watched non-Cargo dependency surfaces (`github-actions` plus the Android smoke fixture's Gradle-managed dependencies)
- the workflow also evaluates the checked-in `.github/security-tooling-watch.json` inventory for repo-controlled security tooling installed by workflows outside Cargo.lock / Dependabot coverage
- that security-tooling slice uses GitHub `securityVulnerabilities` GraphQL data for pinned Rust CLI packages (`cargo-audit`, `cargo-deny`) and renders `manual-review-required` for `gitleaks` until the repo adopts a trustworthy machine-readable advisory source for that downloaded release-tarball path
- the workflow also evaluates the checked-in `.github/runner-host-watch.json` inventory against `host-environment.json` artifacts emitted by the Android and iOS smoke workflows, opening `security: runner-host review needed` when the inventoried runner/toolchain facts drift, when required host evidence is missing/unreadable, when the promoted `runner-images` release metadata disagrees with the observed runner-image facts, or when `android-java` release/support evaluation reports a source-backed finding
- `.github/runner-host-advisory-sources.json` is now the repo-owned contract for runner-host source-backed promotion decisions: `runner-images` and `android-java` are promoted on current `main`, while `android-gradle`, `android-emulator-runtime`, and the current combined `ios-xcode-simulator -> #144` placeholder remain `manual-review-required` follow-ups
- those expansions intentionally stay scoped to dependency-graph-backed alerts, the explicit checked-in security-tooling inventory, and the bounded runner-host release-metadata/drift lane rather than broad runner-image or generic downloaded-tool CVE scraping; the remaining runner-host source-specific promotion work now stays in #155, #156, and #144 while the shipped `runner-images` and `android-java` slices continue to reuse the existing runner-host managed-issue lane
- `java.distribution` is not part of the watched runner-host inventory on current `main`, so later Android source-backed automation must not silently widen the contract to cover it without a separate spec change

## 2. Committed secrets

**Decision:** adopt `gitleaks` now as the committed-secret baseline.

Why:
- the project will eventually handle traces, device artifacts, and credentials-adjacent automation
- repository history is the cheapest place to catch accidental secret leakage

Implementation baseline:
- `.github/workflows/security.yml` installs the pinned `gitleaks` CLI (`8.30.1`) from the upstream release tarball, verifies the published SHA-256 checksum, and runs it on pull requests and pushes to `main`
- the workflow checks out the full git history (`fetch-depth: 0`) so new leaks in commit history are visible to CI
- repo-specific policy lives in `.gitleaks.toml`, which currently extends the upstream default rules and allowlists local Rust build / coverage artifacts such as `target/` and `*.profraw`
- the repository intentionally uses the CLI directly instead of `gitleaks-action`, because the hosted action now requires a commercial license for private organization repositories and would otherwise fail before scanning

Trade-offs:
- secret scanners can produce fixture/test false positives
- allowlisting policy must be documented so contributors know how to resolve noise

Failure surfacing:
- PR check fails when `gitleaks` detects a committed secret candidate
- the same workflow runs on `main` pushes so the default branch cannot silently drift away from the PR baseline
- false positives should be handled by adding the narrowest possible repo-scoped allowlist entry in `.gitleaks.toml`
- broad global suppressions and "ignore the whole docs/tests tree" patterns should be avoided unless a follow-up issue records why they are necessary

Contributor workflow:
- run `gitleaks dir .` locally when changing fixtures, traces, samples, workflow files, or anything else that may resemble credentials
- if CI flags a deliberate fake token or fixture, first confirm it is not a real secret
- after confirming it is synthetic, add the smallest path- or rule-scoped allowlist entry needed in `.gitleaks.toml` and explain that choice in the PR
- if the suppression is non-obvious or seems reusable, record the rationale in GitHub so the allowlist does not become tribal knowledge

Tracked follow-up:
- #20 Add secret-scanning policy and CI guardrails

## 3. Supply-chain and license policy

**Decision:** adopt `cargo-deny` now for license and source-policy checks, while keeping `cargo audit` as the vulnerability baseline.

Why:
- `cargo audit` is not enough for license policy, crate-source restrictions, or advisory exceptions management
- Apache-2.0 projects should be explicit about acceptable transitive licenses before the dependency graph grows
- the current dependency graph is still small enough to make the first allowlist cheap to maintain

Current enforcement baseline:
- `cargo deny check licenses sources` runs in `.github/workflows/security.yml`
- the repo policy file lives at `deny.toml`
- the initial allowed license set is `Apache-2.0`, `MIT`, `Unicode-3.0`, and `Unlicense`
- dependency sources are restricted to the crates.io index, with unknown registries and git sources denied by default
- duplicate-version and wildcard dependency checks are configured for local visibility, but only license and source policy are CI-blocking right now

Trade-offs:
- stronger policy files take maintenance effort as the dependency graph changes
- strict license enforcement can create churn if introduced without a documented allowlist
- source restrictions may need revisiting once the project intentionally adopts git dependencies or private registries

Failure surfacing:
- as a separate PR-visible check so dependency-policy failures are obvious
- contributor docs should explain how to update `deny.toml` intentionally when dependency policy changes

Tracked follow-up:
- #22 Add supply-chain and license policy checks for Rust dependencies

## 4. Static analysis

**Decision:** defer GitHub CodeQL adoption for now, but record an explicit revisit trigger instead of leaving static-analysis scope implied.

Why:
- a live trial on pull request #26 showed that repository-level code scanning is not currently enabled, so CodeQL cannot upload results or become a green required check yet
- the same trial showed that Rust analysis does not accept the `autobuild` mode here, which means adoption needs a more deliberate workflow shape than the cheapest first-pass template
- the repository is still small and mostly scaffolding-oriented, so delaying hosted static-analysis rollout does not currently leave a large unreviewed runtime surface behind
- the existing lightweight security baseline (`cargo audit`, `gitleaks`, and `cargo deny`) still provides deterministic PR-visible coverage while CodeQL readiness is clarified

Evaluation evidence:
- GitHub Actions run `24359700556` on PR #26 failed because code scanning is disabled for the repository
- the same run reported `Rust does not support the autobuild build mode`, so any later rollout should use the supported Rust build mode instead of assuming a generic compiled-language template
- GitHub's current CodeQL documentation still lists Rust as a supported language, so this is a rollout/readiness problem rather than a language-support gap

Trade-offs:
- deferring avoids landing a permanently red workflow that contributors cannot fix from the repository alone
- Casgrain gives up early hosted static-analysis alerts until repository settings and workflow shape are ready
- the deferred decision should stay documented so CodeQL is revisited intentionally rather than forgotten

Next action to adopt later:
- enable GitHub code scanning for the repository in settings
- reintroduce a CodeQL workflow only after validating the supported Rust build mode and expected alert surfacing on a branch
- treat the first real simulator/emulator adapter or non-trivial host integration layer as the latest acceptable trigger for revisiting this decision

Issue status:
- #21 is satisfied by documenting the defer decision, the failed trial evidence, and the explicit revisit trigger

## 5. Dependency update automation

**Decision:** configure Renovate in-repo as the default low-maintenance dependency update lane, while keeping activation explicit via the GitHub app installation step.

Why:
- Casgrain already depends on versioned Rust crates, GitHub Actions, and Android fixture tooling that can drift quietly
- weekly batched update PRs are cheaper to review than ad hoc manual version bumps
- major upgrades should stay human-approved instead of landing as surprise automation churn

Implementation baseline:
- `renovate.json` is the canonical repo config for dependency updates
- enabled managers are limited to `cargo`, `github-actions`, and `gradle`, which matches the dependency surfaces currently present in-tree (including the Android smoke fixture's Gradle files)
- Renovate runs on a weekly UTC schedule with `prConcurrentLimit` / `branchConcurrentLimit` set to `3` so update churn stays within the repo's CI budget
- major updates require Dependency Dashboard approval before Renovate opens a PR
- vulnerability alert PRs are labeled `devops` and `security-review-needed` so security-sensitive upgrade work enters the existing workflow state machine honestly

Operational note:
- the config alone does not execute; a maintainer still needs to install/enable the Renovate GitHub app (or equivalent approved Renovate runner) for `drousselhq/casgrain`
- that app-install step is settings-side and should be handled explicitly rather than implied by the config merge
- until that maintainer-owned settings action happens, treat Renovate activation as external follow-up work rather than assuming the merged config is already live

Review expectations for Renovate PRs:
- treat Renovate PRs as DevOps-lane maintenance work
- keep them small and manager-scoped when possible; if a generated PR widens scope unexpectedly, close it and open a narrower follow-up issue
- do not auto-merge by policy default; required checks must still go green and higher-risk upgrades should receive human review
- when a Renovate PR changes workflow actions or security-relevant tooling, keep `security-review-needed` until a steward or maintainer explicitly clears it

## PR workflow expectations

Current required security-related behavior for contributors:
- keep `cargo audit` green
- keep `gitleaks` green
- treat security-check failures as blocking for merge
- record real validation gaps or security gaps in GitHub issues

As the next phases land, the expected PR security surface should become:
1. dependency vulnerability scan (`cargo audit`)
2. secret scanning on repo content and git history (`gitleaks`)
3. supply-chain/license policy checks
4. hosted CodeQL or equivalent static analysis once repository settings and workflow shape are validated

## Recommended implementation order

1. keep the existing `cargo audit` workflow as the baseline
2. implement secret scanning because it closes the highest-likelihood repository hygiene gap
3. add supply-chain/license policy checks once the policy file can be maintained sanely
4. revisit CodeQL after repository code-scanning support is enabled or when adapter/host-integration work makes the extra coverage materially more valuable

## Done state for issue #3

Issue #3 is satisfied once this plan is documented and the implementation work is tracked explicitly in follow-up issues:
- #20 secret scanning policy and CI guardrails
- #21 CodeQL/static-analysis evaluation
- #22 supply-chain and license policy checks
