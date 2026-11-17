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
schema from operations. The schema load, the schema check and the dropdown and enum mutations
build their candidate schema through one candidate builder: a load and a check build the
operations from the processed schema of the file and keep that schema, and a mutation builds its
schema with the applier. The tests apply the operations of every loaded file with the applier and
fail when the result differs (spec, decision 8). It adds a GraphQL query that returns the schema
change history of a branch in pages. It updates the records when a load fails, and deletes them
when their branch is deleted.

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

- building the operations from the diff of the processed schema, which a load already
  calculates; the schema is processed once, as a direct load does (spec, decision 8);
- a fixed number of record writes for each load, plus one small write each time a migration
  returns.

A task measures the candidate builder on the largest schema fixture in the repository: building
the candidate takes 1.00 times the time of the direct load ([research.md](research.md), R7).
With a second processing pass in the applier, before T065, it took 2.00 times.

**Constraints**:

- Every schema load, schema check and dropdown or enum mutation goes through the candidate
  builder, and every mutation through the applier, so the existing tests of those paths must pass
  with the same expected results (SC-002).
- The records must not be reverted by the rollback of a failed load, and must not be read by a
  diff, a rebase or a merge of data.
- `schema/schema.graphql` and the generated front-end GraphQL types must be regenerated, because
  CI checks both.

**Scale/Scope**: one new back-end package, `backend/infrahub/core/schema_change/`, one new query
module, four new GraphQL modules, and ten existing modules changed. Three more modules change
one call each, because `SchemaUpdateCoordinator.execute` loses an argument and gains one:
`cli/db.py`, `core/branch/tasks.py` and `core/merge/orchestrator.py`. No front-end work, no SDK
change, no CLI command change, no new setting.

## Constitution Check

*GATE: passed before Phase 0 research, checked again after Phase 1 design.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Integrity** | Pass. The applier ends with `SchemaBranch.process`. The load keeps `validate_node_deletions`, `validate_update` and the constraint workflow, on the processed schema of the laid-over file; a mutation runs them on the applier's result. The records are internal `StandardNode` vertices, as `Preference` is, and the task excludes a core kind. No generated file is edited by hand. |
| **II. Branch-Safe by Default** | Pass. Each record names its branch in a property. The edges between records have no `branch` property, so the rebase, rollback and diff queries do not select them. The behaviour at merge and rebase is specified: this feature writes and changes no record there, and a functional test asserts it. Records are hard-deleted only when their branch is deleted. |
| **III. Type Safety & Explicit Contracts** | Pass. Operations are a Pydantic model with an enumerated type. Statuses are enumerations. Every query returns a typed result. The GraphQL contract and the internal contracts are written in [contracts/](contracts/) before implementation. |
| **IV. Test Discipline** | Pass. The equivalence suite is written first. Each tier is used for what it can prove ([research.md](research.md), R14). No Playwright test: the feature has no user interface, and front-end work is out of scope in the source design. |
| **V. Query Performance & Efficiency** | Pass. All Cypher is parameterized. Operations and migration records are created in bulk. The history query is paginated, fetches nested data for a whole page with two queries through data loaders, and fetches only the fields the request selects. The branch deletion runs in batches. No index is added; R3 says why and when to ask for one. |
| **VI. Security & Input Boundaries** | Pass. The query adds no write path. It needs a logged-in account (spec, decision 3), because the stored error strings can hold the text of an internal exception and anonymous read access is on by default ([research.md](research.md), R12). |
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
│   │   ├── constants.py                  # format version, name digits, property names, page sizes
│   │   ├── enums.py                      # statuses, operation enumerations, edge types
│   │   ├── operations.py                 # SchemaOperation, summary and name
│   │   ├── operation_builder.py          # SchemaOperationBuilder
│   │   ├── applier.py                    # SchemaChangeApplier
│   │   ├── candidate_comparer.py         # SchemaCandidateComparer, used by the replay check of the tests
│   │   ├── candidate.py                  # SchemaCandidate, SchemaCandidateBuilder
│   │   ├── operations_check.py           # SchemaOperationsCheck interface, NoSchemaOperationsCheck
│   │   ├── models.py                     # the four StandardNode records
│   │   ├── repository.py                 # SchemaChangeRepository: writes and the version read
│   │   ├── history_reader.py             # SchemaChangeHistoryReader: paged reads of the history query
│   │   ├── version_resolver.py           # SchemaChangeVersionResolver, SchemaChangeVersion
│   │   ├── recorder.py                   # SchemaChangeRecorder, SchemaChangeRecording
│   │   ├── application_runner.py         # SchemaChangeApplicationRunner and the two Protocols it depends on
│   │   ├── migration_recorder.py         # MigrationRecorder interface, NoRecordMigrationRecorder
│   │   ├── application_migration_recorder.py  # ApplicationMigrationRecorder, MigrationRecordStore
│   │   └── factory.py                    # functions that build the components for each entry point
│   ├── query/
│   │   └── schema_change.py              # new: Query classes for the records
│   ├── schema/
│   │   └── update_coordinator.py         # changed: passes the application ID; one signature for execute
│   ├── migrations/schema/
│   │   ├── models.py                     # changed: application ID in the flow message
│   │   └── tasks.py                      # changed: the flow reports to a MigrationRecorder
│   └── branch/
│       └── data_deleter.py               # changed: deletes the records of the branch
├── api/
│   └── schema.py                         # changed: load and check build their candidate with the candidate builder;
│                                         # the load runs the application runner
├── config.py                             # changed: Override.schema_operations_check, set only by the tests
├── exceptions.py                         # changed: the applier's refusal
└── graphql/
    ├── queries/
    │   ├── schema_change.py              # new: InfrahubSchemaChange
    │   └── __init__.py                   # changed: export
    ├── types/
    │   └── schema_change.py              # new
    ├── loaders/
    │   └── schema_change.py              # new: operations and applications loaders
    ├── resolvers/
    │   └── schema_change.py              # new: operations and applications fields, through the loaders
    ├── mutations/
    │   └── schema.py                     # changed: apply_attribute_property_change replaces update_registry
    └── schema.py                         # changed: registers the query

