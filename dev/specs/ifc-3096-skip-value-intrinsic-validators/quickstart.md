# Quickstart: validating IFC-3096

**Feature**: Stop emitting value-intrinsic constraint validators on data-only diffs

This is the validation guide — how to prove the feature works. Implementation detail lives in `tasks.md`.

## Prerequisites

```bash
uv sync --all-groups
```

The determiner component tests need a database. Use the running dev stack rather than testcontainers where one is already up:

```bash
export INFRAHUB_USE_TEST_CONTAINERS=false   # reuse an already-running database
```

Otherwise leave the default and ensure the Docker daemon is running.

## 1. Pin the classification (FR-004, FR-006)

The cheapest check, and the one that fails first if a checker's declaration is wrong.

```bash
uv run pytest backend/tests/unit/core/validators/test_constraint_classification.py -v
```

**Expected**: passes. The expected mapping covers all 29 identifiers in `CONSTRAINT_VALIDATOR_MAP` — 14 declared `False` by this feature, 2 already `False`, 13 remaining `True`.

**Prove it actually pins.** Temporarily add a bogus entry to `CONSTRAINT_VALIDATOR_MAP` and re-run:

```bash
uv run pytest backend/tests/unit/core/validators/test_constraint_classification.py -v
```

**Expected**: fails, naming the unclassified identifier. Revert the bogus entry. A test that does not fail here does not satisfy FR-004.

## 2. Narrowed set on a data-only diff (FR-001, FR-003)

```bash
uv run pytest backend/tests/component/core/constraint_validators/test_determiner.py -v
```

**Expected**: all pass, including the new data-only-diff test. For a diff touching only instance data:

- **Zero** constraints from the 14 value-intrinsic identifiers.
- **Every** cross-node constraint still present — attribute uniqueness, node uniqueness constraints, hierarchy parent/children, relationship cardinality/min_count/max_count/optional, common parent.
- The **count** assertion holds: total scheduled constraints fall by `2A + R + P` for a diff with A attribute pairs, R relationship pairs and P set optional attribute parameters (SC-002).

Six existing sites in this file shrink their expected sets (see `research.md` R5). If any still expect `attribute.kind.update`, `attribute.optional.update`, `relationship.peer.update`, or `attribute.parameters.max_length.update` from a data-only diff, the update is incomplete.

## 3. A real schema change still scans the full population (FR-002)

The safety property. This is the one that must not regress.

```bash
uv run pytest backend/tests/component/core/constraint_validators/test_schema_diff_constraints.py -v
uv run pytest backend/tests/component/core/test_branch_rebase.py -v -k "constraint"
```

**Expected**: on a branch that changes an attribute's kind *and* edits instance data for that kind, the kind constraint is present at unrestricted scope (`node_uuids is None`), contributed by the schema-diff producer and surviving the merge of the two producers' outputs.

**This must not be tested in `test_determiner.py`.** That file exercises `ConstraintValidatorDeterminer.get_constraints` — the *data-diff* producer — which after this change contributes nothing for these constraints. A test placed there would pass while FR-002 was entirely broken. The schema-diff producer is `MergeSchemaAnalyzer.calculate_validations`, composed by `ConstraintInfoMerger.merge`.

**What a false pass looks like**: the constraint present but scoped to the changed nodes only. That would mean the data-diff producer supplied it, not the schema-diff producer — the opposite of what FR-002 requires. Assert the scope, not just presence.

## 4. No regression across the constraint suite (SC-003)

```bash
uv run pytest backend/tests/component/core/constraint_validators/ -v
uv run pytest backend/tests/unit/core/validators/ -v
```

**Expected**: green. Every per-checker test invokes its checker directly with an explicit constraint request, so none should need changing — if one fails, a `check`/`supports` behaviour was altered, which is out of scope for this feature.

Then the broader merge and proposed-change paths:

```bash
uv run pytest backend/tests/unit/core/migrations/ backend/tests/component/core/migrations/ -v
```

## 5. Measure the wall-clock (SC-004)

Reported in the PR description, not gated — no baseline exists to gate against.

Against a dev stack with a populated database, time a rebase of a data-only branch before and after the change:

```bash
# with the branch checked out at its pre-change commit, then at HEAD
time <rebase invocation against the dev stack>
```

Record both numbers and the approximate node population in the PR description. Also record the scheduled-constraint counts, which are the gated part (SC-001, SC-002): for a data-only diff touching K (kind, field) pairs, total scheduled constraints should fall by roughly 3K — the attribute-kind, attribute-optionality and relationship-peer triple previously emitted for every pair.

## 6. Pre-CI

```bash
uv run invoke format
uv run invoke lint
```

Then the full local CI gate before pushing:

```bash
/pre-ci
```

Note the repo caveat: `invoke lint` runs ruff over a subset of paths while CI runs `ruff check . --exclude python_sdk` repo-wide. `/pre-ci` covers the whole-repo check.

## Definition of done

| # | Check | Requirement |
|---|---|---|
| 1 | Classification pinning test passes, and demonstrably fails on an unclassified new entry | FR-004, FR-006 |
| 2 | Data-only diff schedules zero value-intrinsic constraints, all cross-node ones, and the `2A + R + P` count assertion holds | FR-001, FR-003, SC-001, SC-002 |
| 3 | Genuine schema change still schedules at unrestricted scope **from the schema-diff producer**, verified outside `test_determiner.py`, plus one end-to-end case | FR-002 |
| 4 | Constraint, migration and validator suites green with no unexpected changes | SC-003 |
| 5 | `dev/knowledge/backend/constraint-validation.md` exists, naming a confirmed write-time enforcement site per value-intrinsic family, and covering the profile/template asymmetry and the per-checker classification limit | FR-005 |
| 6 | DEBUG log added at both determiner classification skip sites | Observability |
| 7 | `housekeeping` changelog fragment added | Governance |
| 8 | Before/after wall-clock with node population recorded in the knowledge page **and** the PR description | SC-004 |
| 9 | Rollback trigger stated in the spec | Operational |
