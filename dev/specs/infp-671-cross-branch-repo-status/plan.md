# Implementation Plan: Cross-branch Repository Status Query

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-671-cross-branch-repo-status/spec.md`, plus the
request to put the query in front of the frontend team as early as possible, even if it first returns
made-up data.

## Summary

Add one hand-written GraphQL query, `InfrahubRepositoryBranchStatus`, that returns a repository's
per-branch import status and commit for every relevant branch in one request, paginated and filtered
server-side, resolved entirely from the graph. Build it on a core primitive (one Cypher statement over a
branch-name list and an attribute set) that the periodic repository sync also adopts, replacing its
one-query-per-branch loop.

Delivery is contract-first in three increments (see [research.md](research.md), Decision 1):

| Increment | Ships | What is real | What is fabricated |
| --- | --- | --- | --- |
| A, contract stub | Root field, types, all arguments, regenerated `schema/schema.graphql`, permission check, branch row set, paging | Repository lookup, permission denial, row membership, ordering, paging, count | Attribute values (`commit`, `sync_status`, `internal_status`, `ref`); attribute-value filters are inert |
| B, graph read | Core primitive and reader, attribute filters, query-count and inheritance tests, changelog, docs | Everything | Nothing; the stub module is deleted |
| C, periodic sync | `get_repositories_commit_per_branch` on the primitive, chunked | | |

A release must not be cut while increment A's stub is live (research.md, Decision 1, release rule).

---

## Technical Context

**Language/Version**: Python 3.14 (backend); TypeScript 5.9 (frontend consumer, codegen only in this slice)

**Primary Dependencies**: FastAPI 0.131.0, graphene (GraphQL), Neo4j driver 6.2, Pydantic 2.12, Prefect (periodic sync flow)

**Storage**: Neo4j 2026.05. No schema change, no migration, no new write.

**Testing**: pytest 9.0 (unit, component via testcontainers); `CountingInfrahubDatabase` for query counts; `BusRecorder` for message-bus sends

**Target Platform**: Linux server (API workers and task workers)

**Project Type**: Web application backend slice; frontend consumes the generated types

**Performance Goals**: Database queries per page independent of branch count up to `database.query_size_limit` (three reads: repository lookup, branch list, attribute primitive; the repository lookup goes through `NodeManager`, so it is more than one statement and no absolute figure is promised); periodic sync bounded by `1 + ceil(N / 100)` queries for N branches across all repositories

**Constraints**: Read-only; zero message-bus sends and no task worker on the path; permission check covering default and non-default branches regardless of execution branch; `limit` default 40 with no hard maximum

**Scale/Scope**: Repositories with up to several hundred branches; three to four attributes per row; one root field, three GraphQL object types, one Query class, one reader component, one branch filter, one sync refactor

---

## Constitution Check

*GATE: passed before Phase 0; re-evaluated after Phase 1 design below.*

### I. Schema-Driven Integrity: PASS

No node, attribute or relationship is added. `schema/schema.graphql` and the frontend generated types
are regenerated, never edited (`uv run invoke schema.generate-graphqlschema`, `pnpm codegen`).

### II. Branch-Safe by Default: PASS

The query is read-only. It deliberately reads across branches, which is its purpose, and the branch
filter it applies per row is the standard one (own branch plus global at query time, default branch as
of `branched_from`), with the standard `branch_level DESC, from DESC, status ASC` election. The
inheritance and rebase behaviour is pinned by component tests rather than described. No merge
behaviour to specify because nothing is written.

### III. Type Safety & Explicit Contracts: PASS

The GraphQL contract is defined and shipped (increment A) before the graph read exists (increment B).
The Query class yields a frozen dataclass; the reader returns a frozen lookup; the stub's fabrication
returns the same dataclass so the resolver has one shape. The primitive takes primitives (ids, names),
not node objects, per `dev/knowledge/backend/query-pattern.md`.

### IV. Test Discipline: CONDITIONAL PASS, two accepted deviations

Component tests cover the primitive, the resolver, permissions and the sync bound; unit tests cover the
pure paging and filtering helpers. Two requirements of Principle IV are not met by this slice alone.
Neither is a reinterpretation of the principle: both are deferrals with a named owner and a tracked
subtask, recorded in Complexity Tracking.

- **E2E.** "pytest-playwright tests MUST be included for all user-facing features." This slice ships a
  GraphQL field and no UI; the user-facing surface is the Branches card, which the frontend team builds
  against this contract. The test lands with the card. The deferral is only acceptable while it is
  tracked: T059 opens the subtask that carries it.
- **Integration Docker.** "Required for features involving computed attributes." Increment C rewrites
  the structure the computed-attribute trigger gather consumes, so the requirement attaches. Component
  test T052 covers the gather call directly; T052a adds the distributed-stack test the principle asks
  for.

### V. Query Performance & Efficiency: PASS

One parameterised statement over `UNWIND $branch_names`, returning only `uuid`, `name`, `value`,
`branch` and `from` properties. No per-branch loop remains in the sync. `EXPLAIN` is run on the
primitive during increment B and the plan is pasted in the PR.

### VI. Security & Input Boundaries: PASS

All user input reaches Cypher as parameters (branch name filter, status, attribute values, ids). The
permission check is enforced at the API layer inside the resolver because the checker pipeline cannot
see hand-written root fields (research.md, Decision 4). Denial messages come from
`PermissionManager.raise_for_permission` and expose no internals.

### VII. Simplicity & Maintainability: PASS with justified additions

One resolver path instead of two. The reader component serves two callers (resolver and sync) from
increment C onward. The stub module is temporary complexity accepted for the delivery goal and is
deleted in increment B. No new dependency, no new setting.

### Post-design re-evaluation

Design artifacts introduce nothing beyond the above. The widening of `Branch.get_list`'s `limit` to
`int | None` is the only touch on legacy model code and is a signature change, not a new method on the
model.

---

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-671-cross-branch-repo-status/
├── spec.md
├── plan.md                                   # This file
├── research.md                               # Phase 0
├── data-model.md                             # Phase 1
├── quickstart.md                             # Phase 1
├── contracts/
│   ├── graphql-repository-branch-status.graphql   # SDL of the new field and types
│   ├── graphql-repository-branch-status.md        # Argument semantics, example document, example response, stub notes
│   └── core-primitive.md                          # Python API of the Query class and reader
├── checklists/requirements.md
└── tasks.md                                  # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── branch/
│   │   ├── filters.py                        # [A] BranchListFilters.sync_with_git
│   │   └── models.py                         # [A] Branch.get_list limit: int | None
│   ├── query/
│   │   ├── branch.py                         # [A] BranchNodeGetListQuery._build_raw_filter: sync_with_git condition
│   │   └── repository.py                     # [A] RepositoryBranchAttributeValue (new module); [B] RepositoryBranchAttributesQuery
│   └── repository_branch_status/
│       ├── __init__.py                       # [A]
│       ├── interface.py                      # [A] RepositoryBranchAttributesSource protocol
│       ├── models.py                         # [A] RepositoryBranchAttributes (frozen lookup, backfill)
│       └── reader.py                         # [B] RepositoryBranchAttributesReader
├── graphql/
│   ├── schema.py                             # [A] InfrahubBaseQuery.InfrahubRepositoryBranchStatus
│   ├── queries/
│   │   ├── branch.py                         # [A] sync_with_git argument on InfrahubBranchQueryList
│   │   └── repository_branch_status/
│   │       ├── __init__.py                   # [A] empty, per dev/knowledge/backend/package-init-files.md
│   │       ├── field.py                      # [A] composition root: build_attribute_source, resolver instance, Field
│   │       ├── resolver.py                   # [A] RepositoryBranchStatusResolver: validation, lookup, rows, page assembly
│   │       ├── paging.py                     # [A] pure filter / order / page helpers
│   │       ├── payload.py                    # [A] attribute payload mapping, dropdown label and colour
│   │       ├── kind_dispatch.py              # [A] RepositoryKindPolicy per repository kind
│   │       ├── permissions.py                # [A] pre-lookup and post-lookup FR-012 guard
│   │       └── stub.py                       # [A] fabricate_attribute_values; DELETED in [B]
│   └── types/
│       └── repository_branch_status.py       # [A] InfrahubRepositoryBranchStatusNode, ...Edge, ...Type
└── git/
    ├── constants.py                          # [C] REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100
    └── utils.py                              # [C] get_repositories_commit_per_branch on the reader

backend/tests/
├── unit/graphql/queries/
│   └── test_repository_branch_status.py      # [A] paging / filter / order helpers
├── component/
│   ├── core/query/
│   │   └── test_repository_branch_attributes.py   # [B] primitive: inheritance, rebase, own_value, 5 vs 200 query count
│   ├── graphql/queries/
│   │   ├── test_branch.py                    # [A] sync_with_git filter on InfrahubBranch
│   │   └── test_repository_branch_status.py  # [A] membership, paging, permissions, not-found, zero bus sends; [B] filters, inheritance, FR-008
│   ├── computed_attribute/
│   │   └── test_gather.py                    # [C] branches[branch.name] resolves for every non-global branch
│   └── git/
│       └── test_utils.py                     # [C] drop -global- key, assert 1 + ceil(N/100) bound
├── integration_docker/
│   └── test_computed_attributes.py           # [C] trigger gather over the refactored sync read
└── query_benchmark/
    └── test_repository_branch_attributes.py  # [B] primitive benchmark at the target branch counts

schema/schema.graphql                         # [A] regenerated
frontend/app/src/shared/api/graphql/generated/types.ts   # [A] regenerated (pnpm codegen)

changelog/
├── +branch-list-sync-with-git-filter.added.md  # [A]
├── +repository-branch-status-query.added.md    # [B]
└── +repository-sync-single-read.changed.md     # [C]

docs/docs/git-integration/branch-synchronization.mdx     # [B] section on the query
dev/knowledge/backend/query-pattern.md        # [B] cross-branch grouped attribute read
dev/knowledge/backend/permissions.md          # [B] in-resolver enforcement for hand-written root fields
dev/knowledge/backend/git-sync.md             # [C] sync read path
```

