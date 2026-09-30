# PR notes — IFC-3201

## Lifted files

`CommitHash` is lifted byte-identical from #10658 (`ple-branches-card-ifc-3130`) so the two PRs merge as an identical add/add.

- Source: `ple-branches-card-ifc-3130` at `e1042bef6e1f42686c2948d5576941fd65f447c3` (output of `git -C /Users/paul/Projects/infrahub rev-parse ple-branches-card-ifc-3130` at the time of the lift)
- Files:
  - `frontend/app/src/shared/components/display/commit-hash.tsx`
  - `frontend/app/src/shared/components/display/commit-hash.test.tsx`

Pre-merge check (empty output means the lifted files still match; re-run against the branch tip too, in case #10658 moved):

```bash
git diff e1042bef6e1f42686c2948d5576941fd65f447c3 -- frontend/app/src/shared/components/display/commit-hash*
git diff ple-branches-card-ifc-3130 -- frontend/app/src/shared/components/display/commit-hash*
```
