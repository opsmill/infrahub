# Plan file

Path: `dev/specs/<parent-key-lowercase>-refactor-<slug>/plan.md`, e.g.
`dev/specs/ifc-3301-refactor-pool-reservations/plan.md`. It lives on `stable` and reaches
`develop` through the regular stable→develop merge.

The plan file is for humans first: a reviewer of step 17 should be able to open it and understand
where the refactor is going and why this step is next. Keep it under ~300 lines; collapse done
steps to one line each.

## Rules

- **Only step PRs edit it** (plus step 0 creating it, and the final PR marking it complete). A
  step PR marks its own step `done` and may re-plan *later* steps; it never rewrites history of
  done steps.
- **Each step names a done-check** — a command whose output proves the step landed (a grep that
  returns nothing, a test that exists and passes). Reconciliation runs these, so make them exact
  and cheap.
- **Statuses:** `pending`, `in-review` (PR open), `done`, `dropped` (with reason), `needs-human`
  (with reason). The status in the file on `stable` reflects what is merged; an open PR's own
  step shows `done` only in that PR's branch.
- **Steps are numbered once and never renumbered.** A split step becomes `7a`, `7b`; a dropped step
  keeps its number. Jira keys and branch names reference these numbers.

## Template

```markdown
# Refactor: <name>

> Jira: [<PARENT-KEY>](https://opsmill.atlassian.net/browse/<PARENT-KEY>) | Status: active
> Branch prefix: `<initials>-refactor-<slug>` | Max open PRs: 1 | Size budget: ≤300 lines, ≤10 non-test files

## Goal

<2–4 sentences: what is wrong with the code today and what it looks like when done.>

## End state

- <Concrete, checkable statements, e.g. "`ReservationManager` is the only writer of IS_RESERVED edges".>

## Invariants (true after every step)

- No observable behavior change: <the specific surfaces that matter for this area — API, events, DB shape…>
- <Area-specific invariants, e.g. "both old and new code paths produce identical query results".>

## Out of scope

- <Things a reviewer might expect but this refactor will not do.>

## Coverage baseline

Measured on `origin/stable` at <commit> with `<test paths>`; refresh when reconciliation finds the
code or its tests changed.

| File / function | Lines covered | Covered only by tiers that can't run locally | Gap → step |
|-----------------|---------------|----------------------------------------------|-----------|
| `core/a/x.py::foo` | 41/58 | — | 1 |

## Forward-merge notes

- <Files in scope that differ between stable and develop, and how the step order accounts for it.>

## Steps

| # | Intent | Status | Jira | PR |
|---|--------|--------|------|----|
| 0 | Plan | done | <PARENT-KEY> | #1234 |
| 1 | Characterization tests for `foo()` edge cases | done | IFC-3302 | #1240 |
| 2 | Introduce `NewThing` alongside `OldThing` (unused) | in-review | IFC-3303 | #1251 |
| 3 | Move callers in `core/a/` to `NewThing` | pending | IFC-3304 | |

### Step 3 — Move callers in `core/a/` to `NewThing`

- **Touches:** `backend/infrahub/core/a/x.py`, `backend/infrahub/core/a/y.py` (+ tests)
- **Prerequisites:** 2
- **Pattern:** migrate callers in a batch
- **Done-check:** `rtk grep -n "OldThing" backend/infrahub/core/a/` returns nothing
- **Estimate:** ~80 lines

<Repeat a detail block for each pending step. Collapse a done step's detail block once merged.>

## Log

- 2026-10-01 — plan created.
- <date> — step 4 dropped: done by #1260 (someone else's PR) — done-check already passed.
```
