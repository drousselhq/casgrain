# OWASP-aligned Security Baseline

## Goal

Define a practical, repository-specific security baseline for Casgrain that is grounded in OWASP-style risk areas without turning the project into compliance theater.

This baseline focuses on the parts of Casgrain that already exist today:
- public GitHub repository governance
- pull-request and branch-protection controls
- GitHub Actions workflow safety
- dependency and secret-scanning automation
- lightweight CVE triage for the current toolchain and automation surface

It does **not** claim that every desired control is fully enforced in-repo today. When a meaningful gap remains, this document points to the tracked GitHub issue or settings-side limitation instead of pretending the control already exists.

## Evidence snapshot

Current repository evidence checked for this baseline:
- the active `main-protection-ruleset` requires `validate`, `coverage`, `gitleaks`, `cargo-audit`, `cargo-deny-policy`, `analyze (actions)`, `analyze (rust)`, `ios-smoke`, and `android-smoke`
- both mobile smoke workflows always report a PR status while self-skipping unaffected diffs, so the live required mobile contexts stay enforceable without paying full simulator/emulator cost on unrelated changes
- `main` is governed by an active ruleset that enforces strict required status checks, linear history, and resolved review conversations
- force pushes and branch deletions are disabled on `main`
- repository default workflow token permissions are `read`
- `.github/workflows/security.yml` uses job-scoped least-privilege permissions and disables checkout credential persistence
- repository security settings currently report `secret_scanning`, `secret_scanning_push_protection`, and `dependabot_security_updates` as enabled
- repository security settings currently report `secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks` as disabled
- required PR-visible security checks today are `gitleaks`, `cargo-audit`, `cargo-deny-policy`, advisory CodeQL analysis, and the live mobile smoke gates (`ios-smoke` and `android-smoke`)

## Baseline areas

### 1. Secure change control and merge discipline

Relevant OWASP themes:
- security misconfiguration
- software and data integrity failures

Required baseline:
- all changes land through pull requests rather than direct pushes to `main`
- required status checks stay explicit and green before merge
- mergeability must include conversation resolution, not only green CI bubbles
- branch protection should prevent force-push rewrites and casual branch deletion on `main`

Current repo status:
- **meets baseline** for protected-branch merge discipline
- enforced by the active `main-protection-ruleset` plus the repo's merge/validation policy docs

Evidence:
- the active `main-protection-ruleset` targets `refs/heads/main` and keeps `strict_required_status_checks_policy: true`
- the ruleset's `pull_request` rule requires review-thread resolution
- the ruleset also enables `required_linear_history`, `non_fast_forward`, and `deletion` protections

### 2. Workflow least privilege and runner hygiene

Relevant OWASP themes:
- security misconfiguration
- software and data integrity failures

Required baseline:
- default workflow token permissions should stay read-only unless a workflow needs more
- workflows should scope permissions per job when possible
- checkout steps should avoid persisting write credentials by default
- externally maintained GitHub Actions should be pinned to immutable SHAs or tracked as a deliberate gap
- downloaded security tooling should use explicit versions and integrity verification where practical

Current repo status:
- **meets baseline**

Evidence:
- repository default workflow permissions are `read`
- `security.yml` declares explicit top-level permissions and uses `persist-credentials: false`
- the `gitleaks` install path verifies the release tarball SHA-256 before execution
- checked-in workflows pin external actions to immutable SHAs with version comments, including `actions/checkout` (`# v6`), `actions/setup-java` (`# v5`), `Swatinem/rust-cache` (`# v2`), and `actions/upload-artifact` (`# v7`)

Note:
- the earlier workflow SHA-pinning follow-up is already complete; issue `#82` is closed and remains historical context only

### 3. Secret and sensitive-data exposure controls

Relevant OWASP themes:
- cryptographic failures / secret handling failures
- security logging and monitoring failures

Required baseline:
- committed-secret scanning must run on pull requests and default-branch pushes
- repository-side secret scanning and push protection should stay enabled for public contribution safety
- false positives should be resolved with narrow allowlists rather than broad global suppression
- artifact, fixture, and trace handling should preserve contributor safety when secret-like content appears in test data

Current repo status:
- **meets baseline** for the current repository surface

