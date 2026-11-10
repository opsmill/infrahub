# Implementation Plan: Selective Recompute of Transform-Based Computed Attributes

**Branch**: `selective-recompute-ifc-2804` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/ifc-2804-selective-recompute/spec.md`

## Summary

Today a commit to any linked repository recomputes **every** Python transform-based
computed attribute for **every** node of its kind, because the commit event carries no
diff and the scoper falls back to full recompute (`scoping.py:132`,
`computed_attribute_setup_python` at `tasks.py:519`). This feature replaces the
commit-driven trigger with **three static kind-scoped triggers on the transform node's
own lifecycle** (created / updated / deleted), using the IFC-2844 `fingerprint` attribute
as the change signal. When a transform's `fingerprint` changes, the fired workflow
resolves the transform to the computed attribute(s) it feeds via
`python_attributes_by_transform` (`facade.py:56`) and recomputes **only** those
attributes across all nodes of each attribute's kind, by reusing the existing
`TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` fan-out (`tasks.py:221`).

The narrowing is from "every transform's attributes on every commit" to "only the changed
transform's attributes, only when its fingerprint changes". The per-node compute is
untouched. No database schema is added (fingerprint already exists). The governing
invariant is inherited: **over-regenerate, never under-regenerate** - null fingerprints,
no-watch transforms, and any indeterminate state all lead to recompute.

The lifecycle flow has a **second, non-negotiable duty**. Besides the recompute fan-out,
it must reconcile the **data-path (node-input) automations** -
`ComputedAttrPythonTriggerDefinition` / `ComputedAttrPythonQueryTriggerDefinition`
(`computed_attribute/models.py:213,277`) - that recompute an attribute when a node feeding
the transform's query changes. Today `computed_attribute_setup_python`
(`tasks.py:519-612`) does this reconciliation as a side effect on every commit via
`setup_triggers(..., TriggerType.COMPUTED_ATTR_PYTHON)` and
`setup_triggers(..., TriggerType.COMPUTED_ATTR_PYTHON_QUERY)` (`tasks.py:597-612`, using
`gather_trigger_computed_attribute_python` at `tasks.py:538`). The schema trigger
(`TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`) fires only on a real schema diff, so it does
**not** cover a transform-only import. If the commit trigger is removed without moving this
reconciliation, a transform-only import leaves the data-path automations unbuilt and a
later node-input change silently fails to recompute -> permanently stale values, a direct
violation of the invariant. So the new lifecycle flow runs the same two `setup_triggers`
calls on **every** create / update / delete event. This is more precise than the old
commit sweep (it runs on transform events only, not on every commit). The schema path is
unchanged and still reconciles + scoped-recomputes on schema change.

## Technical Context

**Language/Version**: Python 3.14 (backend only). No SDK change; no frontend change.

**Primary Dependencies**: Prefect (automations + workflows), `infrahub_sdk` (the fan-out
reads nodes via `get_client().all(...)`), Pydantic 2.12. No new dependency.

**Storage**: Neo4j graph. This feature adds no attribute, no migration. It only changes
which Prefect automations exist and which workflow they fire.

**Testing**: pytest. Unit tests for the pure transform->attributes resolution (no stack).
Integration tests via testcontainers over the `car-dealership` fixture, mirroring
`backend/tests/integration/git/test_fingerprint_*.py` and `fingerprint_base.py`.

**Target Platform**: Linux server (Infrahub backend + task worker).

**Project Type**: Web-application backend monorepo. This change is confined to
`backend/infrahub/computed_attribute/` and `backend/infrahub/trigger/catalogue.py`.

**Performance Goals**: Recompute work scales with the number of *changed* transforms per
import, not with the total attribute count on the branch (SC-003). An unrelated commit
produces zero recompute jobs (SC-001).

**Constraints**: Live-edit-only (origin=LIVE excludes merge/rebase replays); no recompute
loop (kind+field match excludes the recompute write); no under-regeneration on null or
no-watch. The removed commit trigger must not orphan the schema path or the merge/rebase
path.

**Scale/Scope**: Remove one builtin trigger; add three builtin triggers; add one Prefect
flow plus its catalogue entry; add one small pure resolver component; unit + integration
tests; one changelog fragment. No generated files.

## Constitution / Guideline Check

Evaluated against `.agents/rules/backend-component-design.md`,
`.agents/rules/testing-python.md`, `.agents/rules/code-doc-style.md`, and
`.agents/rules/python-module-layout.md`.

- **Backend component design** - PASS. The new logic is a small resolver
  (transform id/name -> `list[PythonDefinition]`) with a single entry point operating on
  its arguments; its collaborator (the schema branch / client) is injected. The fan-out
  reuses an existing flow rather than reimplementing it. No `isinstance` dispatch. The
  three triggers are declarative data, not behaviour.
- **Testing (no mocks)** - PASS. The resolver is pure (schema-branch lookup) and
  unit-testable without a stack. The trigger match shapes are asserted directly on the
  `EventTrigger` objects (as `test_triggers.py` already does for the schema trigger).
  End-to-end behaviour uses testcontainers with real repos, no `unittest.mock`.
- **Code doc style** - PASS. No Jira/spec IDs in source, docstrings, or test names. The
  triggers module keeps at most a one-line "why" per non-obvious clause (e.g. why
  origin=LIVE).
- **Python module layout** - PASS. Triggers stay in `computed_attribute/triggers.py`;
  the new flow in `computed_attribute/tasks.py`; the resolver in a purpose-named module.
  `constants.py` is not touched with behaviour.

**Result: PASS. No violations; Complexity Tracking is empty.**

One correctness note surfaced during Phase 0 and folded into the design (not a violation):
the epic assumes a `RECOMPUTE` node-mutation origin that does not exist in the code
(`events/constants.py` has only LIVE/MERGE/REBASE). Loop safety (FR-013) is provided by
the kind+field match, not by origin. See research Decision 3.

*Re-check after Phase 1 design: still PASS. The design adds no schema, no migration, no
new dependency, and reuses the existing recompute fan-out unchanged.*

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2804-selective-recompute/
├── plan.md              # This file
├── research.md          # Phase 0: resolved decisions (static vs gathered, flow entry, origin)
├── data-model.md        # Phase 1: in-memory + event data shapes (no DB schema)
├── quickstart.md        # Phase 1: testcontainers end-to-end validation
├── contracts/
│   └── trigger-and-recompute.md   # match shapes, resolution, fan-out
└── tasks.md             # Phase 2 (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/computed_attribute/
├── triggers.py          # REMOVE TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT;
│                        #   ADD three BuiltinTriggerDefinition (create/update/delete)
│                        #   on CoreTransformPython lifecycle. Keep TRIGGER_..._ALL_SCHEMA.
├── tasks.py             # ADD process_transform_lifecycle flow, TWO duties:
│                        #   (1) recompute (create + update-of-fingerprint): resolve
│                        #       transform -> attributes, submit
│                        #       TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES per
│                        #       PythonDefinition (reuse trigger_update_python_*).
│                        #   (2) reconcile data-path automations on EVERY event
│                        #       (create/update/delete): run
│                        #       setup_triggers(COMPUTED_ATTR_PYTHON) and
│                        #       setup_triggers(COMPUTED_ATTR_PYTHON_QUERY) via
│                        #       gather_trigger_computed_attribute_python. Delete relies on
│                        #       setup_triggers' to_delete = existing - desired diff to drop
│                        #       the gone transform's automation. NOT a no-op.
├── recompute_resolution.py   # NEW small pure component: (branch, transform name-or-id) ->
│                             #   list[PythonDefinition] via python_attributes_by_transform.
│                             #   Look up by BOTH name and id (mapping.get(name) or
│                             #   mapping.get(id)); empty -> return before any node fetch.
│                             #   (Or inline in tasks.py if trivial; keep it unit-testable.)
└── gather.py, models.py, scoping.py   # UNCHANGED as modules; gather.py's
                             #   gather_trigger_computed_attribute_python is now ALSO called
                             #   from the lifecycle flow (schema path still calls it too).

backend/infrahub/trigger/catalogue.py   # REMOVE TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT
                                        #   from builtin_triggers; ADD the three new ones.

backend/infrahub/workflows/catalogue.py  # ADD WorkflowDefinition for process_transform_lifecycle;
                                         #   register it in the workflow list. (Code, not generated.)

backend/tests/
├── unit/computed_attribute/
│   ├── test_triggers.py          # EXTEND: assert the three new trigger match/match_related shapes
│   └── test_recompute_resolution.py   # NEW: pure resolution tests (transform -> attributes)
└── integration/computed_attribute/    # NEW: testcontainers end-to-end (mirror fingerprint_base.py)
    └── test_selective_recompute.py

changelog/+ifc-2804.changed.md   # NEW changelog fragment (behaviour change + rollout notes)
```

