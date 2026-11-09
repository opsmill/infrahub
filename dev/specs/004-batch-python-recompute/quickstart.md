# Quickstart Validation: Batch Python Computed-Attribute Recompute

## Prerequisites

- `uv sync --all-groups`; Docker running (component/functional tiers use testcontainers — export the Docker socket if needed).

## Fast signal (unit, seconds)

```bash
uv run pytest backend/tests/unit/computed_attribute/ -q
```

Expected: partition/skip logic green — string persisted; None/non-str skipped with reason; exception isolated; empty batch no-op.

## Behavior (functional, minutes)

```bash
uv run pytest backend/tests/functional/computed_attributes/ -q
```

Expected: end-to-end with a real git repo + transform — values recompute on source change; unchanged recompute emits no follow-on work; one failing node leaves siblings updated.

## Live smoke (dev stack)

1. `uv run invoke dev.build dev.start`
2. Load a schema with a TransformPython computed attribute + repository (tshirt fixture), create a few readers.
3. Update the source attribute; verify: readers' values refresh; task list filtered by branch shows the `computed_attribute_process_transform` run; re-updating with the same value produces no new recompute wave.

## At-scale A/B (perf, hours — optional)

opsmill/infrahub-private-tests `test-dataset.yml` with `test_filter=TestMergeRecomputePython`, same backup/profile, `infrahub_ref` = baseline vs feature ref. Compare: post-merge settle window, flow-run counts (query/process), db_queries, correctness (recomputed == affected).
