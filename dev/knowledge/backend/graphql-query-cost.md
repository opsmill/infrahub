# GraphQL Query Cost

> Part of: `dev/knowledge/backend/` | Related: [graphql-execution.md](graphql-execution.md), [query-pattern.md](query-pattern.md), [async-tasks.md](async-tasks.md)

How Infrahub counts the nodes, resolver calls and database rows of each field of a GraphQL query,
and how it estimates the same figures from statistics that a daily flow stores in the cache. The
user-facing description of the header, the response and the report field is
`docs/docs/development-resources/graphql/query-cost.mdx`.

The code is in the package `infrahub.graphql.cost`. Three parts work together:

- The recorder counts what a request actually does, when the request asks for it.
- The refresh flow reads the default branch once a day and publishes statistics in the cache.
- The estimator combines the statistics with a count of the first step of the query.

## Actual counts: two `ContextVar`s, no middleware

`infrahub.graphql.cost.recorder` holds two `ContextVar`s:

- the request's `QueryCostRecorder`, or `None`
- the path of the field being resolved, the reserved path `ESTIMATE_FIELD_PATH` (`"<estimate>"`),
  or `None`

The request handlers (`InfrahubGraphQLApp._handle_http_request` and
`infrahub.api.query::execute_query`) set the recorder with `activate_recorder` only when the
`X-Infrahub-Query-Cost` header is `details` (compared without case) and the operation contains no
mutation. Counting starts there: authentication, loading the account's permissions and, on
`/api/query`, reading the stored query are not counted.

Two places read the `ContextVar`s:

- The resolver wrappers (`single_relationship_resolver`, `many_relationship_resolver`,
  `hierarchy_resolver`, `default_paginated_list_resolver`, `ipam_paginated_list_resolver`) call
  `record_resolver_call` when a recorder is set. It sets the field path with `resolving_field`,
  awaits the body, and records one call and the returned nodes in `finally`, with 0 nodes when the
  body raises. The wrapper is the function `retry_db_transaction` retries, so a retry counts as a
  call.
- `InfrahubDatabase.execute_query_with_metadata`, the single path of every query, adds
  `len(results)` to the current field, to the estimate totals for `ESTIMATE_FIELD_PATH`, or to
  `unattributed` when no field is set.

A request without the header runs one extra `ContextVar.get()` per resolver call and per query, and
its execution path does not change.

Keep it this way rather than adding a graphql-core middleware. A middleware wraps every field,
including attribute and introspection fields, and an `async` one forces every field onto the async
completion path ([graphql-execution.md](graphql-execution.md)). The resolver wrappers already run
once per relationship field. Counters on an `InfrahubDatabase` subclass do not work either: the
application's database object is shared by every request, and each resolver opens its own session
from it, while a `ContextVar` is scoped to the request and to the tasks it starts.

