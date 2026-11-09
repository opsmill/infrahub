# Critique Report: Selective Recompute of Transform-Based Computed Attributes

**Date**: 2026-07-16
**Lenses**: Product strategy + Engineering risk
**Subjects**: `spec.md`, `plan.md`, `research.md`, `contracts/trigger-and-recompute.md`

## Verdict

**Initial**: 🛑 RETHINK — one CRITICAL under-regeneration hole plus a spec/plan
contradiction and a second under-regeneration path.

**After remediation (one pass)**: ✅ PROCEED — all must-address findings resolved in
the artifacts and verified against the code.

The architecture (three static kind-scoped triggers on the `CoreTransformPython`
lifecycle, reuse of the existing recompute fan-out, `fingerprint` as the change signal)
was sound and well-grounded from the start. The loop-safety correction (no `RECOMPUTE`
mutation origin on `develop`; safety comes from the kind+field match) held up. The
remediation fixed correctness gaps, not the core design.

## Must-address findings and resolutions

### 1. CRITICAL — removing the commit trigger stranded the node-input recompute automations

**Finding**: `computed_attribute_setup_python` (`backend/infrahub/computed_attribute/tasks.py:519-612`)
does two jobs: scoped recompute fan-out (`tasks.py:586-595`) **and** reconciliation of the
data-path automations via `setup_triggers(..., COMPUTED_ATTR_PYTHON)` /
`setup_triggers(..., COMPUTED_ATTR_PYTHON_QUERY)` (`tasks.py:597-612`). Those automations
recompute an attribute when a **node feeding the transform's query** changes — a different
axis from the transform-content change this feature handles. The removed commit trigger ran
that reconciliation on **every** import. The schema trigger only fires on a real schema
diff, so a transform-only import would leave the node-input automations unbuilt →
node-input changes silently fail to recompute → permanently stale values (violates the
non-negotiable invariant). Verified directly in the code.

**Resolution (D1)**: The transform-lifecycle flow now owns that reconciliation: it runs
`setup_triggers` on **every** lifecycle event (create / update / delete), in addition to
recomputing on create/update. This is more precise than the commit sweep (fires only on
transform events). Encoded in FR-006, FR-011, spec Overview, research Decision 5, contract
§3.5, plan Removal-impact. New test SC-010 (node-input change after a transform-only import
recomputes).

### 2. MAJOR — transform→attributes resolution could silently return empty (2nd under-regen path)

**Finding**: a computed attribute may wire its transform by **name or UUID**
(`core/schema/computed_attribute.py:12`); `python_attributes_by_transform` is keyed by that
raw value (`core/schema/schema_branch_computed/python_transform.py:96-99`). The event
carries the transform id; a name-only lookup returns `[]` for a UUID-configured attribute →
no recompute.

**Resolution (D2)**: resolve by **both** name and id; empty-when-recompute-might-be-needed
defaults to recompute (log loudly). Encoded in FR-010, contract §3, research Decision 2b,
new unit test and SC-011.

### 3. MAJOR — spec/plan contradiction on the delete trigger

**Finding**: FR-005 mandated tearing down "per-attribute recompute automation(s)"; the plan
made delete a no-op (static triggers have no per-transform automation).

**Resolution (D3)**: delete is now a real operation — it reconciles away the deleted
transform's node-input automation (the D1 `setup_triggers` run on the delete event drops it
via the `to_delete = existing - desired` diff). FR-005, User Story 5, SC-007 reworded to
behavior-based criteria.

## Recommendations applied

- **D4**: fan-out flow requires `context: EventContext`; the contract example now threads it
  into `parameters` (`tasks.py:221-226`).
- **D6**: first import must write each transform exactly once (create XOR update) →
  exactly one recompute (FR-015, SC-012, open item to confirm the importer branch).
- **D7**: empty-resolution path returns before any node fetch (contract §3).
- **D8**: schema-path / lifecycle-path recompute overlap is idempotent and accepted; the
  schema path is not narrowed here (research Decision 8).

## Risks carried into planning

- **R5 (D5)**: the import write builds an `AnonymousSession` context; the recompute write
  passes a permission gate. Verify the node-event context on the import write carries a
  sufficient account id; integration test asserts recompute actually happens on import.
- **Partial-fan-out recovery**: if the lifecycle flow submits some attributes then crashes,
  the rest only re-cover on the next fingerprint change of that transform. Consider whether
  a periodic reconcile safety net is warranted (noted, not required for this feature).
- **Old commit-trigger automation on upgrade**: confirm the upgrade reconcile
  (`trigger_configure_all`, force update) deletes the retired
  `builtin::computed-attribute-python-setup-on-commit` automation.
