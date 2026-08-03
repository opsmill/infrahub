# Quickstart: Validating Selective Recompute of Transform-Based Computed Attributes

End-to-end validation guide. Trigger match shapes live in
`contracts/trigger-and-recompute.md`; data shapes in `data-model.md`. This file is
run/validation scenarios only. All integration steps use testcontainers - no external or
local Neo4j, no mocks (`.agents/rules/testing-python.md`).

## Prerequisites

```bash
uv sync --all-groups
```

Fixtures: reuse the `car-dealership` repo fixture
(`backend/tests/fixtures/repos/car-dealership/`), which already contains GraphQL queries,
a Python transform, and computed attributes, plus `FileRepo`
(`backend/tests/helpers/file_repo.py`) for multi-commit re-import. Model the new tests on
`backend/tests/integration/git/fingerprint_base.py` and
`test_fingerprint_transformation.py`. Run integration tests with testcontainers:

```bash
INFRAHUB_USE_TEST_CONTAINERS=1 uv run pytest backend/tests/integration/git/test_selective_recompute.py --neo4j
```

Unset any dev-shell `INFRAHUB_*` vars first (esp. `INFRAHUB_USE_TEST_CONTAINERS=false`
and creds) so the suite does not hit an external Neo4j.

## Step 0 - Confirm no generated files change

This feature adds no schema attribute, enum, GraphQL, or REST surface. Nothing to
regenerate. Sanity check that the generated-doc validation stays green:

```bash
uv run invoke docs.validate     # must pass, unchanged
```

Expected: no diff in `backend/infrahub/core/schema/generated/`,
`backend/infrahub/core/protocols.py`, `schema/schema.graphql`, `schema/openapi.json`, or
frontend generated types.

## Step 1 - Unit: transform -> attributes resolution (pure, no stack)

```bash
uv run pytest backend/tests/unit/computed_attribute/test_recompute_resolution.py
```

Assert, against a constructed schema branch:

- A transform feeding exactly one attribute resolves to that one `PythonDefinition`.
- A transform feeding several attributes resolves to all of them, none extra (US2 sc.4).
- A transform feeding no attribute resolves to `[]` (edge case: inert transform).
- A transform not present in `python_attributes_by_transform` resolves to `[]`
  (US5 safety: deleted/renamed transform).

## Step 2 - Unit: trigger shapes

```bash
uv run pytest backend/tests/unit/computed_attribute/test_triggers.py
```

Assert:

- Three `BuiltinTriggerDefinition`s exist for create / update / delete on
  `CoreTransformPython`.
- Update trigger: `match["infrahub.node.kind"] == "CoreTransformPython"`,
  `match["infrahub.node.origin"] == "live"`,
  `match_related["infrahub.field.name"] == ["fingerprint"]`,
  `match_related["prefect.resource.role"] == ["infrahub.node.attribute_update"]`.
- Create trigger: kind + origin=live, no `field.name` filter.
- `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` no longer exists and is not in
  `builtin_triggers`; `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` still is.

## Step 3 - US1: unrelated commit -> zero recompute

1. Create + import the `car-dealership` repo (attribute populated, fingerprint stored).
2. Record the target node's computed attribute value.
3. Commit an edit to a file outside the transform's dependency closure (e.g. a README or
   an unrelated helper); re-import.
4. Assert the transform's `fingerprint` is unchanged, no fingerprint-update event fired,
   and the computed attribute value is unchanged (no fan-out submitted). (SC-001)

## Step 4 - US2: transform change -> only its attributes

1. Two transforms A and B feeding two different computed attributes, both imported.
2. Edit an input of A (its `.py`, its connected query, or a closure file); re-import.
3. Assert A's fingerprint changed, an update event fired, and A's attribute recomputed for
   **every** node of its kind. Assert B's attribute was **not** recomputed. (SC-002, SC-003)

## Step 5 - US3: edit-then-revert -> no recompute on revert

1. Import (fingerprint stored). Edit A's content; re-import (fingerprint changes, one
   recompute).
2. Revert A to byte-identical original content; re-import.
3. Assert the fingerprint returns to its original value and the revert import produces no
   recompute for A's attribute. (SC-004)

## Step 6 - US4: no-watch -> per-commit but scoped

1. Transform A with no `watch` declaration + transform B with `watch` declared, feeding
   two attributes.
2. Commit an unrelated change; re-import.
3. Assert A's fingerprint changed (commit id folded in) and A's attribute recomputed;
   assert B's attribute was not recomputed. (SC-009)

## Step 7 - US5: delete -> no further recompute

1. Import a transform feeding an attribute (attribute populated).
2. Remove the transform from the repo (or delete the node); import the deletion.
3. Assert subsequent commits produce zero recompute for the attribute the deleted
   transform fed, and the lifecycle resolution yields `[]` for it. (SC-007)

## Step 8 - US6: null-fingerprint first import -> exactly one recompute

1. Start from a transform with a **null** fingerprint (pre-feature state): create the
   transform node without a fingerprint, or clear it, then attach a computed attribute.
2. Import the repository once. Assert the fingerprint is stamped (null -> value), an update
   (or create) event fired, and the attribute recomputed **exactly once**.
3. Import again with no content change (watch-declared). Assert the fingerprint is
   unchanged and **no** further recompute. (SC-008)

## Step 9 - Origin / merge-rebase no-double-fire

1. On a branch, create/import the transform + attribute so a fingerprint is stored.
2. Merge the branch into main (and, separately, rebase a branch). The fingerprint change
   replays with `origin == merge` / `rebase`.
3. Assert the coalesced merge/rebase recompute path handles the recompute and the
   lifecycle **update** trigger does **not** fire a second time (no double recompute).
4. Assert a recompute write (which targets the attribute's own node kind, not
   `CoreTransformPython`) does not re-fire the lifecycle trigger (no loop). (SC-006)

## Observing recompute without mocks

To assert "recompute happened / did not happen", prefer one of:

- **Value assertion**: read the target node's computed attribute before and after; a
  recompute changes it when the transform output changed, and leaves it when it did not.
- **Workflow recorder**: inject the test workflow adapter and assert on the set of
  submitted `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` /
  `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM` submissions (kind + attribute name), the same
  way the message bus is asserted via `BusRecorder`. No `unittest.mock`.

## Test placement

- Unit (`backend/tests/unit/computed_attribute/`): resolution and trigger shapes.
- Integration (`backend/tests/integration/git/test_selective_recompute.py`): US3/US4/US6
  and the import-to-event linkage, over the `car-dealership` fixture with testcontainers.
  (The fingerprint-driven recompute scoping for US1/US2/US5 is covered by the component
  suite `backend/tests/component/computed_attribute/test_transform_lifecycle_recompute.py`.)

Per repo convention, no Jira/spec/FR IDs appear in test names, docstrings, or source
comments - those belong in the commit message, PR description, and changelog fragment.
