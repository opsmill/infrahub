# Implementation Plan: Branch-Agnostic Reads That Return the Right Branch's Data

**Branch**: `branch-agnostic-reads` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md) | **Jira**: [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508)

**Input**: Feature specification from `dev/specs/ifc-3508-branch-agnostic-reads/spec.md`

## Summary

Fix the backend reads that run with `branch_agnostic=True` and pick an edge from the wrong branch, and fix the writes that leave a `-global-` edge and a branch edge of the same type between the same two vertices. The work ships as six PRs, in the order and with the dependencies of the spec.

The approach depends on the answer each caller needs:

- **The default branch only (PR 1):** global permissions, the login role list and the single sign-on member check run a normal read on the default branch.
- **Data on `-global-` only (PR 2):** the callers stop passing the flag.
- **Taken or present on any live branch (PRs 3, 4 and the peer match of PR 6):** the query collects the live branch windows once, then keeps a row when `any(window IN branch_windows WHERE <edges visible in the window> AND NOT EXISTS {<an edge outranks them>})`. This is the flat form of `NodeGetByHFIDQuery._build_branch_agnostic_query` at `7015435c4`.
- **One value per node (PR 6):** `NodeListGetInfoQuery` chooses one window per node. The attribute and relationship queries then rank inside that window with their existing `ORDER BY branch_level DESC, from DESC LIMIT 1`.
- **Peer exists in the read's view (PR 5):** a peer existence check on `IS_PART_OF`, rendered only for branch-aware relationships whose peer kind is branch-agnostic or a generic with a branch-agnostic implementation. A branch-agnostic relationship gets no check: the retirement check closes its `-global-` link once no live branch holds both ends (spec Clarifications, 2026-10-30).

The window logic lives once, in a new leaf module `core/query/branch_windows.py` (research R1).

## Technical Context

**Language/Version**: Python 3.14 (backend only)

**Primary Dependencies**: Neo4j 2026.05 (Cypher 25), neo4j Python driver 6.4, Pydantic 2.12, FastAPI 0.131 and the existing GraphQL layer

**Storage**: Neo4j graph. Two new graph migrations: `m083` (PR 5) and `m084` (PR 6).

**Testing**: pytest component tests with testcontainers (`backend/tests/component/`), unit tests for pure helpers (`backend/tests/unit/`), benchmarks with Neo4j `PROFILE` (`backend/tests/benchmark/`)

**Target Platform**: Infrahub API server and task workers (Linux containers)

**Project Type**: Web service backend (graph database and GraphQL API)

**Performance Goals**:

- Reads on one branch keep their database hits. FR-020 and SC-004 cover branch-aware relationships between branch-aware kinds.
- Branch-agnostic reads may cost more. They are reported, not capped.

**Constraints**:

- PR 1 is based on `stable`; PRs 2-6 on `release-1.12`.
- PRs 5 and 6 wait for PR #11220 to reach `release-1.12`.
- PRs 1 to 6 change no GraphQL schema. PR 7 adds `active_on_branches` to `InfrahubNodeMetadata`, approved on 2026-10-30.
- Two database migrations, approved in review as one migration and split by research R13, with code review still required.
- `m083` and `m084` are one-way. Downgrading after either runs is not supported, and the PR 5 and PR 6 changelog fragments say so. Each migration number is assigned when its PR is rebased on its base, after checking `GRAPH_VERSION`.
- Filters on a read on one branch keep PR #11220's query (research R12).

**Scale/Scope**:

- The cost of a window check grows as candidate rows times live branches. Benchmarks use many live branches (50, as in the HFID measurement) and past allocations.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Schema-driven integrity | No schema change. The migration keeps relationship cardinality: it changes only edges that break the database schema's edge constraints. | Pass |
| II. Branch-safe by default | Every changed query keeps branch and time filters. Ranking stays `branch_level DESC, from DESC, status ASC`, inside one window. Cross-branch effects (deleting a branch-agnostic node, the check before the delete) are documented and tested. Merge behavior is tested: the rebase and merge cases of the delete, and open question 1. | Pass, with one exception (hard delete in the migration, see Complexity Tracking) |
| III. Type safety | New helpers have type hints. Query results keep frozen dataclass `get_data()` methods. The `node_windows` map is a typed structure (data-model.md). | Pass |
| IV. Test discipline | Each PR adds component tests that fail on the current code, moved from the audit where one exists. The helper predicate gets unit tests. The migration test follows `m081`. PR 1 adds a test over HTTP. | Pass, with one exception (no E2E test, see Complexity Tracking) |
| V. Query performance | All new Cypher is parameterised. Window checks are flat (no nested `CALL` per window), following the HFID measurement. Each PR reports `PROFILE` database hits before and after. | Pass, measured per PR |
| VI. Security | PR 1 closes a privilege escalation. Error messages name pools, namespaces, branches and peers, which the user can already read, and no internal structure. | Pass |
| VII. Simplicity | One shared helper module with five existing callers. No new exception classes. IPv4 and IPv6 query bodies stay separate. | Pass |