**Structure Decision**: Backend monorepo. The change is contained in the
`computed_attribute` package and the trigger catalogue. The recompute fan-out
(`trigger_update_python_computed_attributes`) and per-node compute
(`process_transform_for_node`) are reused unchanged; only the entry point that decides
*which* attributes to recompute is replaced. The lifecycle flow also assumes the data-path
reconciliation duty (`setup_triggers` for `COMPUTED_ATTR_PYTHON` /
`COMPUTED_ATTR_PYTHON_QUERY`) that the removed commit trigger did as a side effect, so no
reconciliation is lost. A new pure resolver keeps the recompute decision unit-testable
without a stack, per `backend-component-design`.

## Phase 0: Research (see research.md)

Resolved decisions, each grounded in file:line evidence:

1. **Static kind-scoped triggers over per-transform gathered automations.** Gathered
   per-transform triggers would need a setup flow to react to the very lifecycle events we
   already react to (circular). Static triggers resolve transform->attributes at task time
   from live schema; nothing per-transform to create or delete.
2. **Reuse `trigger_update_python_computed_attributes` for fan-out; add a new lifecycle
   flow rather than parameterize `computed_attribute_setup_python`.** The schema flow keeps
   its `changed_elements` scoping and stays on the schema path. But the lifecycle flow must
   still run the data-path `setup_triggers` reconciliation that the removed commit trigger
   did as a side effect (`tasks.py:597-612`), so a transform-only import does not leave the
   node-input automations unbuilt. See research Decision 5.