Evidence:
- GitHub reports `secret_scanning` and `secret_scanning_push_protection` as enabled
- `.github/workflows/security.yml` runs `gitleaks git . --config .gitleaks.toml --no-banner`
- `docs/development/security-automation-plan.md` and `CONTRIBUTING.md` already document the repo-scoped allowlist policy

Note:
- `secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks` are currently disabled in repository settings. They are visible in the audit evidence, but they are not yet treated as a blocking baseline gap because the current repo-specific committed-secret controls are already in place and the first missing high-value follow-up is better spent on workflow SHA pinning and CVE monitoring.

### 4. Dependency and supply-chain exposure

Relevant OWASP themes:
- vulnerable and outdated components
- software and data integrity failures

Required baseline:
- dependency vulnerability scanning must stay PR-visible
- dependency source and license policy should remain explicit
- the repo should have an intentional path for dependency update churn instead of silent drift
- security updates from GitHub's native advisory system should remain enabled

Current repo status:
- **mostly meets baseline**, with one important settings-side follow-up still open

Evidence:
- `cargo audit` is a required CI signal for Rust dependency vulnerabilities
- `cargo deny check licenses sources` is a required CI signal for license/source policy
- GitHub reports `dependabot_security_updates` as enabled
- issue #73 and PR #76 define the Renovate operating lane for routine dependency updates

Tracked gap:
- issue #73 remains `waiting-on-human` because the in-repo Renovate configuration is ready, but a maintainer still needs to install/enable the Renovate app (or an approved equivalent runner) before the update lane is live

### 5. Static analysis and workflow scanning

Relevant OWASP themes:
- security misconfiguration
- software and data integrity failures

Required baseline:
- workflow logic should receive automated static analysis
- Rust analysis should remain visible on pull requests even if the project keeps it advisory instead of mandatory product gating
- settings-side limitations should be documented explicitly instead of hidden behind a permanently red workflow

Current repo status:
- **meets the current staged baseline**

Evidence:
- CodeQL runs on pull requests and `main`
- the active `main-protection-ruleset` requires `analyze (actions)` and `analyze (rust)` on `main`
- `docs/development/security-automation-plan.md` records the rollout history and supported Rust-mode considerations

### 6. CVE monitoring and triage cadence

Relevant OWASP themes:
- vulnerable and outdated components
- security logging and monitoring failures

Required baseline:
- Casgrain should have a documented way to review newly disclosed CVEs that might affect dependencies, build tooling, CI actions, runtime components, or supporting infrastructure
- the first version should prefer authoritative sources and clear relevance rules over noisy broad alerts
- relevant findings should turn into GitHub issues or PRs instead of disappearing into chat or ad hoc notes

Current repo status:
- **mostly meets baseline**, with a small set of non-dependency surfaces still handled manually

Current automated cadence:
1. the weekly `cve-watch` workflow runs `cargo audit --json` for Rust crate advisories
2. the same workflow also queries open GitHub-native Dependabot alerts for the repo's watched non-Cargo ecosystems:
   - GitHub Actions dependencies referenced by `.github/workflows/`
   - Gradle-managed dependencies used by the Android smoke fixture
3. the workflow now also evaluates `.github/security-tooling-watch.json`, the checked-in inventory of workflow-installed security tooling outside Cargo.lock / Dependabot coverage:
   - `cargo-audit` and `cargo-deny` use GitHub `securityVulnerabilities` GraphQL data keyed by the pinned crates.io package and compare the pinned version against the advisory `vulnerableVersionRange`
   - `gitleaks` stays explicit `manual-review-required` until the repo adopts a trustworthy machine-readable advisory source for its downloaded release-tarball path
4. the workflow also evaluates `.github/runner-host-watch.json`, the checked-in inventory of watched runner-image / host-toolchain facts for the Android and iOS smoke workflows:
   - both mobile smoke artifacts now include `host-environment.json` as the normalized runner/toolchain evidence source, with `emulator.json`, `simulator.json`, and `xcodebuild.log` remaining supporting evidence
   - the watch compares only the inventoried runner image, OS, Java, Gradle, Xcode, simulator, and emulator facts against the baseline and opens `security: runner-host review needed` when a watched fact drifts, when required host evidence is missing/unreadable, or when the promoted `runner-images` release metadata disagrees with the observed runner-image facts
   - `.github/runner-host-advisory-sources.json` is the repo-owned source-rule contract for runner-host promotion decisions; `runner-images` is now the delivered source-backed group on `main`, while `android-java`, `android-gradle`, and `android-emulator-runtime` remain manual-review follow-ups and the remaining iOS work still renders as one combined `ios-xcode-simulator` placeholder entry for current-main compatibility
   - the Android backlog now stays split across `#154`, `#155`, and `#156` rather than one combined `android-java-gradle` umbrella, `java.distribution` remains outside the watched runner-host inventory on current `main`, and the live iOS follow-up ownership now lives in open `#164` / `#165` rather than the earlier umbrella issue
