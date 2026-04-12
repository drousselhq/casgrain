# Product Naming and UI Governance

## Naming

`mobile-agent-runtime` is currently a repository-friendly placeholder, not a final product brand.

A future product name should:
- be short enough to say and remember
- sound credible beside tools like Maestro, Appium, and RocketSim
- feel product-like rather than purely infrastructural
- leave room for deterministic execution, local dev workflows, agent workflows, and possible future UI surfaces
- survive CLI/package/repo naming constraints reasonably well

### Naming anti-goals
- overly generic infrastructure labels
- names that sound like internal codegen plumbing only
- names that overfit one interface mode such as only CLI or only agent use

### Naming workflow
1. define evaluation criteria
2. produce shortlist candidates
3. check obvious repo/domain conflicts
4. choose preferred direction
5. plan migration from placeholder naming if needed

Tracked follow-up:
- issue #9

## UI governance

The current product surface is intentionally CLI/CI first.

If future UI surfaces are introduced beyond CLI/CI, a design system must be defined before feature UI implementation begins.

That design system should cover:
- visual tokens
- typography and spacing scales
- reusable components
- navigation and information hierarchy
- artifact/result presentation patterns
- accessibility and density expectations

This rule exists to keep any future UI coherent, maintainable, and product-grade.

Tracked follow-up:
- issue #10
