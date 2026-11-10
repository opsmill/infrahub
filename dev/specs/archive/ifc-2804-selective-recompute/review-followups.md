# Post-MVP code-review follow-ups

Independent review of the MVP (US1 + US2) implementation. Addressed items are folded
into the branch; the rest are deferred with a reason. None is a blocker for the MVP slice.

## Addressed in the MVP branch

- **HIGH — reconcile must survive a failing recompute leg.** The lifecycle flow now runs
  the node-input automation reconciliation in a `finally`, so a failure in the create/update
  recompute leg cannot skip it. A missing transform node (branch race, create-then-delete)
  is tolerated with `raise_when_missing=False`: recompute is skipped and logged, reconcile
  still runs. This protects the over-regenerate-never-under-regenerate invariant.
- **MEDIUM — schema convergence.** The flow calls `wait_for_schema_to_converge` before
  reading the transform -> attribute map, so a worker whose in-memory schema lags does not
  read an empty map and silently skip the first-import recompute.
- **MEDIUM — delete test strengthened.** The delete-path test now removes a transform's
  wiring and asserts its specific node-input automation is dropped while others remain,
  instead of only asserting some automations still exist.
- **Nits** — dropped the redundant `context` entry in the fan-out parameters (the worker
  injects it), and `event_name` is now used in the flow's log line.

## Deferred (follow-up tickets)

- **LOW — concurrent reconcile without a shared lock.** `_reconcile_python_computed_attribute_automations`
  calls the bare `setup_triggers` task, which does not hold the `trigger-rules` distributed
  lock that `setup_triggers_specific` uses. The schema path and the lifecycle path can now
  reconcile the same automation set concurrently. Pre-existing pattern (the removed commit
  trigger already called bare `setup_triggers`), but the lifecycle path increases how often
  reconciles run and adds a second entry point. Route both call sites through the locked
  path in a follow-up.
- **LOW — idempotent double recompute on first import.** On first import the schema-load
  event and the transform-create event can both fan out a recompute for the same attribute.
  Recompute is idempotent (a no-op write when the value is unchanged), so this is wasted
  work, not incorrectness. Decide later whether the schema path should stop covering Python
  transform attributes now that the lifecycle owns them, or accept the overlap.
- **LOW — transform referenced by name then renamed.** If a computed attribute wires its
  transform by name and the transform is later renamed, the map key is the old name while
  the event resolves the new name; resolution would miss on both name and id and skip the
  recompute. Low likelihood (the schema wiring is normally updated in the same import), but
  worth a targeted test if rename-by-name is a supported flow.