backend/tests/
├── unit/core/schema_change/              # equivalence suite, builder, applier, comparer, runner, summary and name;
│                                         # conftest.py (shared processed schema), helpers.py (test implementations)
├── helpers/schema_change.py              # seeding function for the component tests of the records;
│                                         # the replay check that backend/tests/conftest.py installs
├── benchmark/                            # the candidate builder against the direct load
├── component/core/schema_change/         # repository, history reader, version resolver, recorder,
│                                         # migration recorder, branch data deletion
├── component/graphql/queries/            # history query
├── component/graphql/mutations/          # dropdown and enum mutations store a schema change
├── functional/schema_change/             # shared base class and data set; load, check, history,
│                                         # failure and deletion in one ordered class; merge and rebase
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
`graphql/queries/`, `graphql/types/`, `graphql/loaders/` and `graphql/resolvers/`.

## Design

The detail of each decision is in [research.md](research.md). The records are in
[data-model.md](data-model.md). The contracts are in [contracts/](contracts/).

### How a schema load runs after this change

1. Validate the request, the permissions and the branch status, as today.
2. Build the candidate builder and the runner with `factory.py`, and the coordinator that the
   runner receives as its executor.
3. Take the schema lock, as today. Build the candidate with `build_candidate_from_schemas`, which
   the schema check also calls: merge the files, lay them over the branch schema, process, keep
   the paths of the diff that the files state as operations, then calculate the migrations and
   the constraints from that processed schema and that diff. The applier does not run, and the
   schema is processed once. The builder passes the operations to its `SchemaOperationsCheck`,
   which checks nothing in production; in the tests it applies the operations with the applier
   and raises when the result differs ([research.md](research.md), R7).
4. Return without writing when the diff is empty, as today.
5. Run the constraint workflow, as today. A violation refuses the load, and nothing is stored.
6. Run `SchemaChangeApplicationRunner` with the account of the request and the context that has
   the priority `HIGH`:
   - create the schema change and its application with the status `running`;
   - call `SchemaUpdateCoordinator.execute` with the application ID, the account and the context.
     The migration flow creates a record for each migration and updates it when the migration
     returns;
   - on success, assign the version and the parent and set the records to `applied`;
   - on failure, after the coordinator rolled the graph back, set the records to `failed` and
     raise the same error.
7. Refresh the schema hash and send the event, as today.

### How the schema check runs

The check calls the same `build_candidate_from_schemas` and returns the diff of the processed
schema of the laid-over files. It runs the constraint workflow through `_validate_migrations`, as the load does. It
stores nothing.

