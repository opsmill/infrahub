# Implementation Plan: Owner and source metadata, and extension points for ownership-based permissions (Community side), storage option E

**Branch**: `rbac-owners-option-e-infp-753` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-753-rbac-owners-option-e/spec.md`

**Sibling plan**: [`infp-753-rbac-owners-option-b`](../infp-753-rbac-owners-option-b/plan.md) plans the same behaviour with storage option B. The team builds one of the two.

## Summary

Infrahub Community stores several owners per node, per attribute and per relationship field, and several sources per node, separately on each branch. Infrahub reads inherited owners at query time: from profiles, from the object template copy and from the parent. Users read and set owners and sources through GraphQL, the Python SDK and object files. Community also defines the change check that Infrahub Enterprise replaces, the "applies to" setting, and the account group tree setting. In Community, owners restrict nothing. This plan holds no frontend change.

Technical approach (see [research.md](research.md)):

- Storage option E: `HAS_OWNER` edges from node and attribute vertices, `OwnerSet` vertices for relationship fields and for the owners that profiles and object templates give, a `HAS_NO_OWNER` edge to one shared `NoOwner` vertex, and a `HAS_OWNER_SOURCE` edge for the template copy (R-1). No edge has a property.
- One package, `backend/infrahub/core/ownership/`, holds the models, the queries, the repository, the resolution, the writer and the filter (R-2). A local prototype of this package exists (spec, "What the prototype of option E holds").
- One batch read gives the owners that apply to all nodes and fields of a GraphQL request (R-3). A query that does not ask for owners reads none (FR-009).
- The diff, the merge and the conflict code get a separate path for owner edges, because they do not read edges from the node vertex today (R-9).
- The change check is an interface of Community with an implementation that allows everything. Six places in the mutations call it inside their transaction (R-14).
- Node sources use `HAS_SOURCE` edges from the node vertex (R-8). The prototype does not have them.
- The kind migration must change: it keeps one edge only between two vertices, and a node can have the same account group as owner and as source (R-11).

## Technical Context

**Language/Version**: Python 3.14 (backend and Python SDK)

**Primary Dependencies**: FastAPI, graphene, Neo4j driver 6, Pydantic 2. No new dependency.

**Storage**: Neo4j. New vertex labels `OwnerSet` and `NoOwner`. New edge types `HAS_NO_OWNER`, `HAS_OWNER_SET`, `HAS_TARGET_OWNER_SET` and `HAS_OWNER_SOURCE`. `HAS_OWNER` and `HAS_SOURCE` edges from the node vertex. One new attribute on `CoreObjectPermission`. Graph migrations and new indexes (see [data-model.md](data-model.md)).

**Testing**: pytest. Unit tests for pure logic, component tests with Neo4j through testcontainers, functional tests through GraphQL, query benchmarks in `backend/tests/query_benchmark/`.

**Target Platform**: Linux server

**Project Type**: Web service (backend) with the Python SDK submodule. No frontend change (spec, "Out of scope").

**Performance Goals**: SC-001 to SC-008 of the spec. The spike measures SC-009 and SC-010. SC-003 is not met today (spec, "Open questions").

**Constraints**:

- No change in behaviour, permissions or speed for a customer who does not use owners (FR-009, SC-001, SC-002, SC-007).
- All owner data is stored separately on each branch. The upgrade closes edges and deletes nothing.
- The change check runs inside the transaction of the mutation (D-13).
- Community gives no right to an Enterprise permission value (D-14).

**Scale/Scope**: the reference data set of the spec: 10,000 devices with 48 interfaces each, a location hierarchy 5 levels deep, 50 account groups that own nodes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS with note | "Applies to", the action for changing owners and the global permission are in the core schema and the enums. Owner edges are graph metadata, like `HAS_OWNER` and `IS_PROTECTED` today. They are declared in `core/graph/schema.py`. See Complexity Tracking. |
| II. Branch-Safe by Default | OPEN | All owner edges carry branch and time data. Each merge and rebase case of FR-030 gets a test. `OwnerSet` and `NoOwner` vertices have no branch data. Two points are not decided, and a decision task blocks Phase 3 for each: the design for two branches that create the same `OwnerSet` (R-21), and the rule for conflicts between owner changes (R-9). |
| III. Type Safety & Explicit Contracts | PASS | Contracts in [contracts/](contracts/). Query results through frozen dataclasses. The change check is a typed interface. |
| IV. Test Discipline | PASS with note | Unit, component and functional tests for each requirement. An integration Docker test for the schema migrations. E2E tests in `tests/e2e/ownership/` run user stories 1 to 6 through the API on the full stack (R-19). They open no page, because this plan has no frontend change. User story 7 has no E2E test, because its setting needs its own stack. A maintainer confirms both points (first task of tasks.md). |
| V. Query Performance & Efficiency | PASS with measurement | One batch read for each request. No owner read without a request. Each new query gets `EXPLAIN` and `PROFILE` checks and a query benchmark. SC-003 is not met with the database filter (R-6). |
| VI. Security & Input Boundaries | PASS | Owner inputs are validated (FR-003). Cypher uses parameters. Community refuses Enterprise permission values at save time and drops them at load time (R-15). |
| VII. Simplicity & Maintainability | PASS | No new mutation, no new dependency. Sources stay on nodes only. An index of the owners that apply is built only if the spike shows that SC-003 needs it. |

**Post-Phase 1 re-check**: principle II stays open until the decision tasks of Phase 1 are done. The design keeps the other gates. The work crosses these governance gates, and each one needs approval before a pull request (`AGENTS.md`, "Ask First"):

- Database structure change and graph migrations
- A change to the kind migration
- New database indexes
- Core schema change: `applies_to`, the action for changing owners, the global permission to manage ownership
- GraphQL schema change, with no new mutation
- Authentication and authorization change: the change check and the group tree setting
- A new configuration setting
- Python SDK submodule change. The pull request on the SDK repository comes first.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-753-rbac-owners-option-e/
├── spec.md
├── plan.md              # This file
├── research.md          # Decisions R-1 to R-22
├── data-model.md        # Graph structure, core schema changes, domain model
├── quickstart.md        # Validation guide
├── measurements.md      # Created by the spike
├── contracts/
│   ├── graphql-schema.graphql
│   ├── object-file.md
│   └── change-check.md
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

"P" marks a file that the option E prototype already changes or adds. The prototype is not committed.

```text
backend/infrahub/
├── core/ownership/                          # P: new package
│   ├── constants.py                         # P: NoOwner UUID, depth limit, filter names
│   ├── models.py                            # P: OwnerState, OwnerOrigin, HolderKey, dataclasses
│   ├── queries.py                           # P: read and write queries
│   ├── repository.py                        # P: database access for owner states
│   ├── resolution.py                        # P: order of sources for a node and for a field
│   ├── resolver.py                          # P: batch read of the owners that apply
│   ├── writer.py                            # P: states, template copy, legacy `owner` write
│   ├── input.py                             # P: parse and validate owner input
│   ├── filter.py                            # P: owner filter in list and count queries
│   ├── sources.py                           # Node sources: read, write, filter
│   └── report.py                            # Upgrade report queries
├── core/constants/database.py               # P: new edge types
├── core/graph/schema.py                     # P: new vertices and edges
├── core/graph/index.py                      # Index for the diff of owner edges
├── core/graph/__init__.py                   # P: GRAPH_VERSION
├── core/attribute.py                        # P: several owners, deprecated `owner`
├── core/query/attribute.py                  # P: owner edges of attributes
├── core/query/node.py                       # P: owner filter in NodeGetListQuery
├── core/node/__init__.py                    # P: owner input, delete closes owner edges
├── core/node/create.py                      # P: template copy; change check for a create
├── core/diff/ownership_differ.py            # P: owner changes in the diff
├── core/diff/ownership_fields.py            # P: reserved field names in the diff
├── core/diff/query/ownership.py             # P: diff query for owner edges
├── core/diff/calculator.py                  # P
├── core/diff/query_parser.py                # P
├── core/diff/query/bulk_merge.py            # P: merge of owner edges
├── core/diff/merger/merger.py               # P
├── core/diff/merger/exclusion_plan.py       # P
├── core/diff/conflicts_extractor.py         # Conflicts between owner changes
├── core/diff/enricher/labels.py             # Owner display labels in the diff
├── core/changelog/diff.py                   # Several owners in the changelog
├── core/migrations/graph/                   # Upgrade migrations (next free numbers)
├── core/migrations/query/owner_set_attribute.py      # P
├── core/migrations/query/node_duplicate.py           # One edge for each edge type; outgoing owner and source edges
├── core/migrations/schema/attribute_name_update.py   # P
├── core/migrations/schema/node_attribute_remove.py   # P
├── core/migrations/schema/node_remove.py             # P
├── core/migrations/schema/node_kind_update.py        # Copy the new edge types
├── core/schema/definitions/core/permission.py        # applies_to, HFID, uniqueness
├── core/node/permissions.py                 # Save-time validation of Enterprise values
├── core/account.py                          # Load applies_to; group tree ancestors
├── core/constants/__init__.py               # PermissionAppliesTo, new action, new global permission
├── config.py                                # SecuritySettings: group tree setting
├── permissions/change_check/                # New: interface, Community class, models, collector
├── permissions/manager.py                   # Drop Enterprise permission values at load time
├── graphql/types/ownership.py               # P: output and input types
├── graphql/resolvers/ownership.py           # P: field resolvers
├── graphql/manager.py                       # P: fields, inputs, filters, deprecations
├── graphql/initialization.py                # P: resolver on the GraphQL context
├── graphql/mutations/main.py                # Change check for update and delete
├── graphql/mutations/attribute.py           # P: `owners` on attribute inputs
├── graphql/mutations/relationship.py        # Change check for add and remove
├── graphql/mutations/ipam.py                # Change check for the IP prefix delete
├── graphql/mutations/convert_object_type.py # Owners follow the conversion; change check
├── graphql/error_formatter.py               # One error for each refused item
├── graphql/queries/event.py                 # Owner labels in the activity log
├── workers/dependencies.py                  # Build the change check
└── cli/db.py                                # Upgrade report and group tree report

