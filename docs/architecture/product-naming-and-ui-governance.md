# Product Naming and UI Governance

## Naming

Casgrain is the chosen product name. `mobile-agent-runtime` was the original repository-friendly placeholder used earlier in the project.

Selected product name:
- Casgrain

Rationale recorded so far:
- it gives the product a stronger, more ownable identity than the original descriptive placeholder
- it avoids the collision pressure found in crowded candidates like Lighthouse
- it is meaningful to Daniel, honoring Thérèse Casgrain

The product name should satisfy the original criteria:
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

### Current migration state
- product name: Casgrain
- repository name: `casgrain`
- historical placeholder: `mobile-agent-runtime`
- internal Rust crate names still use `mar_*` prefixes for now

A future cleanup pass may still decide whether crate names, binary names, and package surfaces should move closer to the Casgrain brand.

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
