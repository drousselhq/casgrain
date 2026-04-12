# Mobile Agent Runtime

Agent-native mobile runtime for iOS simulators and Android emulators, designed for three first-class use cases from day one:

1. CI/CD execution of deterministic mobile tests
2. Local developer workflows on laptops/desktops
3. LLM-agent workflows for exploration, authoring, repair, and autonomous execution

## Vision

Build a cleanly architected platform where:
- deterministic execution is trustworthy enough for CI
- specs remain documented and reviewable at all times
- agents can explore, author, and repair tests without becoming part of the deterministic execution path

## Principles

- Deterministic engine first
- Specs before implementation
- Clean architecture and strict separation of concerns
- JSON/structured interfaces for machine consumers
- Human-readable documentation and traceability for team adoption
- Cross-platform where honest, platform-specific where necessary
- Favor performant, safe implementation languages for the core runtime

## Working implementation direction

Current architectural direction:
- Rust for the core engine, compiler, execution, trace, and artifact layers
- Swift for iOS-specific adapter/glue where native integration is beneficial
- Kotlin/Java for Android-specific adapter/glue where native integration is beneficial

This is intended to maximize:
- safety
- maintainability
- testability
- local CLI performance
- long-term suitability for mobile-focused engineering teams

## Initial repository structure

- `docs/architecture/` — architecture and bounded-context documents
- `docs/prd/` — product requirements and scope
- `docs/openspec/` — executable intent/specification source files
- `tasks/` — backlog and planning artifacts
- `src/` — implementation (to be added later)
- `tests/` — automated test suites (to be added later)

## Initial scope

The first phase focuses on:
- domain architecture
- execution-plan model
- selector strategy
- agent-facing workflows
- CI/local/agent interface design
- OpenSpec-driven documentation

No implementation code is committed yet beyond repository scaffolding.
