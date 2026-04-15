# Casgrain Product Spec

This file defines Casgrain's product feature set in Gherkin.

Important distinction:
- This file describes Casgrain the product.
- It does not describe Hermes' internal coding workflow.
- Hermes may use PRDs and specs while building Casgrain, but those process conventions are separate from Casgrain's end-user model.

Current product framing:
- Casgrain is a mobile testing and exploration tool for iOS simulators and Android emulators.
- Casgrain should support user-provided Gherkin where that is the right authoring substrate.
- Casgrain compiles or derives deterministic test plans that can run repeatably.
- Casgrain should also support discovery-oriented workflows that observe an app and generate candidate Gherkin from evidence.
- LLMs may assist authoring, exploration, repair, and summarization, but are not part of the deterministic execution path.
- The first product-true vertical slice is intentionally minimal: one fixture-specific iOS scenario compiled from `fixtures/ios-smoke/features/tap_counter.feature` and executed through `casgrain run-ios-smoke`.
- That first slice is iOS-only for now and exists to prove the honest end-to-end path from user-authored Gherkin to simulator-backed execution with structured artifacts.
- The mock runner and handwritten XCTest harness are still useful development infrastructure, but they are not the canonical proof for this first user-facing slice.

```gherkin
Feature: Deterministic mobile test execution
  As a developer or QA analyst
  I want Casgrain to execute mobile test plans deterministically
  So that I can trust local and CI results

  Scenario: Run a deterministic test plan against a simulator
    Given a valid executable test plan
    And an available iOS simulator or Android emulator target
    When Casgrain runs the test plan
    Then each step is executed in a defined order
    And the result is reproducible from the same inputs and environment
    And the run produces machine-readable structured results

  Scenario: Keep LLMs out of the deterministic execution path
    Given a test plan is being executed
    When Casgrain performs runtime actions and assertions
    Then no LLM decides the next runtime action
    And the execution path is fully determined by explicit plan data and runtime state

Feature: Gherkin to test plan compilation
  As a developer or QA analyst
  I want Casgrain to accept user-provided Gherkin
  So that I can define behavior in a familiar testing language

  Scenario: Compile user Gherkin into an executable test plan
    Given a Gherkin feature file provided by a user
    When Casgrain compiles the feature file
    Then Casgrain produces a deterministic executable test plan
    And the plan preserves the intent of the Gherkin steps
    And the output can be executed locally or in CI

  Scenario: Report compilation errors with traceable feedback
    Given a Gherkin feature file contains unsupported or ambiguous steps
    When Casgrain attempts compilation
    Then Casgrain reports a structured compilation failure
    And the failure identifies the offending scenario and step
    And the user can see what must change to make the feature executable

Feature: Structured execution artifacts
  As a developer or QA analyst
  I want rich artifacts from each run
  So that I can debug failures and understand behavior quickly

  Scenario: Capture artifacts during execution
    Given a test plan is executed
    When Casgrain completes or fails a run
    Then Casgrain records structured traces for executed steps
    And Casgrain can emit screenshots and other relevant artifacts
    And the artifacts are linked to the scenario, step, and outcome

  Scenario: Preserve machine-readable failure evidence
    Given a test step fails
    When Casgrain reports the run result
    Then the failure output includes structured error details
    And associated runtime evidence is available for debugging and repair

Feature: Local developer workflow
  As a mobile developer
  I want a fast local CLI workflow
  So that I can explore, debug, and iterate without depending on remote infrastructure

  Scenario: Run tests locally from the command line
    Given a local mobile development environment
    And a simulator or emulator is available
    When the developer invokes Casgrain from the CLI
    Then Casgrain can compile or run the requested test artifact locally
    And the developer receives machine-readable output and useful local artifacts

  Scenario: Use Casgrain to investigate a failing behavior locally
    Given a test fails on a developer machine
    When the developer reruns the scenario with tracing enabled
    Then Casgrain produces enough structured evidence to support debugging
    And the rerun remains deterministic

Feature: CI-friendly execution
  As a CI platform owner
  I want Casgrain runs to be stable in automation
  So that mobile validation can be trusted in pipelines

  Scenario: Execute tests in CI with deterministic outputs
    Given a CI job provisions the required simulator or emulator environment
    And the repository contains executable test artifacts
    When Casgrain runs in CI
    Then the command exits with an automation-friendly status code
    And the run produces machine-readable output for downstream systems
    And artifacts can be archived by the pipeline

  Scenario: Re-run the same artifact in CI and locally
    Given the same executable test artifact
    And equivalent target environment configuration
    When the artifact is run locally and in CI
    Then the observed behavioral result is consistent within the supported runtime guarantees

Feature: App exploration and inspection
  As a developer, QA analyst, or agent
  I want to inspect app state and available interactions
  So that I can author, debug, and repair tests effectively

  Scenario: Inspect the current app surface during exploration
    Given Casgrain is connected to a running simulator or emulator session
    When the user requests app inspection
    Then Casgrain returns structured information about the visible app state
    And the output is suitable for human and agent consumption

  Scenario: Use inspection data to support authoring and debugging
    Given structured app inspection output is available
    When a user or agent reviews the output
    Then they can identify candidate interactions, assertions, and missing selectors

Feature: Agent-assisted repair outside the execution path
  As a developer using an agent
  I want help diagnosing and repairing tests
  So that failures can be resolved faster without compromising deterministic execution

  Scenario: Use structured traces for repair suggestions
    Given a run has failed
    And structured traces and artifacts are available
    When an agent analyzes the failure
    Then the agent can propose a repair candidate
    But the proposed repair is outside the deterministic execution path

  Scenario: Keep repair suggestions traceable
    Given an agent proposes a repair
    When the proposal is surfaced to the user
    Then the proposal references concrete execution evidence
    And the user can review what changed and why

Feature: Generate Gherkin from observed behavior
  As a QA analyst or developer
  I want Casgrain to propose Gherkin from observed app behavior
  So that existing software can be documented as maintainable executable scenarios

  Scenario: Generate candidate Gherkin from a traced session
    Given a user explores an app on a simulator or emulator
    And Casgrain captures structured runtime observations
    When Casgrain derives candidate scenarios from the observed behavior
    Then Casgrain outputs candidate Gherkin scenarios
    And each scenario is linked to supporting runtime evidence
    And the output is clearly marked as generated and reviewable

  Scenario: Keep generated Gherkin reviewable before execution use
    Given Casgrain has generated candidate Gherkin
    When a user inspects the generated scenarios
    Then the user can review and edit the scenarios before adopting them
    And generated Gherkin is not treated as trusted execution input without review

Feature: Generate Gherkin from source and runtime evidence together
  As a developer or QA analyst
  I want Casgrain to combine code analysis with runtime evidence
  So that generated scenarios better reflect actual product behavior

  Scenario: Synthesize candidate scenarios from source and runtime data
    Given source code structure or metadata is available
    And runtime traces or app inspection data are available
    When Casgrain analyzes both forms of evidence
    Then Casgrain can propose richer candidate Gherkin scenarios
    And each proposed scenario includes traceability back to observed evidence

Feature: Platform adapter architecture
  As a maintainer
  I want platform-specific automation to live behind explicit adapters
  So that the deterministic core remains portable and understandable

  Scenario: Execute through a platform adapter
    Given a test plan targets iOS or Android
    When Casgrain executes the plan
    Then the deterministic core delegates platform-specific actions to the appropriate adapter
    And the adapter returns structured runtime results back to the core

Feature: Machine-readable outputs first
  As a tool integrator or agent
  I want stable structured outputs
  So that Casgrain composes well with automation systems

  Scenario: Emit stable structured outputs for core workflows
    Given a user compiles, runs, inspects, or analyzes with Casgrain
    When the command completes
    Then the primary result can be consumed as structured machine-readable data
    And human-readable summaries do not replace the structured output contract
```
