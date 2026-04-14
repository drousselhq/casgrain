# Deterministic Bug Reproduction Evidence Contract

## Goal

When a contributor or agent says a Casgrain bug is reproduced, the claim should come with enough structured evidence that another maintainer can understand the failure without guessing.

This contract keeps reproduction work:
- deterministic when the bug itself is deterministic
- explicit about uncertainty when the failure appears flaky
- aligned with `CONTRIBUTING.md`, `docs/validation.md`, and `docs/development/automation-agent-operations.md`

## When this contract applies

Use this contract for:
- product/runtime bug reports
- CI failures that might reflect a real product regression
- local reproduction notes attached to GitHub Issues or PRs
- agent-produced reproduction reports during maintenance or repair work

## Minimum evidence package

A reproduction report is not complete unless it includes all of the following.

### 1. Precise code and environment identity

Record the exact code under test:
- commit SHA
- branch name, if not on `main`
- whether the worktree was clean or had local modifications

Record the execution environment that could affect reproduction:
- operating system and version
- Rust toolchain version (`rustc --version`)
- relevant simulator/emulator target details when mobile execution is involved
- any repo-specific inputs or fixture paths needed for the run

### 2. Smallest reproducible sequence

Capture the shortest command sequence that reproduces the problem.

Expectations:
- prefer copy-pasteable shell commands over prose-only descriptions
- include required setup commands only when they materially affect the result
- name the specific feature, fixture, test, workflow, or command under investigation
- state the expected result and the actual result

### 3. Determinism classification

Explicitly classify the reproduction result as one of:
- **deterministic** — reproduced repeatedly with the same failure signature
- **flaky** — reproduced intermittently or with materially different signatures
- **not yet classified** — initial evidence exists, but repeat runs are still needed

For deterministic reports, include at least one confirming rerun when the command cost is reasonable.

For flaky reports, include:
- how many attempts were run
- how many failed
- whether the failure signature stayed the same across attempts
- any suspected environment coupling (for example simulator boot timing or GitHub-hosted runner variance)

### 4. Required evidence artifacts

Attach or link the concrete evidence needed to inspect the failure:
- failing command output
- structured traces when available
- relevant logs
- screenshots or produced artifacts when visual state matters
- GitHub Actions run/job links for CI failures

Prefer artifact paths or URLs over summary-only prose. If the failure produced no artifact, say so explicitly.

### 5. Boundary classification

State which bucket currently owns the problem:
- **product/runtime bug** — Casgrain behavior appears wrong even in a stable environment
- **CI/infrastructure bug** — workflow setup, runner environment, or repository automation appears wrong
- **flaky/needs isolation** — the signal is real but cannot yet be cleanly assigned to product or infrastructure

If the boundary is unclear, say why instead of forcing a confident label.

## Reporting format in GitHub

### Issue updates

When reporting reproduction work in an issue, include:
- the reproduction command sequence
- environment details
- determinism classification
- links or paths to traces/logs/artifacts
- the current product-vs-CI boundary classification
- the smallest credible next step

### Pull requests

When a PR fixes a reproduced bug, the PR body should reference:
- the issue containing the reproduction evidence
- the exact validation command used to confirm the fix
- any remaining uncertainty if the original failure was flaky rather than deterministic

## What good evidence looks like

A strong reproduction report makes it possible for another maintainer to answer:
- what exact code and environment were tested?
- what command should I run?
- what outcome was expected?
- what actually happened?
- is this deterministic, flaky, or still unclear?
- where are the traces/logs/artifacts?
- is the next step a product fix, CI fix, or more isolation work?

## What does not meet the bar

The following are insufficient on their own:
- "it failed in CI" without a run link or job evidence
- "I can reproduce locally" without the command sequence
- screenshots without the command/log context that produced them
- a single failure claimed as flaky without repeated attempts
- a claimed deterministic bug without any environment or commit details

## Relationship to other repo documents

- `CONTRIBUTING.md` defines the minimum bug filing expectations for contributors
- `docs/validation.md` defines the canonical validation gate and completion reporting
- `docs/development/automation-agent-operations.md` defines which agent role performs reproduction work and how it hands evidence back into issues and PRs