`ContextVar`s reach the batch functions of `NodeDataLoader` and `PeerRelationshipsDataLoader`
because aiodataloader schedules a batch with `loop.call_soon(ensure_future, ...)`, which copies the
context of the first `load()` of the batch. That is also why a batch is counted for the field that
started it (see [Known limits](#known-limits)).

`build_query_cost_details` merges the estimate and the recorder into the Pydantic models of
`extensions.query_cost`: fields of the estimate in tree order, then recorded paths missing from
the estimate in the order they were first recorded. It raises `ValueError` for a path that has rows
but no resolver call, which the `finally` in `record_resolver_call` prevents.

## Statistics cache layout and versioning

`StatisticsStore` keeps one version of the statistics in the cache (`InfrahubCache`, Redis by
default):

| Key | Value |
| --- | --- |
| `graphql_cost:statistics:current` | `StatisticsPointer`: version, branch, `computed_at`, schema hash, kinds |
| `graphql_cost:statistics:v{version}:kind:{kind}` | `KindStatistics` of one concrete kind |

`KindStatistics` holds the label count (deleted nodes and nodes of other branches included), the
number of nodes active on the default branch, and one `RelationshipSideStatistics` for each
relationship identifier and direction: nodes with peers, total peers, peers for each concrete peer
kind, a powers-of-two histogram (node count and maximum of each bucket) and the `TOP_NODES_LIMIT`
(20) nodes with the most peers. One key per kind keeps each value below the 1 MB default value
limit of the NATS cache driver.

`StatisticsStore.publish` writes a new version in this order, so a reader never loads part of a
version:

1. take the next version number (1 when no pointer exists)
2. delete keys already stored under that version, left by an interrupted run
3. write every kind key
4. write the pointer
5. delete the keys of the previous version

Readers go through `StatisticsSnapshotHolder`, one per process (`get_statistics_snapshot_holder`).
Each estimate reads the pointer and reloads the kinds with one `get_values` call only when the
whole pointer differs from the loaded one; comparing the version alone is not enough, because an
emptied cache numbers the versions from 1 again. A missing kind key makes the holder read the
pointer once more, since a refresh deletes the previous keys after moving the pointer; a kind still
missing has no statistics. Requests never write the statistics.

## Refresh by chunks of IDs

`refresh_query_cost_statistics` (`graphql-cost-statistics-refresh`, registered as
`GRAPHQL_COST_STATISTICS_REFRESH` in `infrahub.workflows.catalogue`) runs once a day at a random
minute past 04:00 UTC, with a concurrency limit of 1 that cancels new runs and low priority. It
takes one timestamp at the start and reads the default branch at that time in a read-only session,
so nodes changed during the run do not count.

`StatisticsCollector.collect` reads every concrete kind (node, profile and template kinds):

1. `KindLabelCountQuery` and `infrahub.telemetry.queries::CountNodesByKindsQuery` read the label and
   active counts of every kind.
2. `KindActiveNodeIdsQuery` reads the IDs of each kind in pages of `chunk_size` nodes, taken before
   the active-edge check so each page checks the edges of its own nodes only.
3. For each relationship side of the kind and each chunk of `chunk_size` IDs,
   `RelationshipSideDegreeQuery` returns `(node_id, peer_kind, peers)` for `n.uuid IN $ids`, with
   the active-edge rule of `RelationshipGetPeerQuery`.
4. `RelationshipSideAccumulator.add_chunk` adds each chunk to the histogram, the totals and the
   top nodes, and `build(active_count)` counts nodes without a row as nodes without peers.

`chunk_size` is `config.SETTINGS.database.query_size_limit`. Each chunk is a separate auto-commit
read, so no transaction holds more than one chunk; the flow keeps the IDs of one kind and one
aggregate per side in memory. For a relationship R of kind K, the collector reads the side of K and
the opposite side of each concrete peer kind, because the worst case needs the largest number of
nodes that reach one peer even when the peer kind declares no relationship back.

The flow logs the version written, the duration and the number of kinds, sides and queries, and
returns `None`.

## Estimator

`QueryCostEstimator.estimate(analyzer, schema, variable_values)` runs four stages:

1. `build_cost_tree` turns the analyzer's query tree into `CostTreeField`s. It coerces the
   variables with graphql-core `get_variable_values` (and raises its first error) and the arguments
   with `get_argument_values`, merges fields with the same path, skips root fields that map to no
   kind, and stops at `ancestors` and `descendants`. An inline fragment narrows the `parent_kinds`
   of the fields inside it, not the kinds those fields return.
2. With `variable_values` (the endpoints always pass them, the report only when `variables` is
   given), `FirstStepCounter.count` runs inside `resolving_field(ESTIMATE_FIELD_PATH)` on its own
   read-only session: one `FirstStepNodesQuery` (a `NodeGetListQuery`) per top-level field and one
   `FirstStepPeerCountQuery` (a `RelationshipGetPeerQuery`) per relationship field directly under
   it, on the request's branch and `at`. Without them, `read_label_counts` runs one
   `KindLabelCountQuery`.
3. `StatisticsSnapshotHolder.get` loads the statistics.
4. `infrahub.graphql.cost.estimator::estimate`, a pure function without I/O, computes the figures.

The first step is not counted, and the estimate uses the statistics instead, for a top-level field
filtered by `hfid` (its resolver reads with another query), for the fields under a top-level field
that matches more than `query_size_limit` nodes, and for relationship fields with
`include_descendants`. `ancestors` and `descendants` are not counted and have no statistics.

For each field, `estimate` passes to the fields under it, for each concrete kind, the expected
number of paths, the worst-case number of paths and the worst-case number of paths that reach one
node (M):

- Expected nodes: parent paths × mean peers of the parent kind (cardinality one: the share of nodes
  with a peer), split between the peer kinds by their stored totals.
- Worst-case nodes: the parent paths go to the nodes with the most peers first, at most M per node:
  the listed top nodes with their exact counts, then each histogram bucket at its maximum. M for the
  next step is M × the largest number of parents of one peer, read from the opposite side. Without
  a histogram, each path takes the maximum peer count.
- Resolver calls: one per parent path, and one for a top-level field.
- Database rows: per node, one list or peer row (none for cardinality one), one node row, one row
  per selected attribute and per selected cardinality-one relationship, plus one row per call when
  `count` is selected. A cardinality-one field that selects only `id` reads nothing. Display labels,
  Profile values and permission filtering are not modelled.
- A statistics-only top-level field scales the stored active count by the current label count ÷
  the stored label count, then applies the literal `offset`, `limit` and the IDs given (or one node
  for a single-target filter). A literal ID listed among the top nodes of a field directly under it
  uses its stored peer count.
- A side or kind without statistics gives `reason = "no statistics"` to the field and every field
  under it.

`worst_case_is_bound` is true only when the request reads the branch the statistics describe at
the current time. The bound is the largest value over every assignment of paths to the nodes of one
step; over several steps it can be strictly above the real maximum, because M is the largest number
of paths that reach any one node, applied to every node.

Failure handling differs by caller. `estimate_request_cost` (header path) returns `None` on a
`GraphQLError`, which execution reports to the client, and logs and returns `None` on any other
error, so the response keeps its `data` and `errors` and the details have no estimate. The report's
`resolve_graphql_query_cost_estimate` lets errors propagate, so a cache failure reaches the caller.

## Known limits

- **Shared `NodeDataLoader` batches**: `NodeDataLoader` is keyed without the relationship name, so
  one batch can serve several cardinality-one fields with the same selection; its rows are counted
  for the field whose `load()` started the batch. Splitting the loaders per field would change the
  number of queries a request runs with the header.
- **Statistics of the default branch only**: the refresh reads the default branch. Requests on
  other branches or with an `at` time get a counted first step on their own branch and time, but
  statistics of the default branch below it, and `worst_case_is_bound` is false.
- **Correlation between steps**: the statistics treat the peers at one step as independent of the
  step before. When the nodes that one relationship returns have more peers than the average of
  their kind, the expected figures below the first step are too low. Counting the first step
  removes that error for the top-level fields and the fields directly under them only.
- **Changes since the refresh**: label-count scaling follows created nodes, but the spread of peers
  only changes at the next refresh, and a relationship added to the schema since then has no
  statistics.
