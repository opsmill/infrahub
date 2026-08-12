# Quickstart: validating the coalesced Python recompute

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

How to prove the feature works. Read [contracts/python-target-resolution.md](./contracts/python-target-resolution.md) for the failure semantics being checked and [data-model.md](./data-model.md) for the pipeline shape.

## Prerequisites

```bash
uv sync --all-groups
git submodule update --init --recursive     # a fresh worktree needs this
```

Component and integration tests run their own services through testcontainers. Unset the development-shell `INFRAHUB_*` variables first, or the tests reach an external database and the client login fails:

```bash
env | grep '^INFRAHUB_'      # expect no output before running the tiered tests below
```

Build the local image once before anything in `integration_docker`:

```bash
INFRAHUB_IMAGE_VER=local-dev INFRAHUB_TESTING_IMAGE_VER=local-dev uv run invoke dev.build
```

## Tier 1 — pure logic, seconds

Covers the owner-axis derivation, the chain-depth bound, the resolver's failure table, and the schema-coverage function.

```bash
uv run pytest backend/tests/unit/core/merge/ backend/tests/unit/computed_attribute/ -q
```

Expect: the builder emits Python owner-axis targets for a kind that owns a Python computed attribute, and none for a kind that does not, including a self-target on update where the other three families correctly emit none. The depth bound rises when the schema carries only Python computed attributes, where today it returns the floor. Each row of the resolver's failure table produces the stated outcome, in particular that "looked, found none" drops the target while "could not look" widens it, and that a widened target produces exactly one submission rather than zero.

## Tier 2 — with a database, a minute or two

Covers the deleted-peer refresh and the end-to-end submission shape.

```bash
uv run pytest backend/tests/component/merge_recompute_coalescing/ -q
```

Expect: a merge that deletes a node read by a Python transform refreshes that node's readers. This test fails before the phase 3 change, for two separate reasons, and that is the point of writing it first.

## Tier 3 — full stack, minutes

Two things run here. The first is the existing suppression test, extended with the Python deployments:

```bash
INFRAHUB_TESTING_TASKMGR_SCALEOUT=1 INFRAHUB_TESTING_IMAGE_VER=local-dev \
  uv run --no-sync pytest backend/tests/integration_docker/test_merge_recompute.py -q
```

Expect: across a merge of about twenty nodes, **counting Prefect flow runs**, no run of either Python flow carries a single object id, and the run count per affected pair follows the chunk limit rather than the node count. A value-only assertion is not enough here: this is the only tier that can observe whether the origin filter actually suppresses the automations, and the component tier cannot, because it records what the coordinator submits rather than what Prefect matches.

Then set the switch off and re-run: today's per-node behaviour must return exactly.

The second is the new cross-family chain test:

```bash
INFRAHUB_TESTING_TASKMGR_SCALEOUT=1 INFRAHUB_TESTING_IMAGE_VER=local-dev \
  uv run --no-sync pytest backend/tests/integration_docker/test_merge_recompute.py -k chain -q
```

Expect: a template-derived value feeding a Python-derived value settles correctly, and so does the reverse. This is the test that catches the trap in this feature: adding the origin filter without teaching the coalesced pass about Python leaves these values stale, and only the full stack exercises the real trigger matching.

If a full-stack test fails, attach a debugger rather than re-running the suite. A failure freezes the stack, the clients and the fixtures in place:

```bash
uv run pytest -c ... <node_id> -s --pdb
```

## Tier 4 — the numbers

This is phase 0 of the plan and phase 6 again, because SC-002 is a ratio and needs both ends.

The timing harness is **not in this repository**. Restore it first:

```bash
git checkout origin/merge-recompute-profile-ifc-2761 -- \
  backend/tests/integration_docker/test_merge_recompute_timing.py \
  backend/tests/helpers/merge_recompute/metrics.py \
  backend/tests/helpers/merge_recompute/scales.py
```

Then fix the import drift against the current dataset helper, add the three Python deployment names to the counted set, add a Python-transform dataset variant, and add a 2000-node scale. The dataset variant is the only genuinely new piece: a Python computed attribute needs a real transform repository, not just a schema load. Reuse the existing schema fixture with a transform-python computed attribute and the existing fixture repository rather than writing new ones.

Record the baseline **before** any production change lands:

```bash
INFRAHUB_PROFILE_TIMING=1 INFRAHUB_TESTING_IMAGE_VER=local-dev INFRAHUB_PROFILE_SCALE=1000 \
  uv run --no-sync pytest backend/tests/integration_docker/test_merge_recompute_timing.py -q -s
```

Repeat at 100 and 2000. Then repeat all three after the change.

| Criterion | What to compare |
|---|---|
| SC-001 | Background job count at 100, 1000 and 2000. After the change it follows the chunk limit per pair; before, it is one per changed node. |
| SC-002 | Trailing window at 1000. At least 90% shorter than the baseline. |
| SC-003 | The set of written nodes and their values, identical between the two runs at every scale. |
| SC-004 | **Transform execution count**, no higher than the baseline at every scale. This is the one that catches a design that trades jobs for work. |
| SC-005 | Poll the API through the window. No error, no timeout. |
| SC-007 | The fail criterion. If executions exceed the baseline, or the window improves by less than 50%, revert the suppression rather than shipping. |

Report the **ratio**, never absolute seconds. Absolute numbers are container-relative and do not transfer between machines.

Two weaknesses in the harness as it stands, both worth fixing while restoring it: the window loop polls every two seconds and conflates "the count rose" with "the queue drained", and the total-duration figure is assigned the window value rather than a sum of run durations.

## Before pushing

```bash
uv run invoke format
uv run invoke lint
uv run ruff format --check backend/
```

`ruff check` passing does not mean the formatting is clean. The lint job runs both and gates everything downstream.

Add a changelog fragment. This is a user-facing performance change, so it needs one:

```bash
# changelog/+ifc3002.fixed.md
```

## What "done" looks like

- Tiers 1 to 3 green.
- Tier 4 shows a chunk-bounded job count, at least a 90% shorter window at 1000 nodes, and **no increase in transform executions**, all against a baseline measured with the same harness.
- The written-node sets match between the old and new paths at every scale.
- The deleted-peer tests pass, having failed before the change, for both a merged delete and a direct one.
- Turning the switch off restores today's behaviour exactly.
- `dev/knowledge/backend/merge-recompute.md` and `dev/knowledge/backend/computed-attributes.md` updated: both currently state that Python transforms are outside the coalesced pass, and the first also documents that the build step needs no database.