**Post-design re-check:** unchanged. The design adds no principle violation beyond the recorded hard delete.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3508-branch-agnostic-reads/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── branch-window-helpers.md
│   └── user-visible-behavior.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── account.py                              # PR 1
│   ├── manager.py                              # PR 5 (identifiers needing the check), PR 6 (get_many windows)
│   ├── query/
│   │   ├── branch_windows.py                   # PR 3 (new)
│   │   ├── subquery.py                         # PR 5 (existence check), PR 6 (window form of filters, order in window)
│   │   ├── ipam.py                             # PR 3
│   │   ├── resource_manager.py                 # PR 3
│   │   ├── agnostic_retention.py               # PR 3
│   │   ├── branch_agnostic_retirement.py       # PR 3
│   │   ├── relationship.py                     # PR 4, PR 5, PR 6
│   │   └── node.py                             # PR 5, PR 6
│   ├── node/
│   │   ├── __init__.py                         # PR 5, PR 6 (Node.delete)
│   │   ├── delete_validator.py                 # PR 4
│   │   └── resource_manager/
│   │       ├── ip_prefix_pool.py               # PR 3
│   │       └── ip_address_pool.py              # PR 3
│   ├── relationship/model.py                   # PR 6
│   ├── schema/relationship_schema.py           # PR 5 (needs_peer_existence_check)
│   ├── convert_object_type/object_conversion.py  # PR 5
│   ├── migrations/graph/m083_convert_global_deleted_link_edges/  # PR 5 (new)
│   └── migrations/graph/m084_remove_branch_edges_of_agnostic_links/  # PR 6 (new)
├── auth/auth.py, auth/auth_groups/service.py   # PR 1
├── graphql/loaders/account.py, graphql/resolvers/resolver.py      # PR 2
├── webhook/tasks/invalidate.py                 # PR 2
├── pools/schema_number_pool_synchronizer.py, pools/schema_number_pool_upserter.py  # PR 2
└── core/integrity/object_conflict/conflict_recorder.py            # PR 2

backend/tests/
├── unit/core/query/test_branch_windows.py      # PR 3
├── unit/core/schema/test_peer_existence_check.py  # PR 5
├── component/core/test_account.py, component/permissions/, component/graphql/auth/  # PR 1
├── component/core/resource_manager/            # PR 3
├── component/core/test_node_manager_delete.py  # PR 4, PR 5
├── component/core/relationship/, component/core/test_relationship_query.py  # PR 5, PR 6
├── component/core/test_branch_agnostic_reads.py  # PR 6
├── component/core/migrations/graph/m083_convert_global_deleted_link_edges/  # PR 5
├── component/core/migrations/graph/m084_remove_branch_edges_of_agnostic_links/  # PR 6
└── benchmark/                                  # PRs 3, 5, 6

dev/knowledge/backend/database-schema.md        # PR 5, PR 6
docs/docs/deploy-manage/user-management/permissions-roles/overview.mdx  # PR 1
docs/docs/resource-manager/                     # PR 3
docs/docs/branches/branch-agnostic-data.mdx     # PRs 5 and 6
dev/knowledge/backend/query-pattern.md          # PR 3 (point to branch_windows.py)
changelog/                                      # PRs 1, 3, 4, 5, 6
```

**Structure Decision**: backend only, inside the existing `backend/infrahub/core` layout. One new module (`core/query/branch_windows.py`) and one new migration package. Tests mirror the source paths, as the constitution requires.

## Delivery by PR

Every PR starts from its base branch, carries its own tests, benchmark results and changelog fragment, and is reviewed separately. The planning artifacts live on `branch-agnostic-reads`. Each PR branch is created from its base when its work starts.

| PR | Branch (proposed) | Base | Starts when |
|---|---|---|---|
| 1 | `fix-global-permissions-default-branch-ifc-3508` | `stable` | Now |
| 2 | `global-only-reads-ifc-3508` | `release-1.12` | Now |
| 3 | `branch-windows-ip-pools-ifc-3508` | `release-1.12` | Now |
| 4 | `agnostic-delete-check-ifc-3508` | PR 3's branch, rebased on `release-1.12` once PR 3 merges | PR 3 is in review |
| 5 | `peer-existence-check-ifc-3508` | `release-1.12` | PR 3 and PR #11220 are in `release-1.12` |
| 6 | `agnostic-relationship-reads-ifc-3508` | PR 5's branch | PR 5 is in review |
| 7 | `active-on-branches-ifc-3508` | PR 6's branch | PR 6 is in review |

PR 5 must not leave a read worse than before when it ships without PR 6. Research R13 settles the order: FR-023 and the removal of shape 2 pairs (migration `m084`) move to PR 6, after its read changes, because they make a read on a branch return a peer that the branch deleted, and only PR 6 builds that peer from its chosen branch. PR 5 keeps the peer existence check, FR-021, FR-022, FR-040 and migration `m083`.

Open questions 1-3 of the spec are gates inside PRs 5 and 6 (see tasks.md). Research R7, R8 and R9 record the evidence found so far and a recommendation for each.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| Hard delete of edges in migrations `m083` and `m084` (constitution II allows hard delete only for branch deletion) | The edges of both shapes break the edge constraints in `database-schema.md`: no `active` edge precedes the `deleted` edge on its branch or on the default branch. Shape 1 is replaced by edges with the same `from`, so history is kept. | Leaving the edges for reads to ignore was rejected in review, because every read would need to skip them forever. |
| No E2E test (constitution IV requires E2E tests for user-facing features) | The changes are backend reads and writes with no new user interface. Component tests cover each behavior, and PR 1 adds a test over HTTP to `/graphql/<branch>`. | An E2E test would cover the same reads through the browser at a much higher cost. The brief does not require one; this exception needs the reviewer's approval, and PR 1 gets one E2E test if it is refused. |
| A shared Cypher fragment module (`query-pattern.md` prefers inline Cypher) | Five consumers, one of which computes a different window (research R1). FR-013 requires one definition. | Fixing each copy in place keeps five definitions that can drift again. |
