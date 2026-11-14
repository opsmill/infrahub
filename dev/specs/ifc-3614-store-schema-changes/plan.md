# Implementation Plan: Store schema changes and query the schema change history of a branch

**Branch**: `ajtmccarty/ifc-3614-store-migrations` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Branches from**: `develop`

**Input**: Jira task [IFC-3614](https://opsmill.atlassian.net/browse/IFC-3614), project B of the
design document
[INFP-719](https://app.notion.com/p/opsmill/INFP-719-Make-schema-migrations-visible-402228b830258193b43ed097d965f633).

## Summary

A schema owner cannot view which migrations ran on a branch, and a merge or a rebase cannot apply
a branch's schema loads in order, because the loads are not stored.

This plan stores each schema change as its operations, each application of it, and each migration
the application runs, as internal records linked by edges. It adds one applier that builds a
schema from operations, and makes the schema load, the schema check and the dropdown and enum
mutations build their schema with it. It adds a GraphQL query that returns the schema change
history of a branch in pages. It updates the records when a load fails, and deletes them when
their branch is deleted.

The work starts with an equivalence test suite for the applier. No workflow uses the applier
before that suite passes, because every schema load depends on it and the format of the operations
stays open until then.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic 2, Graphene, Prefect, `aiodataloader` (already used by
`backend/infrahub/graphql/loaders/`). No new dependency.

**Storage**: Neo4j. Four new vertex labels and four new edge types, outside the branch-aware graph
model. No index, no constraint, no graph migration ([research.md](research.md), R3).

**Testing**: pytest 9. Unit tests without a database for the builder, the applier and the
equivalence suite. Component and functional tests through testcontainers. One Integration Docker
test for migrations that run on a separate worker.

**Target Platform**: Linux server, API servers and task workers

**Project Type**: backend service

**Performance Goals**: the sources set none. The plan keeps the added cost of a load to:

- one more in-memory processing of the schema, because the applier processes the schema after the
  file was laid over it to find the operations;
- a fixed number of record writes for each load, plus one small write each time a migration
  returns.

A task measures the two processing passes on the largest schema fixture in the repository.

**Constraints**:

- Every schema load, schema check and dropdown or enum mutation goes through the applier, so the
  existing tests of those paths must pass with the same expected results (SC-002).
- The records must not be reverted by the rollback of a failed load, and must not be read by a
  diff, a rebase or a merge of data.
- `schema/schema.graphql` and the generated front-end GraphQL types must be regenerated, because
  CI checks both.

**Scale/Scope**: one new back-end package, `backend/infrahub/core/schema_change/`, one new query
module, three new GraphQL modules, and six existing modules changed. No front-end work, no SDK
change, no CLI change, no new setting.

## Constitution Check

*GATE: passed before Phase 0 research, checked again after Phase 1 design.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Integrity** | Pass. The applier ends with `SchemaBranch.process`, and the load keeps `validate_node_deletions`, `validate_update` and the constraint workflow, all on the applier's result. The records are internal `StandardNode` vertices, as `Preference` is, and the task excludes a core kind. No generated file is edited by hand. |
| **II. Branch-Safe by Default** | Pass. Each record names its branch in a property. The edges between records have no `branch` property, so the rebase, rollback and diff queries do not select them. The behaviour at merge and rebase is specified: this feature writes and changes no record there, and a functional test asserts it. Records are hard-deleted only when their branch is deleted. |
| **III. Type Safety & Explicit Contracts** | Pass. Operations are a Pydantic model with an enumerated type. Statuses are enumerations. Every query returns a typed result. The GraphQL contract and the internal contracts are written in [contracts/](contracts/) before implementation. |
| **IV. Test Discipline** | Pass. The equivalence suite is written first. Each tier is used for what it can prove ([research.md](research.md), R14). No Playwright test: the feature has no user interface, and front-end work is out of scope in the source design. |
| **V. Query Performance & Efficiency** | Pass. All Cypher is parameterized. Operations and migration records are created in bulk. The history query is paginated, fetches nested data for a whole page with two queries through data loaders, and fetches only the fields the request selects. The branch deletion runs in batches. No index is added; R3 says why and when to ask for one. |
| **VI. Security & Input Boundaries** | Pass with one risk recorded. The query adds no write path. Reading the history needs the access that reading the schema needs (spec, decision 3). The stored error strings are the ones the load already returns to its caller, now readable by every reader of the schema ([research.md](research.md), R12). |
| **VII. Simplicity & Maintainability** | Pass with three justified items, in "Complexity Tracking". |

**After Phase 1 design**: no new violation. The design adds no dependency, no setting, no index and
no graph migration.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3614-store-schema-changes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── schema-change-history.graphql
│   └── internal-interfaces.md
├── checklists/
│   └── requirements.md
└── tasks.md                 # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── schema_change/                    # new package
│   │   ├── __init__.py
│   │   ├── constants.py                  # statuses, operation types, format version, edge types, page sizes
│   │   ├── operations.py                 # SchemaOperation, summary and name
│   │   ├── operation_builder.py          # SchemaOperationBuilder
│   │   ├── applier.py                    # SchemaChangeApplier
│   │   ├── candidate.py                  # SchemaCandidate, SchemaCandidateBuilder
│   │   ├── models.py                     # the four StandardNode records
│   │   ├── repository.py                 # SchemaChangeRepository
│   │   ├── recorder.py                   # SchemaChangeRecorder, SchemaChangeRecording
│   │   ├── application_runner.py         # SchemaChangeApplicationRunner
│   │   └── migration_recorder.py         # MigrationRecorder and its two implementations
│   ├── query/
│   │   └── schema_change.py              # new: Query classes for the records
│   ├── schema/
│   │   └── update_coordinator.py         # changed: passes the application ID
│   ├── migrations/schema/
│   │   ├── models.py                     # changed: application ID in the flow message
│   │   └── tasks.py                      # changed: the flow reports to a MigrationRecorder
│   └── branch/
│       └── data_deleter.py               # changed: deletes the records of the branch
├── api/
│   └── schema.py                         # changed: load and check build their schema with the applier
├── exceptions.py                         # changed: the applier's refusal
└── graphql/
    ├── queries/
    │   ├── schema_change.py              # new: InfrahubSchemaChange
    │   └── __init__.py                   # changed: export
    ├── types/
    │   └── schema_change.py              # new
    ├── loaders/
    │   └── schema_change.py              # new: operations and applications loaders
    ├── mutations/
    │   └── schema.py                     # changed: update_registry uses the applier and records
    └── schema.py                         # changed: registers the query

backend/tests/
├── unit/core/schema_change/              # equivalence suite, builder, applier, summary and name
├── component/core/schema_change/         # repository, recorder
├── component/graphql/queries/            # history query
├── component/graphql/mutations/          # dropdown and enum mutations store a schema change
├── component/api/                        # load and check
├── component/core/                       # branch data deletion
├── functional/schema_change/             # loads with data, failure, deletion, merge and rebase
└── integration_docker/                   # migrations on a separate worker

schema/schema.graphql                     # regenerated
frontend/app/src/shared/api/graphql/generated/   # regenerated
docs/docs/schema/                         # user documentation of the query
dev/knowledge/backend/schema-changes.md   # new: how stored schema changes work
changelog/                                # one fragment, type "added"
```

**Structure Decision**: the feature is a back-end package next to `core/preferences/`, the
existing example of internal records with a repository and query classes. The query classes go in
`core/query/`, where the other query classes are. The GraphQL modules follow the layout of
`graphql/queries/`, `graphql/types/` and `graphql/loaders/`.

## Design

The detail of each decision is in [research.md](research.md). The records are in
[data-model.md](data-model.md). The contracts are in [contracts/](contracts/).

### How a schema load runs after this change

1. Validate the request, the permissions and the branch status, as today.
2. Take the schema lock, as today.
3. Build the candidate with `SchemaCandidateBuilder`: lay the file over the branch schema, process
   it, keep the paths of the diff that the file states as operations, apply the operations with
   the applier, then calculate the diff, the migrations and the constraints from the applier's
   result.
4. Return without writing when the diff is empty, as today.
5. Run the constraint workflow, as today. A violation refuses the load, and nothing is stored.
6. Run `SchemaChangeApplicationRunner`:
   - create the schema change and its application with the status `running`;
   - call `SchemaUpdateCoordinator.execute` with the application ID. The migration flow creates a
     record for each migration and updates it when the migration returns;
   - on success, assign the version and the parent and set the records to `applied`;
   - on failure, after the coordinator rolled the graph back, set the records to `failed` and
     raise the same error.
7. Refresh the schema hash and send the event, as today.

### How the schema check runs

The check uses the same `SchemaCandidateBuilder` and returns the diff of the applier's result. It
stores nothing.

### How a dropdown or enum mutation runs

1. Validate the input and change the attribute in memory, as today.
2. Build one `element_property` operation on `choices` or `enum`, with the list before the change.
3. Apply it with the applier to get the candidate schema.
4. Inside the transaction that saves the schema, store the schema change, its operation and its
   application with the status `applied`.

### How the history is read

`InfrahubSchemaChange` reads the schema changes of the branch of the request in pages. Two data
loaders read the operations and the applications with their migration records for every schema
change of the page.

### How the records of a branch are deleted

`BranchDataDeleter.delete_branch_data` deletes the schema changes of the branch with their
operations, applications and migration records, in batches.

## Risks

| Risk | What limits it |
| --- | --- |
| The applier handles a case differently from today's load, and ordinary loads break | The equivalence suite passes before the applier is used. The existing schema tests run unchanged (SC-002) |
| A schema change holds a value that processing calculated, and a later replay brings back an out-of-date value | The builder keeps only the paths that the file states, with values read before processing. A group of unit tests applies recorded operations to a target that gained a kind |
| The format of the operations has to change after the suite | The format has a version on every schema change, and no workflow stores records before the suite passes |
| The write that ends a load fails, and a schema change keeps the status `running` | The operations are stored, so a recovery task can finish it. Recovery is out of scope in the source design |
| Two processing passes slow a load on a large schema | A task measures it. The design document measured about 0.16 s for one pass on the internal and core schema |
| A new edge type is picked up by a query that matches edges without a type | The edges have no `branch` property. A functional test runs a rebase, a merge and a failed load and asserts that the records are unchanged |
| Error strings stored in the records are shown to every reader of the schema | Recorded for review ([research.md](research.md), R12) |

## Complexity Tracking

| Item | Why it is needed | Simpler alternative rejected because |
| --- | --- | --- |
| A load and a check process the schema twice | The operations are found by laying the file over the schema, and FR-021 requires the saved schema to come from the applier | Saving the first processed schema would let a load and a later replay of its operations give different schemas |
| `MigrationRecorder` is an interface with an implementation that does nothing | A merge, a rebase and the core schema update run the same flow without an application until their own tasks add one | An optional collaborator with a `None` check at each use is what the component guideline forbids |
| `SchemaChangeApplicationRunner` has one caller in this feature | The source design lists "code that applies one schema change, creates an application and a record for each migration, and updates their status" in this task's scope, and the staging and replay tasks call it | Writing the sequence in the load endpoint would have to be moved out by the next task |
