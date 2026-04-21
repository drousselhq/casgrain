# Issue <number> task list

- Linked issue: #<number>
- Source contract: `./spec.md`
- Analyst note: replace every `<...>` placeholder below with slice-specific paths, artifacts, and commands before handing this to Dev / DevOps.

## Working rules

- Execute tasks in order.
- Replace template placeholders with the exact files, fixtures, commands, and evidence for this slice.
- Delete optional bullets that do not apply instead of leaving generic meta-checklist text behind.
- Update checkboxes honestly on the implementation branch as work lands.
- If this task list conflicts with `spec.md` or current `main`, hand the slice back for reshaping instead of improvising.

## Tasks

- [ ] Confirm the current slice still matches `spec.md` and current `main` for `<one-sentence slice summary>`.
- [ ] Implement `<bounded change summary>`.
  - [ ] Update `<path-or-artifact-1>` to `<required change>`.
  - [ ] Update `<path-or-artifact-2>` to `<required change>`.
- [ ] Add or update validation coverage for the slice.
  - [ ] Update `<test-or-fixture-path>` to prove `<acceptance check>`.
  - [ ] Capture `<log-or-artifact>` if the slice requires workflow/runtime evidence.
- [ ] Run the exact validation commands for this slice.
  - [ ] `<command 1>`
  - [ ] `<command 2>`
- [ ] Reconcile the required repo docs/spec/runbook artifacts.
  - [ ] Update `<doc-path>` so it states `<required wording or contract change>`.
- [ ] Prepare the PR summary with exact validation evidence and honest closure semantics for `#<number>`.
