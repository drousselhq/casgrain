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
- relevant findings should surface as failed scheduled workflow runs with self-contained summaries, then become PRs or explicitly approved follow-up work instead of bot-created backlog issues

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
4. the workflow still renders `.github/runner-host-watch.json`, the checked-in inventory of watched runner-image / host-toolchain facts for the Android and iOS smoke workflows, as report-only evidence in the workflow summary
5. the Rust dependency, non-Cargo Dependabot, and workflow-installed security-tooling slices fail their scheduled job when an active advisory affects a watched surface; none of the slices create, reopen, update, label, or close GitHub issues automatically

Remaining manual review:
1. review authoritative sources for surfaces that are still outside the automated dependency graph and explicit security-tooling inventory, starting with cve.org / CVE Services data, GitHub security advisories, and release/advisory feeds for workflow-critical downloaded tooling
2. compare findings only against Casgrain's actual remaining manual surface area:
   - repo-security tooling or settings-side gaps that require maintainer/platform action rather than an in-repo diff
   - any downloaded tooling not yet represented in `.github/security-tooling-watch.json` with a trustworthy source rule
   - runner-host drift/source-rule evidence when a maintainer intentionally chooses to act on the report
3. classify each finding as one of:
   - **action now** — directly affects a package/tool/action currently used by the repo and needs a PR or explicitly approved follow-up
   - **track** — plausibly relevant but needs version/surface verification before action
   - **ignore with reason** — not used by Casgrain, or only affects unsupported configurations
4. record anything actionable in a PR, maintainer note, or explicitly approved follow-up with the relevant evidence, affected surface, and next bounded step
5. if the safe fix depends on settings, billing, unavailable runners, or maintainer-only activation, use `blocked` and/or `waiting-on-human` only on human-approved work items instead of bot-minted scheduled-watch issues

## Known gaps and tracked follow-up

- #73 — activate the Renovate lane by enabling the app/runner outside the repo
- delivered source-backed runner-host report slices on current `main`: #143 (`runner-images`), #154 (`android-java`), #155 (`android-gradle`), and #156 (`android-emulator-runtime`)
- iOS Xcode/simulator source-backed runner-host promotion is intentionally not queued as autonomous backlog work unless a maintainer reopens that direction explicitly

## Triage rules for security findings

When a security finding appears, the security or DevOps lane should answer these questions before changing code or labels:
1. does the finding affect a dependency, action, tool, or runtime surface Casgrain actually uses today?
2. is the issue already prevented by an existing required check, GitHub setting, or merge policy?
3. is the needed response an in-repo change, a GitHub settings change, or a human-owned platform/billing decision?
4. can the next bounded step land safely in one PR without changing product behavior or developer experience?

Response policy:
- **in-repo fix available from a CVE-watch finding** → implement the narrowest safe PR directly from the failed run summary; do not mint a scheduled-watch GitHub issue first
- **in-repo fix available from human triage** → use a human-approved issue only when the next step is not immediately safe to implement as a PR
- **settings-side fix required** → record concrete evidence in the PR/run handoff or an explicitly approved issue; mark `blocked` and/or `waiting-on-human` only on human-approved work items
- **advisory only / not applicable** → record the reason in the PR, scheduled report, or approved follow-up so the decision is durable

## Relationship to other repo docs

- `docs/development/security-automation-plan.md` explains the current CI security checks and staged rollout decisions
- `docs/development/automation-agent-operations.md` defines how the DevOps and security-oriented agent lanes should operate
- `docs/development/merge-and-validation-policy.md` defines merge discipline for low-risk CI/security changes
- `docs/validation.md` remains the canonical required-check contract
