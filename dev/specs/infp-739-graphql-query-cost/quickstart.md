# Quickstart: Validate the Estimated and Actual Cost of GraphQL Queries

**Feature**: [spec.md](spec.md) | **Contracts**: [contracts/](contracts/)

This guide checks the feature end to end on a local instance. It links to the contracts instead of repeating them.

## Prerequisites

- A development stack: `uv run invoke dev.start`
- Demo data loaded: `uv run invoke demo.load-infra-schema` and `uv run invoke demo.load-infra-data`
- An API token in `$TOKEN` and the server address in `$INFRAHUB` (for example `http://localhost:8000`)

## 1. Before the first refresh: fields have the reason "no statistics"

```bash
curl -s "$INFRAHUB/graphql" \
  -H "X-INFRAHUB-KEY: $TOKEN" -H "X-Infrahub-Query-Cost: details" -H "Content-Type: application/json" \
  -d '{"query": "query { InfraDevice(limit: 5) { edges { node { name { value } interfaces { edges { node { name { value } } } } } } } }"}' \
  | jq '.extensions.query_cost'
```

Expected:

- `statistics` is `null`.
- Each relationship field has `estimate.reason = "no statistics"` and filled `actual` counts.

## 2. Run the statistics refresh

Run the `graphql-cost-statistics-refresh` deployment from the task manager, or call the flow from a shell inside the server container:

```bash
uv run python -c "import asyncio; from infrahub.graphql.cost.tasks import refresh_query_cost_statistics; asyncio.run(refresh_query_cost_statistics())"
```

Expected: the flow run completes, and the cache key `graphql_cost:statistics:current` holds version 1 with `branch = main`.

## 3. Run a query with the header

Repeat the request from step 1.

Expected (see [contracts/cost-details.schema.json](contracts/cost-details.schema.json)):

- `statistics.branch = "main"` and `statistics.computed_at` is the time of the refresh.
- `estimate_mode = "counted_first_step"`, because a request that runs always has its variable values.
- The top-level field and `InfraDevice/interfaces` have `estimate.source = "counted"`.
- For each field, `estimate.expected` and `estimate.worst_case` are filled, with `worst_case ≥ expected`.
- `estimate_queries.queries` is at most 2: one for `InfraDevice` and one for `InfraDevice/interfaces` (SC-003).

## 4. Run the same query without the header

Expected: the response has no `extensions` key and is otherwise identical to step 3 (FR-001, FR-002).

## 5. Run a stored query through `/api/query`

```bash
curl -s "$INFRAHUB/api/query/<stored_query_name>?<variable>=<value>" \
  -H "X-INFRAHUB-KEY: $TOKEN" -H "X-Infrahub-Query-Cost: details" | jq '.extensions.query_cost.fields'
```

Expected: one entry for each relationship field, with `estimate` and `actual`.

## 6. Get the estimate from the report without running the query

```graphql
query {
  InfrahubGraphQLQueryReport(
    query: "query($name: String!) { InfraDevice(name__value: $name) { edges { node { interfaces { edges { node { name { value } } } } } } } }"
    variables: { name: "<device name>" }
  ) {
    targets_unique_nodes
    cost_estimate {
      mode
      statistics { branch computed_at }
      fields { path expected { nodes resolver_calls database_rows } worst_case { nodes } source reason }
    }
  }
}
```

Expected: `mode = COUNTED_FIRST_STEP`. Without the `variables` argument, `mode = STATISTICS_ONLY`, every `source` is `STATISTICS` and no counting query runs (FR-006). Passing `variables: {}` counts the first step of a query that declares no variables.

## 7. Permission check

Call the report from step 6 with an account that cannot view `InfraInterface`.

Expected: the request fails with the same `PermissionDeniedError` message that running the query returns, and no counts (FR-010).

## 8. Mutations ignore the header

Send any mutation with `X-Infrahub-Query-Cost: details`.

Expected: no `extensions` key (FR-015).

## Automated checks

```bash
uv run pytest backend/tests/unit/graphql/cost/
uv run pytest backend/tests/component/graphql/cost/
```