backend/tests/
├── unit/core/ownership/                     # Resolution order, input parsing
├── unit/permissions/change_check/           # Collector, Community class
├── component/core/ownership/                # Storage, resolver, filter, writer, sources
├── component/core/diff/merge/               # P: owner diff and merge scenarios
├── component/core/migrations/               # P: upgrade and schema migrations
├── component/graphql/metadata/              # P: GraphQL read and write of owners
├── component/permissions/                   # applies_to, group tree, change check calls
├── integration_docker/                      # Schema migrations on nodes with owners
└── query_benchmark/                         # SC-001 to SC-006, SC-008

tests/e2e/ownership/                         # User stories 1 to 6 through the API, no page

python_sdk/infrahub_sdk/                     # Submodule
└── spec/object.py                           # node_metadata and field owners in object files

schema/schema.graphql                        # Regenerated
frontend/app/src/shared/api/graphql/generated/  # Regenerated by `pnpm codegen`, not edited
docs/docs/                                   # User documentation and generated reference
dev/knowledge/backend/                       # database-schema.md, permissions.md, mutations.md
changelog/                                   # Towncrier fragments
```

**Structure Decision**: the owner code goes into `backend/infrahub/core/ownership/`, where the prototype has it. The change check goes into `backend/infrahub/permissions/change_check/`, because it is a permission concern and Infrahub Enterprise replaces it. The GraphQL layer, the node layer and the mutation layer call both at their entry points.

## Delivery order

The order follows the priorities of the user stories, as tasks.md does. The step numbers are the delivery steps of the spec, so they are not in sequence. The pull requests do not follow these steps: each pull request holds one layer for all the steps (see "Pull requests").

1. Decisions: the approvals of the governance gates, the product decisions, and the open design points that block a phase (R-22).
2. API review of the names with the SDK maintainers and the consumers of the API (R-4, R-5).
3. Spike: build the storage of step 1 on a branch. Measure SC-003 to SC-006, SC-009 and SC-010 with plain Cypher queries, as the benchmark of 2026-11-09 did. Decide how the owner filter meets SC-003 (R-6). The spike ends before the first pull request.
4. Step 1 (P1.1): storage, resolution, GraphQL read and write of node owners, the owner filter, diff and merge, the upgrade (R-1 to R-6, R-9 to R-13).
5. Step 2 (P1.2): owners that profiles and object templates give (R-7).
6. Step 5: the change check, "applies to", and the permission report of each node (R-14 to R-16).
7. Step 3 (P1.3): owners of single fields, and the deprecated `owner` field (R-13).
8. Step 6: the account group tree setting and its report (R-17).
9. Step 4 (P1.4): node sources (R-8).
10. Object files in the Python SDK, after the API review (R-18).
11. Docs, generated files and changelog fragments (R-20), and a second measure of SC-009 and SC-010 through the change check.

SC-001 and SC-002 are measured before any change (the "today" numbers) and again by the benchmarks of step 1.

## Pull requests

The work is cut by layer, not by user story. A reviewer reads one layer at a time, and the number of pull requests stays low. tasks.md ("Pull Request Split") lists the tasks of each pull request.

The decisions, the API review and the spike produce no pull request. The spike branch is not merged.

| Order | Pull request | Content | Needs |
|---|---|---|---|
| 1 | Database layer | Graph structure, `core/ownership/` (storage, resolution, owner filter, node sources), the copy of template owners at the create, query benchmarks, `dev/knowledge/backend/database-schema.md` | The spike |
| 2 | Branch layer | Diff, merge, conflicts, rebase and changelog of owners and sources | Database layer |
| 3 | Upgrade | Graph migrations, schema migrations, the kind change, the upgrade report, the refusal of repositories as owners | Database layer |
| 4 | GraphQL layer | Types, resolvers, fields, inputs and filters, the deprecated `owner` and `is_protected`, owner labels in the activity log, E2E tests | Branch layer, upgrade |
| 5 | Permission layer | The change check and its calls in the mutations, "applies to", the permission report of each node, `dev/knowledge/backend/permissions.md` and `dev/knowledge/backend/mutations.md` | GraphQL layer |
| 6 | Account group tree | The setting, the permission queries, the report | Permission layer |
| 7 | Object files | The pull request on the SDK repository, then the backend part and the submodule pointer | GraphQL layer, permission layer |
| 8 | User documentation | The pages in `docs/docs/` | All the other pull requests |

Order of the pull requests:

- The branch layer and the upgrade can be in review at the same time. So can the account group tree and the object files.
- The branch layer and the upgrade merge before the GraphQL layer. So no user can write owners that Infrahub cannot merge or migrate.
- Nothing reaches the API before the GraphQL layer. The database layer and the branch layer must change no result for users, and they get no changelog fragment.
- The storage option changes the database layer, the branch layer and the upgrade only. The other pull requests are the same for option B and option E.
- Infrahub Enterprise can start its own work after the permission layer.

Rules for every pull request:

- The tests of a layer are in the same pull request. The database layer, the branch layer and the upgrade use no GraphQL test, because the API does not exist yet.
- Each pull request that users can notice has its Towncrier fragment: the upgrade, the GraphQL layer, the permission layer, the account group tree and the object files.
- Each pull request regenerates the files that it changes.
- Each pull request leaves `stable` and `develop` releasable.

What this split costs:

- A user can set and read owners only after the GraphQL layer.
- All owner types arrive together. Node owners cannot be released before field owners or node sources.
- The database layer and the GraphQL layer are the largest pull requests. If a review is too heavy, cut each one time:
  - Database layer: move the owners that profiles and object templates give, and the node sources, to a second pull request.
  - GraphQL layer: one pull request for the read (fields and filters), one for the write (inputs).

Not decided: the base branch of the pull requests (`develop` or a feature branch).

## Write paths and the change check

| Path | Change check |
|---|---|
| Create, update, upsert and delete of the generic mutations, and the mutation subclasses that call the generic code | Called (R-14) |
| `RelationshipAdd`, `RelationshipRemove` | Called (R-14) |
| IP prefix delete | Called by its own call, because it does not use the generic delete (R-14) |
| Object conversion (`ConvertObjectType`) | Called as a delete and a create (R-14) |
| Profile values applied to nodes, computed attributes, template components, pool allocations, merges | Not called (FR-046) |
| Generators and repository imports | Called with the account of the task worker (spec, "Assumptions") |

## Known gaps of this plan

- SC-003 is not met with the database filter. The spike decides between a faster query and an index of the owners that apply (R-6). If it chooses the index, its tasks are added to tasks.md before Phase 3.
- These rules are not decided, and tasks.md holds a decision task for each: the conflicts between owner changes (FR-030), the result of two writes at the same time (FR-032), the depth limit of the walk to the parents (E-16), and the audit metadata of an owner change (FR-053).
- The finding on the kind migration (R-11) comes from a read of the query. No test proves it.
- The design for two branches that create the same `OwnerSet` at the same moment is a proposal (R-21). No test exists.
- The prototype does not hold node sources, object files, the change check, "applies to" or the group tree. It was not checked for a rebase with conflicts, for two branches merged one after the other, or for a node kind change.
- The GraphQL shape of node sources and of the permission report is a proposal of this plan (R-8, R-16). The engineering design gives the shape of owners only.
- The Infrahub Enterprise repository is not on the dev VM. How Enterprise replaces the Community class was not checked there (R-14).
- The `python_sdk` submodule is not checked out in this worktree. The file names of the SDK come from the earlier draft (R-18).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Owner data as graph edges, not as schema attributes or relationships (principle I) | Each owner must diff and merge as one item on each branch, and "find the nodes of one owner" must not read every owner list | A JSON list in a metadata attribute (option A) is ruled out: Infrahub must read every owner list to find the nodes of one owner. A schema relationship on every kind changes every GraphQL type and loses deleted owners |
| `OwnerSet` vertices without branch data (principle II) | One set for each key must stay after the merges of several branches | Edge properties on `HAS_OWNER` (option B): see the sibling plan. The kind migration keeps one edge for each pair of vertices and loses the properties. With node sources, option E also needs a change to the kind migration (R-11) |
| A separate diff and merge path for owner edges | The diff and the merge do not read edges from the node vertex today | Reuse of the attribute pipeline needs owner lists in attribute vertices, which is option A |