**Structure Decision**: Backend-only slice of a web application. Query classes stay in
`backend/infrahub/core/query/`, the reader component gets its own package under `core/` per
`.agents/rules/backend-component-design.md`, and the GraphQL query gets a package under
`graphql/queries/` because it has a resolver, pure helpers and (temporarily) a stub module. The frontend
card is built by the frontend team from the contract; only regenerated types touch `frontend/`.

Both new packages keep an empty `__init__.py`. The composition root is `field.py`, not the package
init: it is the only module that reads `registry`, builds the attribute source and constructs the
`Field`, and `schema.py` imports the field from it directly the way it already imports
`.queries.diff.tree` and `.queries.event`. Putting that wiring in `__init__.py` would both breach
`dev/knowledge/backend/package-init-files.md` and create a cycle, since the init would import
`resolver.py` for the resolver while `resolver.py` needs the source factory back from the init.

The resolver is a callable class taking the source factory as a required constructor parameter rather
than a module-level function reaching for it. That is what `.agents/rules/backend-component-design.md`
asks for, and it is also what lets the FR-008 test construct the resolver with a recording fake instead
of patching a module attribute, which `.agents/rules/testing-python.md` rules out.

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Temporary `stub.py` fabricating attribute values (increment A) | Frontend team needs a live, typed query weeks before the graph read exists | Sharing a patched SDL gives types but nothing answers the query in a running stack |
| Reader component in addition to the Query class | Two callers (resolver, sync) need the same backfill and lookup shape; Cypher and mapping stay separated per the component design rule | Calling the Query class directly from both callers duplicates the backfill and returns raw rows to the resolver |
| Permission enforced in the resolver rather than the checker pipeline | The analyzer ignores hand-written root fields and the pipeline never requires `ALLOW_ALL` | A new pipeline checker keyed on one root field name is more machinery for one query; revisit if a second cross-branch query appears |
| `Branch.get_list(limit=None)` widening | The resolver must read every in-scope branch before attribute filters apply | Passing a large literal limit is an arbitrary cap; a preceding count query adds a statement to every page |
| E2E test deferred to the Branches card (Principle IV deviation) | The user-facing surface is the card, owned by the frontend team and built against this contract | An E2E test that only fires a GraphQL document adds nothing over the component tests. Accepted only because T059 opens a tracked subtask carrying the requirement; without that it is an unrecorded miss against a MUST |
| Id tiebreaker added to `StandardNodeGetListQuery` | The unpaged chunked branch read is only correct over a total order, and metadata ordering has none today | Ordering the branch read differently from every other standard-node list would leave the shared defect in place for the next caller. The cost is that this feature changes shared machinery, so T031 names the blast radius in the PR |