3. **origin=LIVE excludes merge/rebase (FR-012); kind+field excludes the recompute loop
   (FR-013).** Correcting the epic: there is no RECOMPUTE origin.
4. **Create trigger does first compute + reconcile; update trigger does selective recompute
   + reconcile; delete trigger reconciles (drops the gone transform's data-path
   automation).** Delete is NOT a no-op: `setup_triggers`' `to_delete = existing - desired`
   diff removes the removed transform's node-input automation (research Decision 5).
5. **Resolve transform -> attributes by name OR id** (FR-010): a computed attribute may
   wire its transform either way; look up by both. Empty resolution returns before any node
   fetch. On an empty lookup where recompute might be needed, default toward recompute.
6. **Null-fingerprint self-heal is automatic** - a null->value write is an ordinary
   attribute change the update trigger matches; no null-specific code.

## Phase 1: Design & Contracts (see data-model.md, contracts/)

- **data-model.md**: no DB schema; describes the event data shapes (`get_resource`,
  `get_related`), the in-memory `PythonDefinition` / `python_attributes_by_transform`
  resolution, the three trigger definitions, and workflow parameter shapes.
- **contracts/trigger-and-recompute.md**: the exact `match` / `match_related` dicts per
  lifecycle, the payload fields consumed, the transform->attributes resolution, the
  fan-out to `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES`, and a table contrasting the new
  path with the removed commit path.

### Removal impact (FR-011), grep-confirmed

- `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` is referenced only in
  `computed_attribute/triggers.py` (definition) and `trigger/catalogue.py:19`
  (registration). No test references it. Removing both leaves no dangling import.