### How a dropdown or enum mutation runs

1. Validate the input and calculate the new list of `choices` or `enum`, without changing a copy
   of the kind.
2. Take the schema lock. Read the list before the change from the branch schema, and build one
   `element_property` operation with it.
3. Build the candidate with `SchemaCandidateBuilder.from_operations`, which applies the operation
   with the applier and returns the schema and the diff.
4. Take one timestamp. Inside the transaction, store the schema change, its operation and its
   application with the status `applied`, then save the schema at the same timestamp. The records
   come first, because the save replaces the schema in the registry before the commit.

### How the history is read

`InfrahubSchemaChange` reads the schema changes of the branch of the request in pages, for a
logged-in account, through `SchemaChangeHistoryReader`. Two data loaders read the operations and
the applications with their migration records for every schema change of the page, through the
same reader. The resolver of the query builds the two loaders once for its page, and each loader
opens a read-only session of its own, because graphql-core resolves the nested fields of the page
concurrently.

### How the records of a branch are deleted

`BranchDataDeleter.delete_branch_data` deletes the schema changes of the branch with their
operations, applications and migration records. Each query deletes at most the deleter's batch
size of schema changes, each with all its records, and the deleter runs it until it deletes
nothing. It runs the query itself, as it runs its other queries. Neither the repository nor the
history reader has a delete method.

## Risks

| Risk | What limits it |
| --- | --- |
| The applier handles a case differently from today's load, and ordinary loads break | The equivalence suite passes before the applier is used. The existing schema tests run unchanged (SC-002) |
| A schema change holds a value that processing calculated, and a later replay brings back an out-of-date value | The builder keeps only the paths that the file states, with values read before processing. A group of unit tests applies recorded operations to a target that gained a kind |
| The format of the operations has to change after the suite | The format has a version on every schema change, and no workflow stores records before the suite passes |
| The write that ends a load fails, and a schema change keeps the status `running`. When the write that sets `applied` fails, the load also returns that error although the schema was saved | The operations are stored, so a recovery task can finish it. Recovery is out of scope in the source design ([research.md](research.md), R8) |
| The stored operations of a load miss a change, and a later replay gives another schema than the saved one | The schema is processed once and the operations are not applied in production (spec, decision 8). In the tests, every load applies them with the applier and fails when the result differs; the equivalence suite covers the listed cases |
| A new edge type is picked up by a query that matches edges without a type | The edges have no `branch` property. A functional test runs a rebase, a merge and a failed load and asserts that the records are unchanged |
| Error strings stored in the records hold the text of an internal exception | The query needs a logged-in account ([research.md](research.md), R12) |
| A case outside the equivalence list differs in production | Nothing detects it in production. Every test that loads a schema file fails on it, with the kinds that differ ([research.md](research.md), R7) |
| A branch created while a load on main is running gets the wrong base version | `applied_at` is the timestamp of the load's writes, and a component test covers the timing ([research.md](research.md), R10) |

## Complexity Tracking

| Item | Why it is needed | Simpler alternative rejected because |
| --- | --- | --- |
| `SchemaOperationsCheck` is an interface whose production implementation checks nothing | The tests verify, on every schema load, that the operations rebuild the schema; production processes the schema once (spec, decision 8) | Applying the operations in every load processes the schema a second time; a setting or an environment variable to turn the check on was not wanted |
| Three `Protocol` classes have one production implementation each (`ApplicationRecorder`, `SchemaUpdateExecutor`, `MigrationRecordStore`) | Each has a recording or a failing implementation in the tests, which the component guideline counts as the second implementation | Typing the runner and the migration recorder against the concrete classes would need a database or a mock library to test the handling of a failure |
| `MigrationRecorder` is an interface with an implementation that does nothing | A merge, a rebase and the core schema update run the same flow without an application until their own tasks add one | An optional collaborator with a `None` check at each use is what the component guideline forbids |
| `SchemaChangeApplicationRunner` has one caller in this feature | The source design lists "code that applies one schema change, creates an application and a record for each migration, and updates their status" in this task's scope. The staging and replay tasks apply a schema change that already exists, so they extend the runner; this feature does not design for them | Writing the sequence in the load endpoint would put the handling of a failed load where a unit test cannot reach it with test implementations of the recorder and the coordinator |
