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
(`events/constants.py` has only LIVE/MERGE/REBASE). Loop safety (FR-011) is provided by
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
├── tasks.py             # ADD process_transform_lifecycle flow: resolve transform ->
│                        #   attributes, submit TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
│                        #   per PythonDefinition. Reuse existing trigger_update_python_*.
├── recompute_resolution.py   # NEW small pure component: (branch, transform name) ->
│                             #   list[PythonDefinition] via python_attributes_by_transform.
│                             #   (Or inline in tasks.py if trivial; keep it unit-testable.)
└── gather.py, models.py, scoping.py   # UNCHANGED (data-path + schema-path stay as-is)

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
*which* attributes to recompute is replaced. A new pure resolver keeps the decision
unit-testable without a stack, per `backend-component-design`.

## Phase 0: Research (see research.md)

Resolved decisions, each grounded in file:line evidence:

1. **Static kind-scoped triggers over per-transform gathered automations.** Gathered
   per-transform triggers would need a setup flow to react to the very lifecycle events we
   already react to (circular). Static triggers resolve transform->attributes at task time
   from live schema; nothing per-transform to create or delete.
2. **Reuse `trigger_update_python_computed_attributes` for fan-out; add a new lifecycle
   flow rather than parameterize `computed_attribute_setup_python`** (which also reconciles
   automations and must stay on the schema path).
3. **origin=LIVE excludes merge/rebase (FR-010); kind+field excludes the recompute loop
   (FR-011).** Correcting the epic: there is no RECOMPUTE origin.
4. **Create trigger does the first computation; update trigger does selective recompute;
   delete trigger is a no-op under the static model** (no per-transform automation exists).
5. **Null-fingerprint self-heal is automatic** - a null->value write is an ordinary
   attribute change the update trigger matches; no null-specific code.

## Phase 1: Design & Contracts (see data-model.md, contracts/)

- **data-model.md**: no DB schema; describes the event data shapes (`get_resource`,
  `get_related`), the in-memory `PythonDefinition` / `python_attributes_by_transform`
  resolution, the three trigger definitions, and workflow parameter shapes.
- **contracts/trigger-and-recompute.md**: the exact `match` / `match_related` dicts per
  lifecycle, the payload fields consumed, the transform->attributes resolution, the
  fan-out to `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES`, and a table contrasting the new
  path with the removed commit path.

### Removal impact (FR-009), grep-confirmed

- `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` is referenced only in
  `computed_attribute/triggers.py` (definition) and `trigger/catalogue.py:19`
  (registration). No test references it. Removing both leaves no dangling import.
- `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`triggers.py:29`, `SchemaUpdatedEvent` +
  `BranchDeletedEvent`) is independent and stays. It still drives
  `computed_attribute_setup_python` with `changed_elements` forwarded, so schema-scoped
  Python recompute keeps working.
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
  `list[PythonDefinition]` is exactly the tied attributes and nothing else. No stack.
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
- **US5 delete -> no further recompute**: import (attribute populated); delete the
  transform; import; assert subsequent commits produce zero recompute for that attribute
  and no lifecycle recompute fires (resolution yields `[]`).
- **US6 null-fingerprint first import -> exactly one recompute**: start from a transform
  with null fingerprint (pre-feature state); import once; assert fingerprint stamped and
  one recompute; import again (no change) -> zero further recompute.
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
- **R3 - Delete-trigger scope.** Under the static model the delete trigger removes nothing
  per-transform. If a reviewer expects a per-transform automation to be enumerated and
  deleted (the epic's "per-attribute automation" wording), that expectation is met
  vacuously (none exists). Documented in research Decision 5; the US5 test proves absence
  of further recompute rather than absence of a specific automation.
- **R4 - Resolution keyed by name while event carries id.** The workflow must resolve id
  -> name before the `python_attributes_by_transform` lookup. A stale schema branch could
  in theory resolve to `[]` and under-regenerate; mitigated because
  `trigger_update_python_computed_attributes` and `process_transform` already resolve
  transforms against the same live schema, and the fan-out re-reads nodes at run time.
