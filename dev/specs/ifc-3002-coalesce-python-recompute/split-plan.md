# Splitting the branch into reviewable PRs

Written as a handoff. Everything needed to execute it is here; no conversation history required.

## Where things stand

- Branch `coalesce-python-recompute-ifc-3002`, 47 commits, based on `develop`, pushed and green.
- Pre-CI passes: 2288 unit tests, ruff, `ty`, generated files, schemas, docs.
- PR #10288, the branch-tag fix, is already merged into `release-1.11`.
- IFC-3015 tracks moving the pass off the merge and rebase critical path. Out of scope here.

## What the feature is worth, in one table

Measured on today's `release-1.11` with the same harness, 20 changed source nodes:

| 20 changed nodes | Base | Branch |
|---|---|---|
| Merge, `process_transform` runs | 20 | ~2 |
| Merge, `query_transform_targets` runs | 60 | 0 |
| Rebase, `process_transform` runs | 20 | ~2 |
| Rebase, `query_transform_targets` runs | 100 | 0 |
| Readers refreshed | 20 | 20 |

**The claim to make, and the one to avoid.** The work scales with the number of *changed* nodes, not
with the number of nodes reading them. A merge that changes little does not get faster, and a
production comparison on that shape measured base and branch as equal. Do not promise a duration:
the same timing metric moved between 62.9 s and 121.0 s across identical runs on this hardware.

## The four PRs

Each targets the previous branch. Risk is concentrated in PR4, which is deliberately tiny.

### PR 1 — Shared plumbing and the switch. No behaviour change.

- `3e639d017` share the query-group subscriber lookup
- The `whole_kind` field on `AffectedTarget` and its handling in `plan()`, plus the
  `PYTHON_ATTRIBUTE` family literal, from `ecf42f4c6`. Inert: nothing emits it yet.
- The feature switch in `config.py`, with `253ced50a` squashed in for `schema/openapi.json` and the
  generated configuration page.
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/` from `96a227dd6` and `de94c326b`.

Reviewer question: does this change any behaviour? No.
Standalone value: the subscriber lookup was duplicated between regeneration and computed
attributes. This is also the answer to "why not reuse the post-merge regeneration work" — it does.

### PR 2 — The resolver. Standalone, nothing calls it.

- `818138eab` the seam, `1bdf5262c` the database sources, `922ff02dd` the narrowing
- `0cec55754` squashed in, which is the fix for the widening regression. Do not ship the
  pre-fix behaviour in one PR and correct it in a later one.
- `1442cfb43` the index cache and the per-pass lookup memo
- Unit tests in final state, plus the test doubles

Includes the change to `TransformReadSet.from_read_fields` so a kind read without any field stays a
kind-level dependency. **That is shared with the schema-change scoper**, so call it out: a kind add
or remove still selects, a field edit on a field-less kind no longer does. It is also the same
semantics as #10189, which is on `release-1.11` and still not on `develop`.

Reviewer question: is the narrowing correct, and does it fail safe? Nothing calls it, so it cannot
break anything.

### PR 3 — Activate. Work happens twice, nothing is missed.

- `576974d17` builder derivation
- `46cafe2e7` the wiring, and the `process_transform` changes
- The schema-convergence wait, which has to be **split out of** `2db2a3c79`
- `f4d2a5e54` the selection and widening logs
- `952cf17f4` deleted peer, `b3d90eef6` schema overlap
- `23963b47f` and `44ac0fa6d` their tests

Reviewer question: with the switch on, is anything done twice or missed? Twice, never missed.
Standalone value: `process_transform` used to ignore the attribute name it was given and recompute
every Python attribute of the kind, so a kind with several did N times the work.

### PR 4 — Suppress, and prove it. About thirty lines of behaviour.

- The origin filter on both Python triggers, the other half of `2db2a3c79`
- `c1c1830fe` the compose passthrough for the switch
- The harness: `dceb62187`, `0f2788bbf`, `5f10c0ed5`
- The gates: `8616f08f2` parity, `184313b78` dispatch shape, `913191b78` the imprecise gate
- All of `baseline.md`, the spec revisions, and the `tasks.md` checkboxes

Reviewer question: is the measured win real, and can we roll back? Both answers are in the diff.

## Mechanics

- Drop `634138689` entirely. It is in `release-1.11` and arrives through the next develop sync.
- Squash the corrections into what they correct rather than shipping them as separate commits:
  `91e45ad49` (develop adaptation), `0868d5832` (docstring trim), `909bfc553` (type fixes),
  `fa7832d4e` (gate window), `e75602d33` and `913191b78` (the xfail reproductions, which the fix
  then removed).
- `2db2a3c79` must be split: convergence wait to PR3, origin filter to PR4.
- Keep `tasks.md` out of PRs 1 to 3. Ticking checkboxes in each guarantees conflicts between
  stacked branches. Update it once, in PR4.
- Expect to rebase 2, 3 and 4 if PR1 or PR2 gets substantive review comments.

## Things that will cost an hour if forgotten

- **Rebuild the image before any integration run.** `uv run invoke dev.build`. A run against a stale
  image returns the old numbers and reads as "the change did nothing".
- **Start run counters after the branch edits.** Editing peers on a branch is live work that fans
  out per node by design. Counting from before charges those runs to the merge; that alone turned 2
  into 42 in one measurement.
- **One component package per pytest session.** Three in one session times out fixtures. ERRORs in
  the last package of a long run are the environment, not the code.
- **Sweep stacks before and after.** An orphan holds the ports and the next run fails in 13 s with
  every app container stuck in `Created`.
- **Never `git add <directory>`.** The tree carries untracked work in progress from other branches;
  a directory add commits it. This happened three times.
- Integration tests are gated behind `INFRAHUB_PROFILE_TIMING`, `INFRAHUB_PARITY` and
  `INFRAHUB_PYTHON_DISPATCH`, and need `INFRAHUB_TESTING_DOCKER_PULL=false` plus
  `INFRAHUB_TESTING_TASKMGR_BACKGROUND_SVC_REPLICAS=1`.

## Still open, deliberately

- T042, the cross-family chain test. Needs a schema change; design is in `baseline.md`.
- T045, T048, T050, the plain-delete half of US2. Blocked on the mutation timestamp not reaching the
  event. See research R6.
- SC-005, API responsiveness during the drain window. Never verified, marked as such.
- IFC-3015, the critical path.
