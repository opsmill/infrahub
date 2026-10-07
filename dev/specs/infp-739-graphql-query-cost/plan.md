# Implementation Plan: Estimated and Actual Cost of GraphQL Queries for Each Relationship Field

**Branch**: `fac/graphql-proactive-analyzer-rrake` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md) | **Jira**: [INFP-739](https://opsmill.atlassian.net/browse/INFP-739)

**Input**: Feature specification from `dev/specs/infp-739-graphql-query-cost/spec.md`

## Summary

An engineer who diagnoses a slow artifact query, or writes a new one, gets for each relationship field the expected, worst-case and actual nodes, resolver calls and database rows. They get the actual counts by sending `X-Infrahub-Query-Cost: details` with a request to `/graphql` or `/api/query`. They get the estimate without running the query from a new `cost_estimate` field on `InfrahubGraphQLQueryReport`, which also gains an optional `variables` argument and a read-permission check.

Technical approach (details in [research.md](research.md)):

- A scheduled Prefect flow reads main once a day in pages by node `uuid`. It stores in the cache, for each concrete kind, the label count and the spread of peers for each relationship side, with a version pointer (D5, D7, D8).
- A pure estimator walks a tree built from the GraphQL analyzer's query tree. When every declared variable has a value, it first counts the top-level nodes and the fields directly under them on the request's branch and time. Below that, it uses the statistics for the expected figure and a bound from per-node peer counts for the worst case (D9, D10).
- A recorder in a `ContextVar`, set only for requests with the header, counts resolver calls and nodes in the relationship resolver wrappers and database rows in `InfrahubDatabase.execute_query_with_metadata`. No middleware is added (D3).

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: FastAPI 0.131, graphene 3.4 and graphql-core 3.2, Prefect (task manager), aiodataloader, Pydantic 2.12. No new dependency.

**Storage**: Neo4j (read only, for counting and the refresh). The statistics live in the existing cache (`InfrahubCache`, Redis by default). No graph schema change and no migration.

**Testing**: pytest. Unit tests for the estimator and the statistics; component tests (testcontainers Neo4j) for the refresh, the endpoints and the report. The customer-shaped data set for SC-001 lives in `infrahub-private-tests`.

**Target Platform**: Infrahub API server and task worker (Linux containers).

**Project Type**: Web service (backend only; no UI change).

**Performance Goals**:

- Requests without the header run the same number of database queries as today (SC-002).
- A request with the header runs at most one extra database query for each top-level field and one for each relationship field directly under it (SC-003).

**Constraints**:

- No per-field middleware (`dev/knowledge/backend/graphql-execution.md`).
- No refresh query holds more than one page of nodes (`query_size_limit`, 5,000 by default).
- Each cache value stays below the 1 MB default limit of the NATS cache driver.

**Scale/Scope**: the customer case in the brief: 4,866 devices, 215,764 interfaces, 58 logical networks, a query that made 183,000 single-relationship resolver calls.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Schema-Driven Integrity | Pass | The statistics are keyed by schema kinds and relationship identifiers. No schema kind is added and no generated file is edited by hand; `schema/schema.graphql` and the frontend GraphQL types are regenerated. |
| II. Branch-Safe by Default | Pass, with a documented exception | The counted first step reads the request's branch and `at` time. The statistics describe main only, and label counts include deleted nodes and nodes of other branches. The spec accepts this under Assumptions, and every estimate states its branch, time and whether the worst case is a bound. |
| III. Type Safety & Explicit Contracts | Pass | The header, the `extensions` content and the report fields are defined in [contracts/](contracts/) before implementation. Internal values are frozen dataclasses; the response content is a Pydantic model. Database results go through `get_data()`. |
| IV. Test Discipline | Pass, with a documented exception | Unit and component tests for every FR (research D12). No pytest-playwright test, because the feature adds no UI (see Complexity Tracking). |
| V. Query Performance & Efficiency | Pass | Counting queries use parameters and the `node_uuid` and `rel_identifier` indexes, and run only when the header or the `cost_estimate` field asks for them. The refresh pages by `uuid` and returns only IDs and counts. |
| VI. Security & Input Boundaries | Pass | The `cost_estimate` field runs the same permission checker pipeline as `/graphql` on the submitted query. Variables are coerced by graphql-core before use. Kind labels in the label-count query come from the schema, not from user input. |
| VII. Simplicity & Maintainability | Pass | Reuses `RelationshipGetPeerQuery`, `NodeGetListQuery`, `CountNodesByKindsQuery`, the cache adapter and the workflow catalogue. The histogram is stored in full although P1 reads only bucket maximums and the mean; the brief chose this and FR-009 tests every statistic. |

**Governance gates (AGENTS.md "Ask First")**, as recorded in the brief:

- GraphQL schema change: crossed (`variables` argument and `cost_estimate` field on the report).
- API contract change: crossed (new request header and `extensions` content).
- Authorization change: crossed (read-permission check on the report's estimate). No new permission.
- Database schema or migration, new dependency, CI/CD change in `opsmill/infrahub`: not crossed.

**Post-design re-check**: the design in Phase 1 keeps every row above. The only new process is the daily flow, which is registered through the existing workflow catalogue.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-739-graphql-query-cost/
├── spec.md
├── plan.md                 # this file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── cost-details-header.md
│   ├── cost-details.schema.json
│   └── graphql_query_report.graphql
├── checklists/requirements.md
└── tasks.md                # Phase 2 (speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/graphql/cost/            # new package, empty __init__.py
├── constants.py          # header name and value, cache keys, number of listed nodes (20)
├── models.py             # frozen dataclasses: statistics, histogram, tree, estimate, actual counts
├── histogram.py          # builds a RelationshipSideStatistics from per-node peer counts, page by page
├── statistics_store.py   # cache layout (pointer + one key per kind), in-process snapshot
├── queries.py            # label counts, refresh degree page, first-step nodes, first-step peers
├── collector.py          # StatisticsCollector: reads main in pages, builds KindStatistics
├── tree.py               # CostTreeField from the analyzer tree and coerced argument values; paths
├── first_step.py         # counts the top-level nodes and the fields directly under them
├── estimator.py          # pure expected and worst-case estimate over the tree
├── recorder.py           # ContextVars, QueryCostRecorder, helpers used by resolvers and the database
├── details.py            # Pydantic response models; merges the estimate and the actual counts
├── service.py            # QueryCostEstimator: tree → first step → statistics → estimate
└── tasks.py              # @flow refresh_query_cost_statistics

backend/infrahub/graphql/analyzer.py                       # GraphQLQueryNode: response key, relationship ref, count selection
backend/infrahub/graphql/app.py                            # header, recorder, extensions on /graphql
backend/infrahub/api/query.py                              # header, recorder, extensions on /api/query
backend/infrahub/graphql/resolvers/resolver.py             # record calls and nodes in the relationship and list wrappers
backend/infrahub/graphql/resolvers/ipam.py                 # record calls and nodes for IP list queries
backend/infrahub/graphql/queries/graphql_query_report.py   # variables argument, cost_estimate field, permission check
backend/infrahub/database/__init__.py                      # rows for the current field in execute_query_with_metadata
backend/infrahub/workflows/catalogue.py                    # GRAPHQL_COST_STATISTICS_REFRESH (daily cron)

backend/tests/unit/graphql/cost/                           # estimator, histogram, tree, paths, store layout
backend/tests/component/graphql/cost/                      # refresh, endpoints, report, permissions, branch, SC-002/003

schema/schema.graphql                                      # regenerated
frontend/app/src/shared/api/graphql/generated/             # regenerated (graphql-env.d.ts, graphql-cache.d.ts)
docs/docs/development-resources/graphql/query-cost.mdx     # user documentation
dev/knowledge/backend/graphql-query-cost.md                # architecture note
changelog/+graphql-query-cost.added.md                     # towncrier fragment
```

**Structure Decision**: backend only. The new code lives in one package, `infrahub.graphql.cost`, so that the request path, the report and the flow share the models and the estimator. Existing modules change only where they must call the recorder or expose the new contract.

## Design Notes

### Request with the header (`/graphql`, `/api/query`)

1. The handler reads `X-Infrahub-Query-Cost`. If the value is `details` and the analyzer reports no mutation, it builds a `QueryCostRecorder` and sets it in the recorder `ContextVar`.
2. After the existing permission check, `QueryCostEstimator.estimate(...)` builds the tree, runs the first-step queries (counted under `estimate_queries`), loads the statistics snapshot and computes the estimate.
3. The query executes unchanged. Resolver wrappers record calls and nodes; `execute_query_with_metadata` records rows for the field in the field `ContextVar`.
4. The handler merges the estimate and the recorder into `extensions.query_cost` and resets the `ContextVar`.

Requests without the header skip steps 1, 2 and 4; step 3 reads one `ContextVar` that returns `None`.

### Report

`resolve_graphql_query_report` keeps returning `targets_unique_nodes`. The new `cost_estimate` field has its own resolver: it rejects mutations, runs the permission checker pipeline on the submitted query's analyzer, coerces `variables`, and calls the same `QueryCostEstimator` without a recorder.

### Refresh flow

`refresh_query_cost_statistics` builds a `StatisticsCollector` with a database session and the main schema branch, reads label counts and active counts, reads each relationship side in pages, then writes the new version through `StatisticsStore.publish(...)`. The flow returns nothing (`dev/guidelines/backend/prefect-payloads.md`).

### Branch and time

- The counted first step uses the request's branch and `at`.
- The statistics always describe main. `worst_case_is_bound` is true only when the request reads main with no `at` time.

## Risks

- **Rows of shared batches**: a `NodeDataLoader` batch that serves several cardinality-one fields is counted for the first field. The contract states this.
- **Refresh duration on large data**: one query for each page of each relationship side. On the customer data this is several hundred queries for interfaces alone. If it is too slow, read all relationships of a kind in one paged query (research D7, alternatives).
- **Correlation between steps**: the statistics assume that peers at one step do not depend on the step before. The customer data shows strong correlation (89 % of link endpoints have a link in the traced network, against 51 % overall). Counting the first step reduces the error; SC-001 in `infrahub-private-tests` measures what is left.
- **Statistics age**: the default daily refresh is a recommendation. The acceptable age is open question 1 of the spec.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| No pytest-playwright test (Principle IV requires one for user-facing features) | The feature adds no UI. Its users call `/graphql`, `/api/query` and the report directly. | A browser test would only send HTTP requests that the component tests already send. |
| Statistics describe main only (Principle II) | The brief decided it: statistics from one branch, refreshed once, used by every branch. | Statistics for each branch multiply the refresh cost by the number of branches. Adjusting with the branch diff is out of scope in the brief. |