---

## Implementation Strategy

### Increment A: contract stub (first PR, needs GraphQL schema sign-off)

1. `BranchListFilters.sync_with_git`, the Cypher condition, the argument on `InfrahubBranchQueryList`;
   test in `test_branch.py`.
2. `Branch.get_list` accepts `limit=None` and reads all rows through the base chunked path.
3. GraphQL types in `graphql/types/repository_branch_status.py`; resolver, wiring and field in
   `graphql/queries/repository_branch_status/`; registration on `InfrahubBaseQuery` importing
   `field.py` directly, with no re-export through `graphql/queries/__init__.py`.
4. Resolver: argument validation (`id` required, uuid or name; `limit >= 1`; `offset >= 0`),
   pre-lookup permission check (caller holds the required `view` decision on `Core/Repository` or
   `Core/ReadOnlyRepository`, else denied before any lookup), repository lookup through
   `NodeManager.get_one_by_id_or_default_filter` and kind dispatch, post-lookup FR-012 check on the
   resolved kind, branch row read, `fabricate_attribute_values`, Python order and page, `count`. A
   missing `PermissionManager` on the context is treated as denial, not as an internal error.
5. Stub visibility: `stub.py` logs one warning when it is imported into the schema and `debug` per
   call; the root field description carries "(preview: attribute values are placeholders, not yet read
   from the graph)" while the stub is live. The description is API-facing, so it names neither the
   ticket nor the increment (`.agents/rules/code-doc-style.md`).
