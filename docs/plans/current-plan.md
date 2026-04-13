# Current Plan

This is the live execution plan for Casgrain.

## Operating rule
- Backlog items live in GitHub Issues.
- This file stays small and focused on the current active direction.
- Archive old plans only when the live plan becomes too complex to read quickly.

## Current project direction
- Keep the deterministic core strong and explicit.
- Prove the overall approach with the first iOS adapter boundary and follow it into real simulator plumbing.
- Strengthen runner / trace / artifact quality around adapter-backed execution.
- Keep docs, validation, and governance aligned with the codebase.
- Use the macOS iOS simulator smoke workflow only for changes that may affect simulator interaction.
- Keep the first simulator-backed slice isolated: one fixture app, one UI test, one visible state change, one screenshot artifact.

## Near-term priorities
1. Expand the iOS adapter boundary into real simulator plumbing.
2. Add the smallest honest simulator-backed smoke path for a fixture app.
3. Extend runner and trace validation around the first real adapter path.
4. Keep product, architecture, and validation docs current.

## Planning discipline
- Work one bounded slice at a time.
- Update this plan when priorities change.
- Convert discovered follow-up work into GitHub Issues.
- Do not let this file become a long history log.
