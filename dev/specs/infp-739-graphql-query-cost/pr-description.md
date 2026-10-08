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

[CLAUDE RECOMMENDED – based on the "Ask First" list of [backend/AGENTS.md](../../../backend/AGENTS.md)] Also confirm that no new root query and no new database index is needed. The change adds a field and an argument to the existing `InfrahubGraphQLQueryReport` query, and the plan names only the existing `node_uuid` and `rel_identifier` indexes. The plans under "Query plans of the refresh and first-step queries" show whether that holds.

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

The results are not known yet. They go in "Results of the quickstart steps on a development stack" and "Checks run before review".

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

## Query plans of the refresh and first-step queries

Not known yet. This section will hold the `EXPLAIN` plans of `RelationshipSideDegreeQuery`, `FirstStepNodesQuery`, and `FirstStepPeerCountQuery`, run against a database seeded with at least 100,000 nodes of one kind ([tasks.md](tasks.md), T043). The plans show:

- whether `n.uuid IN $ids` uses the `node_uuid` index
- whether the first-step queries scan every node of a kind they do not need

## Results of the quickstart steps on a development stack

Not known yet. This section will hold the results of steps 1 to 8 of [quickstart.md](quickstart.md), run on a development stack ([tasks.md](tasks.md), T044).

## Checks run before review

Not known yet. This section will list the checks run with `/pre-ci` and their results ([tasks.md](tasks.md), T045):

- format
- lint, including `ruff check . --exclude python_sdk`
- mypy
- unit tests of the changed areas
- `uv run invoke docs.validate`
- validation of the generated files

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
