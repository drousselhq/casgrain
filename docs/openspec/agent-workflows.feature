Feature: Agent-native workflows are first-class citizens
  In order to make LLM tools genuinely useful for mobile development
  As a platform team
  We want agents to explore, author, repair, and operate against the same runtime platform

  Rule: Agents are first-class users, not an afterthought

    Scenario: An agent explores an app interactively
      Given an interactive device session
      When an agent requests screen state, logs, and available actions
      Then the runtime returns structured observations
      And the agent can perform bounded interactions through explicit commands

    Scenario: An agent authors a deterministic test artifact
      Given a requirement spec or explored flow
      When an agent requests test generation
      Then the system produces a deterministic executable plan
      And the generated artifact is reviewable and version-controlled

    Scenario: An agent proposes a repair for a failed test
      Given a failed execution trace with artifacts
      When an agent analyzes the failure
      Then it can propose selector or wait-condition updates
      But deterministic CI execution still does not require an LLM
