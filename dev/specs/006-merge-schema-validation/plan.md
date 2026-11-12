# Implementation Plan: Validate schema changes against both branches at merge and rebase

**Branch**: `merge-schema-validation` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-merge-schema-validation/spec.md`

## Summary

Merge, proposed-change merge and rebase run the checks of every migration-required schema change made on either
branch since the branch was created. The checks read the data the operation would produce (the merge view) and
compare it with the schema the operation would write. That schema is built by applying the branch's schema diff to
the default branch's current schema. A schema load on a branch keeps reading the branch view. The design follows the
stashed implementation (`migration-validators-wip-2026-11-03`), with two changes from research: the merge gate
compares the in-memory schema hashes instead of the cached branch flag (R4), and the merged schema applies the
branch's diff instead of a generic 3-way merge (R5).

Delivery is two pull requests against `release-1.12`:

1. User stories 1–4 and 6: the checks, the views, the merged schema, the gate, the proposed-change check, and the
   investigation of the two suspected gaps.
2. User story 5: the regex, enum, length and choices queries take the view option.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Pydantic 2.12 (schema models, validation message), Prefect (validation workflow), Neo4j
driver 6.4 (Cypher queries)

**Storage**: Neo4j graph; no change to vertices, edges or indexes

**Testing**: pytest 9 — unit (`backend/tests/unit/`), component with testcontainers (`backend/tests/component/`),
integration with `TestInfrahubApp` (`backend/tests/integration/`), Docker integration with
`TestInfrahubDockerClient` (`backend/tests/integration_docker/`); plus the local merge/rebase matrix on a
`dev.start` stack (see [quickstart.md](quickstart.md))

**Target Platform**: Infrahub server and task workers (Linux containers)

**Project Type**: Web service (backend only; no frontend, GraphQL schema or SDK change)

**Performance Goals**: A merge or rebase where neither branch changed the schema runs no schema check (SC-006). When
the schema changed, the added checks run once per changed property, as a schema load does.

**Constraints**:

- Branch-aware queries with the standard edge ordering (`branch_level DESC, from DESC, status ASC`).
- No database migration, GraphQL change, dependency or CI change (AGENTS.md "Ask first").
- The validation message travels to a Prefect workflow; its new field must serialize.

**Scale/Scope**: About 15 backend modules and their tests; the reference stash changes 26 files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | The feature enforces schema constraints at merge and rebase, where they were skipped. |
| II. Branch-Safe by Default | Pass | Merge behavior is the subject of the feature and is specified and tested per path; new and changed queries use the branch filter and the standard ordering. |
| III. Type Safety & Explicit Contracts | Pass | The view choice is a required, typed field on the validation message; no `Any`, `cast` or new suppression. |
| IV. Test Discipline | Pass with deviation | Unit, component, integration and Docker integration tests (the feature validates schema migrations, and the worker-loaded schema only appears on a distributed stack); no Playwright E2E test (see Complexity Tracking). |
| V. Query Performance & Efficiency | Pass | The new-attribute query is parameterized and returns only the node id and the branch name; the gate keeps checks off merges without schema changes; `EXPLAIN` is run on the new query. |
| VI. Security & Input Boundaries | Not affected | No new input, permission or endpoint. |
| VII. Simplicity & Maintainability | Pass | The merged schema applies the existing schema diff instead of adding a generic merge to the base model (research R5). |

Post-design re-check: unchanged. The design adds one query class, two methods on the schema analyzer, one method on
the schema branch, and one field on the validation message.

## Project Structure

### Documentation (this feature)

```text
specs/006-merge-schema-validation/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Entities and the merged-schema rules
├── quickstart.md        # Local validation matrix
├── contracts/
│   └── refusal-messages.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/merge/
│   ├── schema_analyzer.py        # MergeSchemaAnalyzer: constraints from both sides, merged schema, schema-change gate
│   ├── graph_merger.py           # GraphMerger._validate_constraints: gate and merged schema
│   └── constraints.py            # MergeConstraintValidator.validate: reads the merge view
├── core/branch/tasks.py          # rebase: same gate, merged schema and view as merge
├── core/schema/schema_branch.py  # SchemaBranch: apply a branch's schema diff to this schema
├── core/validators/
│   ├── models/validate_migration.py  # SchemaValidateMigrationData: required view field
│   ├── model.py                      # SchemaConstraintValidatorRequest: view field with the branch view as default
│   ├── tasks.py                      # schema_validate_migrations / schema_path_validate: pass the view
│   ├── shared.py                     # SchemaValidatorQuery: view option
│   ├── attribute/optional.py         # read the requested view
│   ├── attribute/kind.py             # read the requested view
│   ├── node/attribute.py             # new-attribute value query; checker reads the requested view
│   └── attribute/{regex,enum,length,choices}.py   # later pull request
├── proposed_change/tasks.py      # schema integrity check: analyzer's merged schema and constraints, merge view
├── api/schema.py                 # schema load and schema check: branch view, stated explicitly
└── cli/db.py                     # core schema update: branch view, stated explicitly

