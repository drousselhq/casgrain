# Rust coding guide

This guide defines the default Rust coding expectations for Casgrain contributors.

It is intentionally practical and repo-specific:
- prefer official Rust defaults over custom style rules
- keep the deterministic core explicit and easy to review
- optimize for small, honest PRs rather than broad cleanup campaigns

See also:
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
- [`docs/validation.md`](../validation.md)
- [`docs/architecture/clean-architecture.md`](../architecture/clean-architecture.md)
- [`docs/architecture/rust-domain-model-and-scaffolding.md`](../architecture/rust-domain-model-and-scaffolding.md)

## Baseline toolchain and quality bar

Casgrain currently pins Rust `1.85.0` in `rust-toolchain.toml` and the workspace `rust-version` to `1.85`.
When the toolchain changes, update both files together so contributor docs, local development, and CI stay aligned.

Use the pinned toolchain for local work and treat these commands as the canonical baseline:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

For the full merge gate, follow `docs/validation.md`.

## Formatting and linting

- `cargo fmt` is the formatting source of truth.
- Clippy is the standard lint tool.
- Workspace Clippy policy currently denies `dbg!`, `todo!`, and `unimplemented!` across every crate to keep accidental debugging or placeholder code out of CI.
- Prefer fixing the code over adding lint suppressions.
- Prefer default Rust/Clippy behavior unless the repository has a documented reason to do otherwise.
- Keep config minimal; do not add noisy style-only rules just to increase policy surface area.

The repo also treats `cargo doc --workspace --no-deps` with `RUSTDOCFLAGS="-D warnings"` as part of the default validation gate so contributor-facing Rust docs do not silently rot.

## Architectural shape in this repo

Casgrain already has a deliberate workspace split:
- `domain` for canonical contracts and data shapes
- `application` for use-case boundaries and validation
- `compiler` for source lowering
- `runner` for deterministic execution
- `ios` / `android` for platform-specific smoke and adapter work
- `casgrain` for the CLI entrypoint

When adding or moving Rust code:
- prefer placing behavior in the narrowest crate that owns it
- avoid letting the CLI crate become the home for reusable domain logic
- keep platform-specific details out of cross-platform domain types unless the contract truly requires them
- prefer explicit data flow across crate boundaries over hidden global state

## Module and file size guidance

Keep modules small enough that a reviewer can understand them quickly.

Guidance:
- soft limit: aim for files and functions that stay easy to scan in one sitting
- warning sign: a module mixes parsing, orchestration, formatting, and platform details at once
- hard smell: a file becomes the default dumping ground for unrelated helpers or multiple responsibilities

When a module grows, prefer extracting focused helpers or submodules instead of adding more sections to one giant file.

If a file is already oversized, do not opportunistically rewrite it during unrelated work. Keep the current slice bounded and open a follow-up issue when needed.

## Visibility and API surface

- default to the narrowest visibility that works
- prefer private items first, `pub(crate)` second, and fully `pub` only for real crate APIs
- every public type or function should have a clear caller and a stable reason to exist
- avoid exporting convenience helpers that only serve one internal code path

Small modules with intentional visibility are easier to refactor safely than wide, leaky APIs.

## Types and boundaries

Prefer types that make invalid states harder to represent.

- use structs and enums to model domain concepts explicitly
- prefer newtypes for domain identifiers, user-facing handles, or validated values when raw `String`/`u64` usage starts to blur meaning
- use traits for real behavior boundaries such as compiler, runner, or device-engine seams
- only introduce builders when construction is genuinely complex, multi-step, or validation-heavy
- do not add builders for small plain-data structs that are already clear with struct literals

In this repo, trait boundaries should usually clarify execution seams, not hide simple local logic behind indirection.

## Naming conventions

- use names that match the language of the product and architecture docs
- prefer explicit names over abbreviations unless the term is already standard in Rust or the domain
- types should read like nouns (`ExecutablePlan`, `TargetProfile`)
- functions should read like actions (`validate_plan`, `render_run_summary`)
- prefer `snake_case` module and function names, `CamelCase` types, and `SCREAMING_SNAKE_CASE` constants
- keep public API names boring and literal; avoid clever wording in stable surfaces

When a name appears in traces, plan JSON, or CLI output, optimize for clarity over brevity.

## Errors, `Result`, and `panic!`

Default rule:
- return `Result` for fallible runtime behavior
- reserve `panic!` for invariants that indicate programmer error or impossible states

More specifically:
- use typed errors when the boundary benefits from structure
- use readable string errors only when the boundary is intentionally lightweight and the loss of structure is acceptable
- add context to errors at crate or process boundaries so failures are actionable in CI logs and traces
- do not silently swallow I/O, process, serialization, or adapter failures

### `unwrap()` and `expect()` policy

- do not introduce `unwrap()` in production paths
- `expect()` is acceptable in tests when the failure message is specific and helps diagnosis
- in production code, use `expect()` only for true invariants that would represent a bug if violated
- if you use `expect()`, make the message explain the invariant, not restate the method name

Good test example:
- `expect("trace output should be valid json")`

Weak example:
- `expect("unwrap failed")`

## `unsafe` policy

`unsafe` is by exception, not by style.

Only use it when there is no reasonable safe alternative and the need is explicit.

If `unsafe` is required:
- keep the unsafe region as small as possible
- add a short comment explaining the invariant being relied on
- document why the operation is safe in this context
- add or update tests that would fail if the invariant stops holding

Do not normalize `unsafe` as a convenience escape hatch.

## Testing expectations

- behavior changes should come with targeted tests when the crate already has a relevant test surface
- prefer tests near the code they protect unless the behavior is explicitly cross-cutting
- preserve deterministic assertions; avoid time-, ordering-, or environment-sensitive checks unless the behavior specifically requires them
- when tests mutate process-wide environment state, serialize them and restore the prior state explicitly
- for CLI-facing behavior, prefer contract-style assertions on output shape and error messages
- for compiler and runner behavior, prefer explicit fixture-driven expectations over broad snapshot churn

## Dependency hygiene

- prefer the standard library unless a crate materially improves correctness or clarity
- keep the dependency graph small and understandable
- avoid adding overlapping crates that solve nearly the same problem
- prefer well-maintained, mainstream crates with a clear maintenance story
- new dependencies must be compatible with the repo's validation and security posture (`cargo audit`, `cargo deny`, CI reproducibility)

When adding a dependency, be ready to explain:
- why the standard library is not enough
- why this crate is the right fit
- what new maintenance or security surface it introduces

## Supported Rust version guidance

- treat the pinned toolchain and workspace `rust-version` as the compatibility contract
- do not use features that require a newer stable Rust version unless the repo explicitly updates that contract
- if a change would benefit from a language or standard-library feature from a newer edition/toolchain, capture that as intentional follow-up work rather than sneaking it into an unrelated PR

## Practical review checklist

Before opening a PR, quickly verify:
- formatting is clean with `cargo fmt`
- Clippy is clean without casual suppressions
- the code lives in the right crate and module
- visibility is no broader than necessary
- fallible paths return useful errors
- new tests cover the changed behavior
- no unnecessary dependency or abstraction was introduced
- docs were updated if the change affects contributor expectations or public behavior
