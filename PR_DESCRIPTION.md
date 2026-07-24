# Why

Uniqueness validation scanned the **entire population** of a kind on every data change. Merging, rebasing, or proposing a change that touched a handful of nodes of a large kind still ran a population-wide scan — slow on big kinds (hundreds of thousands of nodes) and it shipped large duplicate result sets back to Python.

**Goal:** scope a data-triggered uniqueness check to only the nodes the diff actually affects, so the work is proportional to the size of the change rather than the size of the kind.

**Non-goals:** this does not change node-save-time uniqueness (`grouped_uniqueness`), does not touch other constraint validators, and does not change the uniqueness error surfaced to users.

**Note:** uniqueness constraints do not support attribute of relationships (e.g. `"device__name"`). some parts of the code support this kind of uniqueness constraint, but not all of it and it is still blocked when creating/updating a schema.

Part of IFC-2796 (epic IFC-2706).

## What changed

**Behavioral**

- Data-triggered uniqueness validation (merge, rebase, proposed-change integrity) now validates **only the changed/affected nodes** via a batched, index-anchored targeted query instead of a full-population scan.
- A uniqueness check is scoped to exactly the nodes whose changed field participates in the constraint — changing one node's unique field no longer drags in every other changed node of the kind.
- A **newly added or broadened** constraint (schema-diff origin, with no affected-node set) still runs the full-population scan, as before.
- Cross-kind constraints that read a peer's attribute (e.g. `owner__name`) fall back to full-population validation, which supports them; the targeted query does not. **Again, this type of uniqueness constraint cannot be added to schemas currently.**
- Uniqueness **error messages are unchanged** — attribute values render identically to the full-population path regardless of their type.

**Implementation notes**

- A `node_uuids` carrier is threaded end to end: `None` means full scan, a list means validate exactly those nodes. It rides from the diff summary through the determiner, the constraint info, and the validator request into the checker.
- `NodeDiffFieldSummary`/`NodeDiffIndex` now keep the correlation between each changed field and the nodes that changed it (per-field UUID maps), so scoping targets a specific field's nodes rather than every changed node of the kind.
- New here (constructor-injected, wired by `build_constraint_validator_determiner`): `UniquenessConstraintScoper` decides, per kind, whether uniqueness must run and which nodes it affects (`None` → full scan); the `ConstraintValidatorDeterminer` update threads the affected set through; constraint dedup/merge helpers collapse a node's uniqueness check into its generic's where the generic already covers it.
- `UniquenessChecker` now runs the targeted query for a scoped set, and falls back to the full-population scan when a constraint reads a peer attribute.

**What stayed the same**

- The full-population path and the node-save-time uniqueness checker (`grouped_uniqueness`) are untouched.
- No GraphQL/API contract changes, no database schema or migration changes.

### Suggested review order

1. `core/diff/model/path.py`, `core/diff/query/field_summary.py`, `core/validators/node_diff_index.py` — how per-field changed-node UUIDs are captured.
2. `core/validators/uniqueness/scope.py` + `core/validators/determiner.py` — how the affected-node set (or `None`) is decided.
3. `core/validators/uniqueness/checker.py` — running the targeted query for a scoped set vs the full-population fallback.
4. `proposed_change/tasks.py`, `merge/constraints.py`, `branch/tasks.py` — the three call sites that thread the affected set through.
5. Tests.

## How to review

Focus on the scope decision (`UniquenessConstraintScoper._compute_scope`) and the checker's targeted-vs-full-population branch (`UniquenessChecker.check` / `_supports_targeted`) — those govern correctness. Mechanical: the `attribute_node_uuids` conversions across the test files.

## How to test

```bash
# unit + node-scoped component suites (need a running database)
uv run pytest backend/tests/unit/core/validators
uv run pytest backend/tests/component/core/constraint_validators
uv run pytest backend/tests/component/core/diff/repository/test_diff_repository.py::TestDiffRepositorySaveAndLoad::test_get_node_field_summaries
uv run pytest "backend/tests/component/message_bus/operations/requests/test_proposed_change.py::test_get_proposed_change_schema_integrity_constraints"

# end-to-end schema-validator uniqueness (rebase/merge path)
uv run pytest "backend/tests/integration/schema_lifecycle/test_schema_validator_generic_uniqueness.py::TestSchemaLifecycleValidatorMain"
```

## Impact & rollout

- **Backward compatibility:** no breaking changes; uniqueness error messages are identical to before.
- **Performance:** the headline win. On a large local dataset (≈500k-node kind) the full-population scan ran 8+ minutes before OOM-killing Neo4j; the targeted query validates ~9,400 changed nodes of that kind in ~12s and ~23,500 in ~29s, and all implicated kinds complete in tens of seconds. Work is now bounded by the change, not the population.
- **Config/env changes:** none.
- **Deployment notes:** safe to deploy; no coordinated release or migration required.

## Checklist

- [x] Tests added/updated
- [x] Changelog entry added
- [ ] External docs updated (no user-facing surface change)
- [x] Internal .md docs updated (internal knowledge and AI code tools knowledge)
- [x] I have reviewed AI generated content