backend/tests/
├── unit/core/schema/test_schema_branch.py                     # merged schema cases
├── component/core/test_branch_merge.py                        # analyzer constraint list
├── component/core/constraint_validators/                      # each query in both views; new-attribute query
├── component/core/constraint_validators/test_models.py        # message round-trip with the view field
├── integration/schema_lifecycle/test_schema_validator_stored_data.py   # merge/rebase refusals and state after
└── integration_docker/test_schema_merge_validation.py                  # kind change on each side, merge and rebase

docs/docs/branches/
├── merge.mdx    # refusals for schema changes on either side
└── rebase.mdx   # same, with the recovery paths for a mandatory attribute without a default value
```

**Structure Decision**: Backend only, in the existing merge, branch, schema and validator packages. Tests mirror the
source layout and reuse the car/person schema fixtures; the integration module extends the existing stored-data
class.

## Design

### Constraints from both sides (FR-001)

`MergeSchemaAnalyzer.calculate_validations` builds the validation result from the 3-way diff and adds the checks of
its migrations with `CONSTRAINT_VALIDATOR_MAP`, as a schema load does. The stash's version of this method carries over
unchanged.

### Schema-change gate (FR-004, research R4)

A new analyzer method returns true when the recomputed branch diff holds schema changes or when the source and
destination schema hashes in the registry differ. `GraphMerger._validate_constraints` and the rebase task both use
it. The rebase stops reading the branch's cached schema-hash flag for this decision; its later use of the flag to
decide whether to run migrations is out of scope and stays.

### Merged schema (FR-003, research R5)

`MergeSchemaAnalyzer.get_candidate_schema` becomes async. It returns a copy of the destination schema when the two
hashes are equal; otherwise it loads the common ancestor schema (already loaded for the 3-way diff and cached on the
analyzer), computes the branch's diff since the ancestor, and calls a new `SchemaBranch` method that applies that
diff, taking values from the branch's schema. Rules are in [data-model.md](data-model.md#merged-schema-rules).

### Views (FR-002, FR-008)

- `SchemaValidateMigrationData.is_isolated` is required. Merge, rebase and the proposed-change check pass `False`;
  the schema load endpoint, the schema check endpoint and the core schema update pass `True`.
- The validation task passes the value to `schema_path_validate` (required parameter), which sets it on
  `SchemaConstraintValidatorRequest` (default `True`, because many tests and a graph migration build it directly).
- `SchemaValidatorQuery` stores the option; the optional, kind and new-attribute queries pass it to
  `get_query_filter_path`; their checkers pass `request.is_isolated` when they build the query.

### New-attribute check (FR-005, research R3)

`NodeAttributeAddChecker` uses a new query, `NodeAttributeValueMissingValidatorQuery`, instead of the shared
"node not present" query, which stays for the new-relationship check. Compared with the stash's version, the query
returns only `n.uuid` and the root edge's branch name, not the whole edge (principle V).

### Proposed-change check (FR-009, research R6)

`run_proposed_change_schema_integrity_check` builds a `MergeSchemaAnalyzer` for the source and destination branches,
takes its merged schema and its constraints, keeps the schema processing step and the data-diff constraints, and
sends the validation message with the merge view.

### Refusal state (FR-006, FR-007)

No change to the refusal path: the checks run before the graph is changed, under the diff lock for merge and before
the rebase transaction. Integration tests assert the branch status, both branches' schema and data, and the exact
messages in [contracts/refusal-messages.md](contracts/refusal-messages.md).

### Merged-schema guards (critique E1, E3)

Unit cases cover the profile and template kinds of a changed node, an attribute inherited from a generic, a kind or
attribute the default branch removed and the branch changed (the branch's copy is kept and checked), and the
`used_by` list of a generic. An element the branch's diff lists that the branch's own schema lacks raises an error
naming the kind and element. See
[data-model.md](data-model.md#merged-schema-rules).

### Registry freshness (critique E2)

The gate and the merged schema read the in-memory schemas of the worker that runs the merge. The merge and rebase
flows did not load the latest schemas before the checks: a worker loads a schema update when it processes the
registry refresh message that the schema update sends, or in its refresh every 15 minutes, and neither flow waits for
either. The analyzer now reads each branch from the database before it first reads either schema, and loads the
stored schema of each branch whose hash differs from the one in the registry, the default branch first.

### Docker integration test (critique E6)

A new class in `backend/tests/integration_docker/`, following `test_schema_migration.py`: an attribute's kind
changes from Text to Number on the branch with a non-number value on the default branch, and on the default branch
with a non-number value on the branch. Each is refused at merge and at rebase with the exact messages, and a branch
with compliant data merges. This runs the checks in a worker that loads the branch schema from the database, which
the in-process tests do not.

### Documentation (FR-012)

`docs/docs/branches/merge.mdx` and `docs/docs/branches/rebase.mdx` already state that Infrahub checks the schema
constraints against the data the operation would produce. Add the refusals for schema changes made on either side
to their troubleshooting tables, with the recovery paths for a mandatory attribute added on the default branch
without a default value: delete the nodes on the branch, or add a default value on the default branch. Run
`uv run invoke docs.lint`.

### Operational notes (critique E5, E7, E8)

- Run `EXPLAIN` on the new-attribute query and put the plan in the pull request.
- The validation message's view field is required. During an upgrade in which servers and workers briefly run
  different versions, a request in flight can fail validation; requests started after the upgrade are not affected.
- The proposed-change check loads the common ancestor schema when the two schemas differ, as the merge already does.

### Second pull request (user story 5, FR-010)

The regex, enum, length and choices queries take the view option and their checkers pass `request.is_isolated`,
with a component test per query in both views and one integration refusal.

### Suspected gaps (user story 6, FR-011)

A component test for the new-relationship check in the merge view, and an integration test for an attribute added on
the default branch with a default value. Each one is written to assert the correct behavior; a confirmed gap is fixed
in the first pull request when the fix is in the checks, and recorded as an issue with its reproduction when the fix
belongs in the merge migrations.

## Behavior Changes and Changelog

- One `fixed` changelog fragment, created with `towncrier create` (orphan `+merge-schema-validation`), describing
  the refused merges and rebases. The stash's fragment text is the starting point.
- The pull request description lists the behavior changes from the spec: rebase refusals for default-branch changes,
  the number pool scope check at merge and rebase, and the proposed-change check reading the merge view.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No Playwright E2E test (principle IV) | The feature has no UI change: the refusal appears through the existing merge and proposed-change error display. | An E2E test would exercise the existing error display, not this feature's logic; the behavior is covered at the API level by integration tests with exact messages and by the local matrix through merge, proposed-change merge and rebase. |
