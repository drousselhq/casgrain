Feature: Deterministic execution engine and specification compilation
  In order to trust mobile automation in CI and local workflows
  As a platform team
  We want human-facing specs compiled into deterministic executable plans

  Rule: The deterministic runner must not require an LLM

    Scenario: Compile a requirement spec into an executable plan
      Given a requirement spec describing a login flow
      When the compiler processes the spec
      Then it produces an executable scenario plan
      And the plan contains explicit selectors, actions, waits, and assertions
      And the output is deterministic for the same input and compiler version

    Scenario: Run a compiled plan without model inference
      Given an executable scenario plan
      And a compatible device engine adapter
      When the runner executes the plan
      Then no LLM call is required to determine the next runtime action
      And the runner emits structured step results and artifacts

    Scenario: Fail deterministically when required selectors are unresolved
      Given an executable scenario plan with a selector that cannot be resolved
      When the runner executes the plan
      Then the run fails explicitly
      And the failure report identifies the unresolved selector
      And diagnostic artifacts are attached

  Rule: Gherkin is not the execution substrate

    Scenario: Higher-level intent compiles to lower-level executable steps
      Given a Gherkin-style scenario
      When the compiler produces an executable plan
      Then the output is more explicit than the input
      And execution semantics are not inferred at runtime from prose
