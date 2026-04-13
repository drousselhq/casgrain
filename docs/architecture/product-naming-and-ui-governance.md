# Product Naming and UI Governance

## Naming

`mobile-agent-runtime` is currently a repository-friendly placeholder, not the intended long-term product brand.

Selected working product name:
- **Casgrain**

Rationale recorded so far:
- it gives the product a stronger, more ownable identity than the descriptive repository placeholder
- it avoids the collision pressure found in crowded candidates like Lighthouse
- it is meaningful to Daniel, honoring Thérèse Casgrain

The product name should still satisfy the original criteria:
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

### Current migration plan
1. keep `mobile-agent-runtime` as the temporary repository/package slug while core architecture is still stabilizing
2. treat **Casgrain** as the intended product-facing name in docs and future positioning work
3. once repo/package rename work is scheduled, map the rename surface explicitly: GitHub repository, Cargo package names, CLI binary naming, docs, and any future website/assets
4. avoid partial renames that create mixed branding across artifacts

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
