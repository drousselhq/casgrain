# Android smoke reliability window: NOT QUALIFIED

- Threshold: `>=10` successful runs including `>=3` `schedule` runs on `main` and `>=3` `pull_request` runs
- Current streak: `total=4`, `schedule on main=1`, `pull_request=3`
- Evaluated streak run IDs: 400004, 400003, 400002, 400001
- Reason codes: `streak_summary_missing`
- Blocker run: `399999` (`conclusion=failure`, `failure_class=artifact-contract-breach`)
- Blocker summary issue: `evidence-summary.json missing from downloaded artifact`