6. Confirm `StandardNodeGetListQuery` adds an id tiebreaker when ordering by `created_at` or
   `updated_at`, so the unpaged chunked branch read stays a total order; add one if missing.
7. Regenerate `schema/schema.graphql`; run `pnpm codegen`; commit both.
8. Component tests for membership per kind, not-found, permission matrix including anonymous with and
   without a role grant, paging and count, ordering, `ref` dispatch, zero bus sends. Unit tests for
   `paging.py`. The 5-branch and 200-branch fixtures are one module-scoped fixture built with
   `Branch(...).save()` and shared with the increment B and C test files.
9. Changelog fragment for the `sync_with_git` argument on `InfrahubBranch`. It is a user-visible
   GraphQL change and ships in this increment, so the fragment does too; the query itself stays
   unlogged while its values are fabricated.
10. Hand the frontend team `contracts/graphql-repository-branch-status.md`. The card is built without
    the git-derived drift column for now.

### Increment B: graph read

1. `RepositoryBranchAttributesQuery` with the per-branch visibility predicate, its operators copied
   verbatim from `Branch.get_query_filter_path`, `WITH DISTINCT` on `(n, a, branch_name, branched_from)`
   before the election subqueries, and `br.is_isolated` honoured (`CASE WHEN br.is_isolated THEN
   br.branched_from ELSE $at END` as the default-branch window); `EXPLAIN` reviewed.
2. `RepositoryBranchAttributes` lookup and `RepositoryBranchAttributesReader`.
3. Resolver swaps the stub for the reader; attribute names come from the GraphQL selection
   (`extract_graphql_fields`), `ref` only for the read-only kind; `sync_status__value`,
   `internal_status__value` and `own_values_only` become real filters. Delete `stub.py`.
4. Component tests: inheritance at fork point, default-branch import does not move an untouched
   branch, rebase does, never-imported repository yields empty `commit`, own-value filter, attribute
   filter with count, query count equal at 5 and 200 branches, attribute-name set equals selection.
   Differential test: for every branch in the fixture, including one legacy branch with
   `is_isolated=false`, the primitive's `(value, updated_at)` equals a standard
   `NodeManager.get_one(branch=...)` read of the same attribute.
5. Query benchmark for the primitive in `backend/tests/query_benchmark/`, so the invariant this slice
   exists to establish has a regression guard beyond the one-off `EXPLAIN`.
6. Changelog fragment; docs section; knowledge docs (`query-pattern.md` for the cross-branch grouped
   read, `permissions.md` for in-resolver enforcement of a hand-written root field);
   `uv run invoke docs.generate`; `/pre-ci`.

### Increment C: periodic sync

1. `REPOSITORY_BRANCH_READ_CHUNK_SIZE` constant; `get_repositories_commit_per_branch` on the reader,
   chunked, global branch excluded; `RepositoryData` unchanged in shape.
2. Update `test_utils.py`; add the `1 + ceil(N / 100)` assertion with `CountingInfrahubDatabase`;
   assert `RepositoryData.repository` carries default-branch values for `default_branch`, `location`
   and `ref`; add a computed-attribute gather test that resolves `branches[branch.name]` for every
   non-global branch, plus the distributed-stack test Principle IV requires for a change on the
   computed-attribute path.
3. Widen `RepositoryData.branches` to `dict[str, str | None]` and follow the type through
   `populate_branch_commit`, which feeds a `dict[str, str]` today and will not type-check otherwise.
4. Changelog fragment; `dev/knowledge/backend/git-sync.md`.

### Dependency graph

```text
A (contract stub) ──> B (graph read) ──> C (periodic sync)
                 └──> frontend Branches card (frontend team, parallel with B)
```

C depends on B's reader. The frontend card depends only on A.

### Governance sign-off needed before A merges

- GraphQL schema modification: new root field `InfrahubRepositoryBranchStatus` and its three types;
  new `sync_with_git` argument on `InfrahubBranch`.
- Everything else in the spec's Governance table is ruled out (no migration, no dependency, no CI
  change, no new permission).