5. all four slices render triage-friendly markdown, sync a managed GitHub findings issue only when their slice-specific alert condition is active, and close that managed issue again on later clean runs

Remaining manual review:
1. review authoritative sources for surfaces that are still outside the automated dependency graph, explicit security-tooling inventory, and drift-based runner-host watch, starting with cve.org / CVE Services data, GitHub security advisories, and release/advisory feeds for workflow-critical downloaded tooling
2. compare findings only against Casgrain's actual remaining manual surface area:
   - source-backed host-toolchain advisory evaluation beyond the delivered `runner-images` release-metadata slice, as split across #154, #155, #156, #164, and #165; current `main` still keeps one combined `ios-xcode-simulator` manifest placeholder while that later iOS split remains backlog work
   - repo-security tooling or settings-side gaps that require maintainer/platform action rather than an in-repo diff
   - any downloaded tooling not yet represented in `.github/security-tooling-watch.json` with a trustworthy source rule
3. classify each finding as one of:
   - **action now** — directly affects a package/tool/action currently used by the repo and needs an issue or PR immediately
   - **track** — plausibly relevant but needs version/surface verification before action
   - **ignore with reason** — not used by Casgrain, or only affects unsupported configurations
4. record anything actionable in GitHub with the relevant evidence, affected surface, and next bounded step
5. if the safe fix depends on settings, billing, unavailable runners, or maintainer-only activation, use `blocked` and/or `waiting-on-human` explicitly instead of inventing a fake in-repo resolution

Tracked gap:
- later source-backed promotion work for the runner-host watch now stays split across the delivered `#143` (`runner-images`) slice plus the remaining open follow-ups `#154` (`android-java`), `#155` (`android-gradle`), `#156` (`android-emulator-runtime`), `#164` (`ios-xcode`), and `#165` (`ios-simulator-runtime`); current `main` still keeps one combined `ios-xcode-simulator` manifest placeholder for the remaining iOS backlog

## Known gaps and tracked follow-up

- #73 — activate the Renovate lane by enabling the app/runner outside the repo
- #154 — evaluate source-backed advisory automation for Android Java host surfaces
- #155 — evaluate source-backed advisory automation for Android Gradle host surfaces
- #156 — evaluate source-backed advisory automation for Android emulator-runtime host surfaces
- #143 — delivered source-backed runner-image release-metadata automation for GitHub-hosted runner image surfaces
- #164 — evaluate source-backed advisory automation for iOS Xcode host surfaces
- #165 — evaluate source-backed advisory automation for iOS simulator runtime-catalog host surfaces

## Triage rules for security findings

When a security finding appears, the security or DevOps lane should answer these questions before changing code or labels:
1. does the finding affect a dependency, action, tool, or runtime surface Casgrain actually uses today?
2. is the issue already prevented by an existing required check, GitHub setting, or merge policy?
3. is the needed response an in-repo change, a GitHub settings change, or a human-owned platform/billing decision?
4. can the next bounded step land safely in one PR without changing product behavior or developer experience?

Response policy:
- **in-repo fix available** → open or update an issue, implement the narrowest safe PR, and validate honestly
- **settings-side fix required** → open or update an issue with concrete evidence, mark `blocked` and/or `waiting-on-human` when appropriate, and avoid pretending a docs-only change fully resolves it
- **advisory only / not applicable** → record the reason in the issue, PR, or scheduled report so the decision is durable

## Relationship to other repo docs

- `docs/development/security-automation-plan.md` explains the current CI security checks and staged rollout decisions
- `docs/development/automation-agent-operations.md` defines how the DevOps and security-oriented agent lanes should operate
- `docs/development/merge-and-validation-policy.md` defines merge discipline for low-risk CI/security changes
- `docs/validation.md` remains the canonical required-check contract