- **Reconciliation is NOT dropped by the removal.** `computed_attribute_setup_python`
  (`tasks.py:519-612`) did two jobs on every commit: the recompute fan-out (`tasks.py:586-595`)
  AND the data-path automation reconciliation via `setup_triggers(..., COMPUTED_ATTR_PYTHON)`
  and `setup_triggers(..., COMPUTED_ATTR_PYTHON_QUERY)` (`tasks.py:597-612`, gathered by
  `gather_trigger_computed_attribute_python` at `tasks.py:538`). Removing the commit trigger
  drops the per-commit recompute sweep, but the lifecycle flow now runs the same two
  `setup_triggers` calls on every create / update / delete. So the node-input automations are
  still reconciled - more precisely, on transform events only, not on every commit. Without
  this move a transform-only import (no schema diff) would leave them unbuilt. See research
  Decision 5.
- `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`triggers.py:29`, `SchemaUpdatedEvent` +
  `BranchDeletedEvent`) is independent and stays. It still drives
  `computed_attribute_setup_python` with `changed_elements` forwarded, so schema-scoped
  Python recompute and its reconciliation keep working on schema change.
- The coalesced merge/rebase recompute (`core/merge/recompute_coalescing`, invoked from
  `post_merge.py`, `branch/tasks.py`) is independent and stays.
- `CommitUpdatedEvent` (`git/integrator.py:399`) is still emitted; only the
  computed-attribute-python subscription to it is removed.

### Generated files

**None.** No schema attribute, enum, GraphQL, or REST change. The new
`WorkflowDefinition` and `BuiltinTriggerDefinition` are hand-authored Python registered in
their catalogues; they are not generated artifacts. `uv run invoke docs.validate` should
stay green with no regeneration. (Confirm no doc references the removed trigger by name in
generated reference docs; the trigger set is not part of the generated reference surface.)

## Testing Strategy

Per `.agents/rules/testing-python.md` (no mocks; adapter/protocol; mirror source path).

### Unit (`backend/tests/unit/computed_attribute/`)

- `test_recompute_resolution.py` (new): the pure resolver. Given a schema branch with a
  transform feeding one, many, and zero attributes, assert the resolved
  `list[PythonDefinition]` is exactly the tied attributes and nothing else. Include a case
  where the computed attribute wires its transform by **UUID** (not name) and assert it
  resolves to the same attribute(s) (SC-011, FR-010): the lookup checks both name and id.
  The zero case returns `[]` before any node fetch (SC-010 cheap empty path). No stack.
- `test_triggers.py` (extend): assert the three new `BuiltinTriggerDefinition` objects
  have the expected `events`, `match` (kind + origin=LIVE), and `match_related`
  (role + `field.name == ["fingerprint"]` on update). Assert
  `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` is gone and not in `builtin_triggers`.

### Integration (`backend/tests/integration/computed_attribute/`, testcontainers)

Mirror `fingerprint_base.py` + `test_fingerprint_transformation.py`. Observe recompute by
asserting the target node's computed attribute value and/or by recording submitted
workflows through the workflow adapter (no mocks).

- **US1 unrelated commit -> no recompute**: import a repo with a watch-declared transform;
  commit a change to an unrelated file; re-import; assert the transform fingerprint is
  unchanged and the attribute value is not recomputed (no fan-out submitted).
- **US2 transform change -> only its attributes**: two transforms A, B feeding two
  attributes; change A's input; re-import; assert A's attribute recomputed for all nodes,
  B untouched.
- **US3 edit-then-revert -> no recompute on revert**: edit A, re-import (one recompute),
  revert to identical bytes, re-import; assert fingerprint returns to original and no
  recompute on the revert import.
- **US4 no-watch -> per-commit but scoped**: no-watch transform A + watch-declared B;
  unrelated commit; assert A recomputed, B not.
- **US5 delete -> no further recompute + data-path teardown**: import (attribute populated,
  node-input automation built); delete the transform; import; assert (a) subsequent node/data
  changes and commits produce zero recompute for that attribute, and (b) the data-path
  (node-input) automation for the removed transform no longer exists after the delete-event
  `setup_triggers` run (SC-007). The delete event is not a no-op.
- **US6 null-fingerprint first import -> exactly one recompute**: start from a transform
  with null fingerprint (pre-feature state); import once; assert fingerprint stamped and
  one recompute; import again (no change) -> zero further recompute.
- **Data-path axis after a transform-only import (the test that would have caught the
  CRITICAL)**: import a NEW transform (no schema diff), then change a NODE that feeds the
  transform's query, and assert the attribute recomputes (SC-010). This proves the lifecycle
  flow built the node-input automation even though the schema path never ran. Without the
  `setup_triggers` reconciliation on the create/update event, this recompute would silently
  never happen.
- **UUID-configured transform resolves correctly (SC-011, FR-010)**: a computed attribute
  wires its transform by UUID (not name); change the transform; assert the attribute
  recomputes exactly as it would for a name-wired attribute.
- **First import produces exactly one recompute per transform (SC-012, FR-015)**: on a
  transform's first import, assert exactly one recompute fires for it - guard against a
  create AND a separate update in the same import double-firing. (Open item: trace the
  importer's create-vs-update branch to confirm a single write per import; if both can
  occur, the flow must dedupe.)
- **Origin / merge-rebase no-double-fire**: create the attribute on a branch, merge (or
  rebase) into main; assert the coalesced path handles recompute and the lifecycle trigger
  does **not** double-fire (fingerprint replay carries MERGE/REBASE origin). Assert a
  recompute write (kind != CoreTransformPython) does not re-fire the trigger.

## Complexity Tracking

> No constitution violations. Section intentionally empty.

## Risks

- **R1 - Import write must actually match the LIVE trigger.** The importer writes the
  transform through the SDK-over-GraphQL path (`git/integrator.py:1772`, `1806`), which
  emits node events with the default `origin=LIVE`. If any future change routes the
  importer's fingerprint write through a non-live origin, the trigger would stop firing and
  the feature would silently under-regenerate. Mitigation: the US6/US2 integration tests
  assert a recompute actually happens on import, catching this.
- **R2 - `fingerprint` in the create changelog.** The create trigger does not filter on
  `field.name`, so it fires on any live create of a transform regardless of whether
  `fingerprint` is in the create changelog. This is intentional (first compute must not
  depend on fingerprint presence) but means a create with an unusual (null) fingerprint
  still triggers one recompute - acceptable over-regeneration, aligned with the invariant.
- **R3 - Delete does real teardown, not a no-op.** The delete trigger runs the data-path
  `setup_triggers` reconciliation; its `to_delete = existing - desired` diff drops the gone
  transform's node-input automation. The risk is the reverse of the old framing: if the
  delete event did NOT run `setup_triggers`, a node-input automation for a removed transform
  would leak and keep firing (or fail). Mitigation: the US5 test asserts the automation is
  gone after the delete import and that no further recompute fires.
- **R4 - Resolution must handle name OR id.** A computed attribute may wire its transform by
  either name or UUID (`core/schema/computed_attribute.py:12`), and
  `python_attributes_by_transform` is keyed by that raw value
  (`core/schema/schema_branch_computed/python_transform.py:96-99`). The event carries the
  transform id. The resolver looks up by both (`mapping.get(name) or mapping.get(id)`). On an
  empty lookup where recompute might be needed, it defaults toward recompute and logs loudly,
  never silently skipping (FR-010, the over-regenerate invariant). The unit test covers the
  UUID-wired case.
- **R5 - Import-context permission for the recompute write.** The import write builds an
  `AnonymousSession` context (`git/integrator.py`), while the recompute write goes through a
  permission gate (`graphql/mutations/computed_attribute.py`). If the node-event context on
  the import write does not carry an account id sufficient for the recompute permission
  check, the fan-out could be rejected and the feature would silently under-regenerate on
  import. Mitigation: verify the import write's context carries a sufficient account id, and
  the US2/US6/data-path integration tests assert recompute actually happens on import.
- **R6 - Create AND update in the same first import (double-fire).** The importer must write
  a transform exactly once per import (create XOR update). If the importer's branch can both
  create a transform and then separately update its fingerprint in one import, the first
  import could fire two recomputes. Open item: trace the importer's create-vs-update branch
  to confirm a single write per import; if both can occur, the lifecycle flow must dedupe.
  The SC-012 test asserts exactly one recompute per transform on first import.
