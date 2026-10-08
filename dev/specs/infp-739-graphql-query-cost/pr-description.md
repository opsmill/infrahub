# Estimated and actual cost of GraphQL queries for each relationship field

<!--
Draft written from the plan, before the implementation. Before the PR leaves draft:
- check every identifier, file path, figure and default below against the diff, and state what landed (AGENTS.md "Always Do")
- replace "Not known yet" in the four result sections at the end
-->

Jira: [INFP-739](https://opsmill.atlassian.net/browse/INFP-739). A GitHub issue for this work is not known.

This PR stays in draft until a maintainer confirms the three changes listed under "Changes that need a maintainer's confirmation".

## TL;DR

- Problem: an engineer who diagnoses a slow artifact or generator query cannot view how many nodes, resolver calls, and database rows each relationship field causes. Infrahub records only the depth and height of a query, so finding the field that multiplies the rows requires a trace of the run.
- What is needed:
  - a request header that returns, for each relationship field, the actual nodes, resolver calls, and database rows next to an expected and a worst-case estimate
  - a daily background task that computes peer statistics from main, which the estimate uses
  - the same estimate from the `InfrahubGraphQLQueryReport` query, without running the submitted query
- Not decided yet:
  - a maintainer's confirmation of a GraphQL schema change, an API contract change, and an authorization change
  - how old the statistics may be, which the refresh schedule sets
  - whether `infrahub-private-tests` needs a CI change to run the synthetic data set

## Why engineers cannot find the field that causes the work of a query

A team that renders artifacts or runs generators from GraphQL queries over a large data set cannot tell, before or after a run, how much work a query causes or which relationship field causes it. The work depends mostly on how many peers each relationship returns, and that number varies widely between nodes.

On one customer's `CablingPlanLogical` query, an estimate from averages gives about 23,000 single-relationship resolver calls, against an actual 183,000. The trace these figures come from is not linked, and the customer is not named in the sources ([spec.md, "Summary"](spec.md#summary)).

Goal: the person who diagnoses or writes a query views, for each relationship field, the expected, worst-case, and actual work.

Out of scope for this PR ([spec.md, "Out of Scope"](spec.md#out-of-scope)):

- limiting how many artifact and generator runs happen at once by their total estimated cost
- sizing Cypher pages and loader batches from the estimate
- Prometheus metrics, a single combined cost figure, and admission based on cost
- estimating the reads caused by display labels rendered from templates, profile values, and permission filtering
- mutations

## Changes that need a maintainer's confirmation

[AGENTS.md](../../../AGENTS.md), under "Boundaries → Ask First", lists changes to ask about before they land. This PR makes three of them. The INFP-739 brief records them as decided ([tasks.md, "Before the PR leaves draft"](tasks.md#before-the-pr-leaves-draft)). A maintainer, please confirm each one by ticking it or by replying on this PR:

- [ ] GraphQL schema change: an optional `variables` argument and a `cost_estimate` field on `InfrahubGraphQLQueryReport` ([contracts/graphql_query_report.graphql](contracts/graphql_query_report.graphql)). The existing fields and arguments do not change.
- [ ] API contract change: the `X-Infrahub-Query-Cost` request header on `/graphql` and `/api/query`, and the `extensions.query_cost` content of the response ([contracts/cost-details-header.md](contracts/cost-details-header.md), [contracts/cost-details.schema.json](contracts/cost-details.schema.json)).
- [ ] Authorization change: a read-permission check on the estimate of the report. Selecting `cost_estimate` requires read permission, on the request's branch, for every kind in the submitted query. No new permission is added.

Not crossed, according to [plan.md, "Constitution Check"](plan.md#constitution-check):

- database schema or migration change: the statistics are stored in the cache, not in the graph
- new dependency
- CI/CD workflow change in `opsmill/infrahub`; whether `infrahub-private-tests` needs a CI change is not known

[CLAUDE RECOMMENDED – based on the "Ask First" list of [backend/AGENTS.md](../../../backend/AGENTS.md)] Also confirm that no new root query and no new database index is needed. The change adds a field and an argument to the existing `InfrahubGraphQLQueryReport` query, and the plan names only the existing `node_uuid` and `rel_identifier` indexes. The plans under "Query plans of the refresh and first-step queries on 100,000 interfaces" use only the existing `node_uuid`, `node_kind`, and `rel_identifier` indexes and the label counts that Neo4j keeps.

## Changes for people who call `/graphql`, `/api/query`, and the report

Behavior, as defined in [contracts/](contracts/):

- A request to `/graphql` or `/api/query` with `X-Infrahub-Query-Cost: details` gets `extensions.query_cost` in the response. It lists, for each relationship field, the actual nodes, resolver calls, and database rows of the request, next to an expected and a worst-case estimate of the same figures.
- A request without the header gets the same response as today, with no `extensions` key, and runs the same number of database queries.
- A mutation sent with the header gets the same response as today.
- `InfrahubGraphQLQueryReport` accepts an optional `variables` argument and returns `cost_estimate` without running the submitted query:
  - with `variables`, the top-level nodes and the relationship fields directly under them (the first step) are counted on the request's branch and time
  - without `variables`, every figure comes from the statistics, and only the current label counts are read
- A scheduled flow, `graphql-cost-statistics-refresh`, computes the statistics from main once a day. Until its first run, every field has the reason "no statistics" and still has its actual counts.

How it works ([plan.md, "Summary"](plan.md#summary), [research.md](research.md)):

- The refresh flow reads main in chunks of node IDs. For each concrete kind, it stores in the cache the label count and the spread of peers for each relationship side, with a version pointer (research D5, D7, and D8).
- An estimator with no database access computes the expected figure from the mean number of peers, and the worst case from a bound built from per-node peer counts (research D10).
- A recorder stored in a `ContextVar`, set only for requests with the header, counts resolver calls and nodes in the relationship resolver wrappers, and database rows in `InfrahubDatabase.execute_query_with_metadata`. No GraphQL middleware is added (research D3).

What stays the same:

- no database schema change and no migration
- no new dependency
- no UI change
- the existing `targets_unique_nodes` field of the report

## Known limits of the counts and the estimate

- Rows of shared batches: a `NodeDataLoader` batch that serves several cardinality-one fields with the same selection is counted for the field whose resolver started the batch ([contracts/cost-details-header.md, "Counting rules"](contracts/cost-details-header.md#counting-rules)). Splitting the loaders by field would change how many queries run with the header (research D3).
- Refresh duration on large data: the refresh runs one query for each chunk of IDs of each relationship side. On the customer data, this is several hundred queries for interfaces alone. If the refresh is too slow, the plan is to read all relationships of a kind in one query for each chunk ([plan.md, "Risks"](plan.md#risks)).
- Correlation between steps: the statistics assume that the peers at one step do not depend on the step before. The customer data shows strong correlation: 89% of link endpoints have a link in the traced network, against 51% overall. Counting the first step reduces the error, and the accuracy check in `infrahub-private-tests` measures what is left.
- Reading the IDs of a kind during the refresh: each page of `KindActiveNodeIdsQuery` reads and sorts every node of the kind, so the read grows with the square of the kind's size ("Query plans of the refresh and first-step queries on 100,000 interfaces").
- Age of the statistics: the daily refresh is a default. How old the statistics may be is open question 1 of the spec.
- Statistics of main only: on another branch or at a past time, the worst case is labelled with its source and is not an upper bound (`worst_case_is_bound` is false) ([plan.md, "Branch and time"](plan.md#branch-and-time)).

[spec.md, "Edge Cases"](spec.md#edge-cases) lists the other cases where the estimate is less reliable. In each one, the actual counts stay correct.

## Suggested review order and code that every request runs through

[CLAUDE RECOMMENDED – based on the delivery order in [plan.md](plan.md#delivery-order)] Review in the order the work was delivered:

1. The contracts in [contracts/](contracts/).
2. The recorder and the actual counts:
   - `backend/infrahub/graphql/cost/recorder.py` and `details.py`
   - the changes to `backend/infrahub/database/__init__.py`, `backend/infrahub/graphql/resolvers/`, `backend/infrahub/graphql/app.py`, and `backend/infrahub/api/query.py`
3. The statistics refresh and store: `histogram.py`, `queries.py`, `collector.py`, `statistics_store.py`, and `tasks.py` in `backend/infrahub/graphql/cost/`, and the entry in `backend/infrahub/workflows/catalogue.py`.
4. The estimate: the changes to `backend/infrahub/graphql/analyzer.py`, then `tree.py`, `first_step.py`, `estimator.py`, and `service.py` in `backend/infrahub/graphql/cost/`.
5. The report: `backend/infrahub/graphql/queries/graphql_query_report.py`.
6. Documentation and generated files:
   - `docs/docs/development-resources/graphql/query-cost.mdx`, `dev/knowledge/backend/graphql-query-cost.md`, and the changelog fragment
   - `schema/schema.graphql` and `frontend/app/src/shared/api/graphql/generated/`, which are regenerated

Changed code that every request runs through, with or without the header:

- `InfrahubDatabase.execute_query_with_metadata`, which every database query runs through
- the relationship and list resolver wrappers in `backend/infrahub/graphql/resolvers/resolver.py` and `backend/infrahub/graphql/resolvers/ipam.py`

The permission check on `cost_estimate` reuses the permission checker pipeline of `/graphql`, so a denied account gets the error that running the query returns ([research.md, "D11"](research.md#d11-the-report-query)).

## Commands and steps to test the change

Automated tests, run from `backend/` (file list from [tasks.md](tasks.md)):

```bash
cd backend
uv run pytest tests/unit/graphql/cost/
uv run pytest tests/component/graphql/cost/ tests/component/api/test_query_cost_header.py tests/component/graphql/queries/test_graphql_query_report.py tests/component/graphql/queries/test_graphql_query_report_permissions.py
```

Manual check on a development stack with the demo data: follow [quickstart.md](quickstart.md). It covers:

- fields without statistics before the first refresh
- the refresh
- requests with and without the header on `/graphql`
- a stored query run through `/api/query` with the header
- the report with and without `variables`
- the permission check
- mutations

The results are under "Results of the quickstart steps on a development stack" and "Checks run before review".

## Impact on existing clients, performance, and deployment

- Backward compatibility: requests without the header, and report calls that do not select `cost_estimate`, behave as today. Clients that do not read `extensions` are not affected ([research.md, "D2"](research.md#d2-where-the-cost-details-go-in-the-response)).
- Performance ([plan.md, "Technical Context"](plan.md#technical-context) and ["Memory"](plan.md#memory)):
  - requests without the header run the same number of database queries as today
  - a request with the header runs at most one extra database query for each top-level field, plus one for each relationship field directly under it
  - the refresh reads every node of main once a day, in chunks of `query_size_limit` IDs (5,000 by default)
  - each process keeps a copy of the statistics in memory, about 2 KB for each relationship side, so about 10 MB for a schema with 5,000 sides; a process loads it on the first request that needs an estimate, not at startup
- Configuration: no new setting. The refresh schedule is fixed in code ([research.md, "D8"](research.md#d8-refresh-schedule)).
- Deployment: no migration. Until the first refresh runs, every estimate has the reason "no statistics". Operators pause the schedule of the `graphql-cost-statistics-refresh` deployment, or start an extra run, from the task manager.

## Open questions

From [spec.md, "Open Questions"](spec.md#open-questions):

1. How old may the statistics be? The interval of the scheduled refresh sets this.
2. Does `infrahub-private-tests` need a CI change to run the synthetic data set?
3. Which trace and which customer do the `CablingPlanLogical` figures come from? Neither is linked yet.
4. For limiting concurrent renders later: does the last actual cost of a stored query for the same target predict better than the estimate?

Whether the Python SDK needs a way to send the header is not known either ([spec.md, "Assumptions"](spec.md#assumptions)).

## Query plans of the refresh and first-step queries on 100,000 interfaces

Checked for [tasks.md](tasks.md), T043, and constitution Principle V ([dev/constitution.md](../../constitution.md)).

### Database and data used for the plans

- Neo4j 2026.05.0 enterprise, the database container of a development stack built from this branch (`uv run invoke dev.build`, then `dev.start`). The quickstart steps below ran on the same stack before the seeding.
- The demo data, plus 100,000 `InfraInterfaceL3` nodes written in Cypher with the vertex and edge shape Infrahub writes:
  - the kind labels and the `uuid`, `kind`, `namespace` and `branch_support` properties
  - an active `IS_PART_OF` edge to `Root` on main
  - a `name` attribute
  - a `device__interface` relationship to one of the 30 demo devices, about 3,340 new interfaces for each device
- Totals: 100,190 `InfraInterfaceL3` nodes, 102,492 `Node` vertices, and 100,730 `Relationship` vertices named `device__interface`.
- Indexes in the plans, as `SHOW INDEXES` names them: `node_range_node_uuid_uuid` (`Node.uuid`, the `node_uuid` index of Infrahub), `node_range_node_kind_kind` (`Node.kind`) and `node_range_rel_identifier_name` (`Relationship.name`).
- The query text and parameters come from instantiating the query classes with a chunk and ID limit of 5,000 (`query_size_limit`), then running them with `PROFILE`. The plans therefore show the real rows and database hits next to the planner's estimate. The index statistics were resampled before the plans.
- Each plan below keeps only the operators that read data.

### Results of the plans

- `RelationshipSideDegreeQuery`, `n.uuid IN $node_ids`:
  - with the 30 device IDs, the lookup starts from the `node_uuid` index
  - with a chunk of 5,000 interface IDs, the lookup started from the `node_kind` index and read all 100,190 interfaces to keep the 5,000 of the chunk. The refresh runs this query for each chunk of each relationship side, so it read every node of the kind once for each chunk.
  - this PR adds `USING INDEX n:Node(uuid)` to the query; with it, the chunk reads its 5,000 nodes only
- Label counts, in `KindLabelCountQuery` and in `FirstStepNodesQuery`: each count scanned every node of the label. A request on `InfraDevice` with an `interfaces` field scanned the 100,190 interfaces, a kind it does not count but whose total it needs. This PR computes each count before the kind name is added to the row, and Neo4j then reads it from its count store with one database hit.
- `FirstStepNodesQuery` reads the nodes of its top-level field's kind only: a scan of the 30 devices for `InfraDevice(name__value: ...)`. On the 100,000-node kind with an order and a limit, it reads every `IS_PART_OF` edge of main and the `name` value of each interface. That is the plan of the list query of the field, which `FirstStepNodesQuery` is built on.
- `FirstStepPeerCountQuery`:
  - with 1 device ID, the lookup starts from the `node_uuid` index and reads the 3,347 edges of that device
  - with 5,000 interface IDs, the lookup starts from the `rel_identifier` index and reads all 100,730 `device__interface` relationships to keep those of the 5,000 source nodes
  - the query reuses the first `MATCH` of `RelationshipGetPeerQuery`, which the peer resolver of every relationship field runs, so this PR does not change it
- `KindActiveNodeIdsQuery` starts from the `node_kind` index, not from a label scan. Each page reads and sorts every node of the kind: the page at offset 95,190 sorted 100,190 rows to return 5,000. Reading the IDs of a kind of N nodes therefore reads about N × N ÷ 5,000 index entries, 2.1 million for the 100,190 interfaces.

The refresh flow on the seeded database, one run before and one after the two query changes (the task workers were restarted in between, and the times come from the flow's log on a development host):

- before: version 2, 27.2 seconds, 888 database queries
- after: version 3, 14.5 seconds, 888 database queries
- for comparison, on the demo data alone: version 1, 1.6 seconds, 455 database queries

### Plan of `RelationshipSideDegreeQuery` for a chunk of 5,000 interface IDs

Before this PR's change:

```text
Apply                                                        rows=5,000
  Expand(All)  (n)-[:IS_RELATED]->(rl)                       rows=5,000    db hits=5,000
    Filter  n.uuid IN $node_ids                 est=217      rows=5,000    db hits=100,190
      NodeIndexSeek  Node(kind) WHERE kind = $kind
                                                est=2,329    rows=100,190  db hits=100,191
  Top  latest edges of each node, LIMIT 1                    rows=5,000
    Expand(All)  (rl)<-[r2:IS_RELATED]-(peer)                rows=10,000   db hits=15,000
      Expand(Into)  (n)-[r1:IS_RELATED]->(rl)                rows=5,000    db hits=10,000
```

With `USING INDEX n:Node(uuid)`:

```text
Apply                                                        rows=5,000
  Expand(All)  (n)-[:IS_RELATED]->(rl)                       rows=5,000    db hits=10,000
    Filter  n.kind = $kind                      est=217      rows=5,000    db hits=10,000
      NodeIndexSeek  Node(uuid) WHERE uuid IN $node_ids
                                                est=9,528    rows=5,000    db hits=10,000
  Top  latest edges of each node, LIMIT 1                    rows=5,000
    Expand(All)  (rl)<-[r2:IS_RELATED]-(peer)                rows=10,000   db hits=15,000
      Expand(Into)  (n)-[r1:IS_RELATED]->(rl)                rows=5,000    db hits=10,000
```

### Plan of `RelationshipSideDegreeQuery` for the 30 device IDs

The same before and after the change:

```text
Apply
  Expand(All)  (n)-[:IS_RELATED]->(rl)                       rows=101,062  db hits=101,092
    Filter  n.kind = $kind                                   rows=30
      NodeIndexSeek  Node(uuid) WHERE uuid IN $node_ids
                                                est=100      rows=30       db hits=60
  Top  latest edges of each node, LIMIT 1                    rows=100,730
    Expand(All)  (rl)<-[r2:IS_RELATED]-(peer)                rows=201,460  db hits=302,190
```

### Plan of `FirstStepNodesQuery` for `InfraDevice(name__value: "atl1-core1")` and its interfaces

The nodes, the same before and after the change:

```text
Apply
  Expand(All)  (n)-[r:IS_PART_OF]->(root)                    rows=30       db hits=30
    NodeByLabelScan  n:InfraDevice              est=30       rows=30       db hits=31
  (for each device) Expand(All)  (n)-[:HAS_ATTRIBUTE]-(i)    rows=240      db hits=270
                    Expand(All)  (i)-[:HAS_VALUE]-(av)       rows=30       db hits=60
```

The label counts of `InfraDevice`, `InfraInterfaceL2` and `InfraInterfaceL3`, before the change:

```text
NodeByLabelScan  labelled:InfraDevice                        rows=30       db hits=31
NodeByLabelScan  labelled:InfraInterfaceL2                   rows=510      db hits=511
NodeByLabelScan  labelled:InfraInterfaceL3                   rows=100,190  db hits=100,191
```

After the change, the same in `KindLabelCountQuery`:

```text
NodeCountFromCountStore  count( (:InfraDevice) )             rows=1        db hits=1
NodeCountFromCountStore  count( (:InfraInterfaceL2) )        rows=1        db hits=1
NodeCountFromCountStore  count( (:InfraInterfaceL3) )        rows=1        db hits=1
```

### Plan of `FirstStepNodesQuery` for `InfraInterfaceL3(limit: 5)`

After the change; before it, the label count was a scan of 100,190 rows:

```text
Top  name value ASC, n.uuid ASC LIMIT $first_step_limit + $first_step_offset
                                                             rows=5
  Apply
    Distinct, Union of
      DirectedRelationshipIndexSeek  IS_PART_OF(branch) WHERE branch IN $branch0
                                                est=85,950   rows=102,484  db hits=102,486
      DirectedRelationshipIndexSeek  IS_PART_OF(branch) WHERE branch IN $branch0
                                                est=85,950   rows=102,484  db hits=102,486
    (for each interface) Expand(All)  (n)-[:HAS_ATTRIBUTE]-(attribute)
                                                             rows=102,090  db hits=202,280
                         Expand(All)  (attribute)-[:HAS_VALUE]-(last)
                                                             rows=100,190  db hits=200,380
NodeCountFromCountStore  count( (:InfraInterfaceL3) )        rows=1        db hits=1
```

### Plans of `FirstStepPeerCountQuery`

`InfraDevice/interfaces` for 1 device:

```text
Apply
  Expand(All)  (source_node)-[:IS_RELATED]->(rl)             rows=3,347    db hits=3,347
    NodeIndexSeek  Node(uuid) WHERE uuid = $source_ids[0]
                                                est=1        rows=1        db hits=2
  Top  latest edges of each peer, LIMIT 1                    rows=3,340
    Expand(All)  (rl)<-[r2:IS_RELATED]-(peer)                rows=6,680    db hits=10,020
```

`InfraInterfaceL3/device` for 5,000 interfaces:

```text
Apply
  Filter  source_node.uuid IN $source_ids       est=404      rows=5,000    db hits=412,920
    Expand(All)  (rl)<-[:IS_RELATED]-(source_node)
                                                est=4,347    rows=201,460  db hits=201,460
      NodeIndexSeek  Relationship(name) WHERE name = $rel_identifier
                                                est=2,174    rows=100,730  db hits=100,731
  Top  latest edges of each peer, LIMIT 1                    rows=5,000
    Expand(All)  (rl)<-[r2:IS_RELATED]-(peer)                rows=10,000   db hits=15,000
```

### Plans of `KindActiveNodeIdsQuery` for the first and the last page

Offset 0:

```text
Skip  $page_offset                                           rows=5,000
  Top  n.uuid, elementId(n) LIMIT $page_limit + $page_offset rows=5,000
    NodeIndexSeek  Node(kind) WHERE kind = $kind
                                                est=2,329    rows=100,190  db hits=100,191
```

Offset 95,190:

```text
Skip  $page_offset                                           rows=5,000
  Top  n.uuid, elementId(n) LIMIT $page_limit + $page_offset rows=100,190
    NodeIndexSeek  Node(kind) WHERE kind = $kind
                                                est=2,329    rows=100,190  db hits=100,191
```

### Changes not made in this PR

- [CLAUDE RECOMMENDED – based on the plan of `FirstStepPeerCountQuery` for 5,000 interfaces] Hold the first `MATCH` of `RelationshipGetPeerQuery` on the `node_uuid` index, for example with `USING INDEX source_node:Node(uuid)`, in a separate PR. Every relationship field's peer query runs that `MATCH`, so the change needs its own `PROFILE` of small and large batches of source IDs.
- [CLAUDE RECOMMENDED – based on the two plans of `KindActiveNodeIdsQuery` and a `PROFILE` of two alternatives on the same data] Read the IDs and active flags of a kind in one query without `ORDER BY` and `SKIP`. On the 100,190 interfaces:
  - paging by key (`n.uuid > $after ORDER BY n.uuid LIMIT 5,000`) still started from the `node_kind` index and read all 100,190 interfaces for one page
  - one read of every ID of the kind without a sort cost 200,381 database hits, against about 2.1 million index entries for the 21 pages of the current query
  - the flow already keeps every ID of a kind in memory, so the cost of the change is in the size of the query's result, which is not measured here

## Results of the quickstart steps on a development stack

Steps 1 to 8 of [quickstart.md](quickstart.md) ([tasks.md](tasks.md), T044) ran on 2026-10-08 on a development stack built from commit 9f5b34d91c (`uv run invoke dev.build`, then `dev.start`), with the demo data loaded by `dev.load-infra-schema` and `dev.load-infra-data` (30 devices). The requests used the admin token of the development stack, except in step 7. The query changes of this PR came after these steps; they change how the database finds the nodes, not the figures returned.

Every step gave the expected result. Two instructions of the quickstart were wrong and are corrected in this PR:

- Step 2: the Python command that calls the flow failed with `InitializationError`, because the flow reads the default branch from the registry that a task worker initializes. Run in the server container of a development stack, `uv run` also replaced the `.venv` of the repository, which the container mounts at `/source`. The quickstart now runs the deployment with `prefect deployment run`.
- Prerequisites: the quickstart named the `demo.*` tasks to load the data. On a development stack, the matching tasks are `dev.load-infra-schema` and `dev.load-infra-data`.

The quickstart also now says how to create the stored query of step 5 and the account of step 7, which the demo data does not have, and that the automated tests run from `backend/`.

### Step 1: a request with the header before the first refresh

`POST /graphql` with `X-Infrahub-Query-Cost: details` and the query of step 1 returned, trimmed:

```json
{
  "estimate_mode": "counted_first_step",
  "statistics": null,
  "fields": [
    {"path": "InfraDevice", "estimate": {"expected": null, "worst_case": null, "source": null, "reason": "no statistics"},
     "actual": {"nodes": 5, "resolver_calls": 1, "database_rows": 15}},
    {"path": "InfraDevice/interfaces", "estimate": {"expected": null, "worst_case": null, "source": null, "reason": "no statistics"},
     "actual": {"nodes": 94, "resolver_calls": 5, "database_rows": 282}}
  ],
  "estimate_queries": {"queries": 2, "database_rows": 2},
  "unattributed": {"queries": 0, "database_rows": 0}
}
```

Matches the expectation: `statistics` is null, each field has the reason "no statistics" and filled actual counts. The 94 interfaces are the sum of the five devices' interfaces (6, 6, 15, 15 and 52).

### Step 2: the statistics refresh

The command of the quickstart failed, as described above. `prefect deployment run "graphql-cost-statistics-refresh/graphql-cost-statistics-refresh" --watch`, run in the server container, completed. The flow logged "Published version 1 of the GraphQL query cost statistics in 1.6 seconds: 137 kinds, 1148 relationship sides, 455 database queries". The cache key `graphql_cost:statistics:current` held, trimmed:

```json
{"version": 1, "branch": "main", "computed_at": "2026-10-08T10:30:50.661117Z", "schema_hash": "8c6ad0e5ec014f75365362d0834955f1", "kinds": ["BuiltinTag", "CoreAccount", "..."]}
```

Matches the expectation, with the deployment instead of the Python command.

### Step 3: the same request after the refresh

Trimmed:

```json
{
  "estimate_mode": "counted_first_step",
  "statistics": {"branch": "main", "computed_at": "2026-10-08T10:30:50.661117Z", "version": 1},
  "fields": [
    {"path": "InfraDevice", "estimate": {"expected": {"nodes": 5, "resolver_calls": 1, "database_rows": 15},
     "worst_case": {"nodes": 5, "resolver_calls": 1, "database_rows": 15}, "worst_case_is_bound": true, "source": "counted", "reason": null},
     "actual": {"nodes": 5, "resolver_calls": 1, "database_rows": 15}},
    {"path": "InfraDevice/interfaces", "estimate": {"expected": {"nodes": 94, "resolver_calls": 5, "database_rows": 282},
     "worst_case": {"nodes": 94, "resolver_calls": 5, "database_rows": 282}, "worst_case_is_bound": true, "source": "counted", "reason": null},
     "actual": {"nodes": 94, "resolver_calls": 5, "database_rows": 282}}
  ],
  "estimate_queries": {"queries": 2, "database_rows": 2},
  "unattributed": {"queries": 0, "database_rows": 0}
}
```

Matches the expectation: the statistics are those of step 2, both fields are counted, the worst case equals the expected figures, and the counted first step ran 2 queries.

### Step 4: the same request without the header

The response had the single key `data`, and its `data` was identical to the `data` of step 3, compared with `jq -S`. Matches the expectation. The number of database queries without the header was not measured in this step.

### Step 5: a stored query through `/api/query`

The demo data has no stored query, so the query `device_interfaces($device: String!)`, which reads a device and its interfaces, was created with `CoreGraphQLQueryCreate`. `GET /api/query/device_interfaces?device=atl1-leaf1` with the header returned two fields:

- `InfraDevice`: expected 1 node, actual 1 node, source `counted`
- `InfraDevice/interfaces`: expected 52 nodes, actual 52 nodes, source `counted`

Without the header, the response had the single key `data`. Matches the expectation.

### Step 6: the estimate from the report

- With `variables: {name: "atl1-leaf1"}`: `mode` was `COUNTED_FIRST_STEP`, with 1 expected node for `InfraDevice` and 52 expected and worst-case nodes for `InfraDevice/interfaces`, both with the source `COUNTED`.
- Without `variables`: `mode` was `STATISTICS_ONLY`, every source was `STATISTICS`, and `InfraDevice/interfaces` had 24 expected nodes and 52 worst-case nodes.
- With `variables: {}` and a query that declares no variables: `mode` was `COUNTED_FIRST_STEP`.
- The same report requests sent with the header showed the database queries the estimate ran: 2 with `variables` (the counted first step), and 1 without `variables` (the label counts).

Matches the expectation.

### Step 7: the permission check

Created with the admin token:

- an object permission `object:Infra:Device:view:allow_all`
- a role "Device viewer" with that permission only
- an account `device-viewer` and a group "Device viewers" with that role and that account

Logged in as `device-viewer` through `/api/auth/login`:

- The report of step 6 that selects `cost_estimate` returned `data: null` and the error "You do not have one of the following permissions: object:Infra:Device:view:allow_default | object:Infra:Interface:view:allow_default | object:Infra:InterfaceL2:view:allow_default | object:Infra:InterfaceL3:view:allow_default | object:Infra:LagInterfaceL2:view:allow_default | object:Infra:LagInterfaceL3:view:allow_default", with the code `PERMISSION_DENIED`, on the path `InfrahubGraphQLQueryReport.cost_estimate`.
- Running the submitted query returned the same message.
- The report that selects only `targets_unique_nodes` returned `true`.

Matches the expectation: the same message as running the query, and no counts.

### Step 8: a mutation with the header

`BuiltinTagCreate` sent with `X-Infrahub-Query-Cost: details` returned the single key `data`. Matches the expectation.

## Checks run before review

The checks of `/pre-ci` ([.agents/commands/pre-ci.md](../../../.agents/commands/pre-ci.md)) ran on 2026-10-08 for [tasks.md](tasks.md), T045. The branch changes the backend, the documentation, `schema/schema.graphql` and the generated frontend GraphQL types. It changes no YAML file, no `python_testcontainers` file, no OpenAPI file and no error catalogue file, so the checks of those areas did not run.

How the checks ran on this host:

- `git fetch` of `stable` failed for lack of access, so the changed files were listed against the local `origin/stable` (merge base 6a1f2952cd).
- Node on this host is version 18 and `frontend/app` needs 24, so Biome ran as its native binary, `knip`, Betterer and the GraphQL type generation ran in a `node:24-slim` container, and the Vitest suites ran in the `mcr.microsoft.com/playwright:v1.60.0-noble` image.

| Check | Command | Result |
| --- | --- | --- |
| Python format | `uv run invoke format`, `uv run ruff format --check --diff --exclude python_sdk .` | Passed, no file changed |
| Main Python lint | `uv run invoke main.lint` | Passed |
| Ruff on the whole repository | `uv run ruff check . --exclude python_sdk` | Passed |
| Type check with ty | `uv run ty check .` | Failed with 1 error, fixed in this PR, then passed |
| Lockfiles | `uv lock --check`, also in `python_testcontainers` | Passed |
| Backend lint with mypy | `uv run invoke backend.lint` | Passed: no issues in 1,716 source files |
| Generated backend files | `uv run invoke backend.validate-generated` | Passed |
| GraphQL schema | `uv run invoke schema.validate-graphqlschema` | Passed, no difference |
| JSON schema | `uv run invoke schema.validate-jsonschema` | Passed, no difference |
| Documentation lint | `uv run invoke docs.lint` | markdownlint passed with 0 errors; Vale is not installed on this host, so the style check did not run |
| Generated documentation | `uv run invoke docs.validate` | Passed, no difference |
| Frontend format and lint | `biome ci .` | Passed |
| Unused frontend code | `knip` | Passed, with one configuration hint about the ignore pattern of the generated GraphQL files |
| Frontend TypeScript regressions | `betterer ci` | Passed: 178 issues, unchanged |
| Frontend unit tests | `vitest run --coverage` in `frontend/app` | Passed: 193 files, 1,361 tests |
| `@infrahub/graph` unit tests | `vitest run` in `frontend/packages/graph` | Passed: 5 files, 23 tests |
| Frontend GraphQL types | `gql.tada generate output`, `gql.tada generate turbo`, then `git diff --exit-code` on the two generated files | Passed, no difference |
| Backend unit tests | `uv run pytest --cov=infrahub backend/tests/unit` | Passed: 2,831 tests |
| Component tests of the feature | `uv run pytest tests/component/graphql/cost/ tests/component/graphql/queries/test_graphql_query_report.py tests/component/graphql/queries/test_graphql_query_report_permissions.py tests/component/api/test_query_cost_header.py`, from `backend/` | Passed: 49 tests |
| Feature suites after the review fixes | `uv run pytest tests/unit/graphql/cost/`, then `uv run pytest tests/component/graphql/cost/ tests/component/graphql/queries/test_graphql_query_report.py tests/component/graphql/queries/test_graphql_query_report_permissions.py tests/component/api/test_query_cost_header.py tests/component/api/test_20_graphql.py tests/component/api/test_10_query.py`, from `backend/`, on 2026-10-08 | Passed: 145 unit tests; 77 component tests, and 1 test that is marked as an expected failure failed as expected |

The ty error: `resolve_graphql_query_cost_estimate` in `backend/infrahub/graphql/queries/graphql_query_report.py` passed the `variables` argument, narrowed from `object` to `dict[Unknown, Unknown]`, where `QueryCostEstimator.estimate` takes `dict[str, Any] | None`. The resolver now builds a mapping with string keys after it checks that the argument is an object. mypy did not report it.

## Accuracy check in infrahub-private-tests

Not known yet. This section will link the PR in `opsmill/infrahub-private-tests` ([tasks.md](tasks.md), T046). That PR adds:

- a synthetic data set that reproduces the customer's distribution, including the correlation between steps
- a check that the estimated single-relationship resolver calls of a `CablingPlanLogical`-shaped query, with the first step counted, are between half and twice the actual count (SC-001 in [spec.md](spec.md#measurable-outcomes))

## Checklist

- [ ] A maintainer confirmed the three changes under "Changes that need a maintainer's confirmation"
- [ ] Unit and component tests added
- [ ] Changelog fragment added: `changelog/+graphql-query-cost.added.md`
- [ ] User documentation added: `docs/docs/development-resources/graphql/query-cost.mdx`
- [ ] Internal documentation added: `dev/knowledge/backend/graphql-query-cost.md`
- [ ] Generated files regenerated: `schema/schema.graphql` and the frontend GraphQL types
- [ ] I have reviewed AI generated content

## Sources

- [INFP-739](https://opsmill.atlassian.net/browse/INFP-739): the card and the idea brief in its comments
- The spec directory:
  - [spec.md](spec.md)
  - [plan.md](plan.md)
  - [research.md](research.md)
  - [data-model.md](data-model.md)
  - [quickstart.md](quickstart.md)
  - [tasks.md](tasks.md)
  - [critiques/critique-20261007-184332.md](critiques/critique-20261007-184332.md)
- The contracts:
  - [contracts/cost-details-header.md](contracts/cost-details-header.md)
  - [contracts/cost-details.schema.json](contracts/cost-details.schema.json)
  - [contracts/graphql_query_report.graphql](contracts/graphql_query_report.graphql)
- [AGENTS.md](../../../AGENTS.md) and [backend/AGENTS.md](../../../backend/AGENTS.md), "Ask First"
