# Research: Estimated and Actual Cost of GraphQL Queries

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Jira**: [INFP-739](https://opsmill.atlassian.net/browse/INFP-739)

Each decision below states what was chosen, why, and what else was considered. The code facts come from `opsmill/infrahub` at commit `6a1f2952cd`. Decisions the brief did not make are labelled "[CLAUDE RECOMMENDED – based on X]".

## Facts the design depends on

- `/graphql` runs through `infrahub.graphql.app::InfrahubGraphQLApp._handle_http_request`. The response is built as `{"data": ..., "errors": ...}`, and `ExecutionResult.extensions` is never read, so no response carries a top-level `extensions` key today.
- `/api/query/{query_id}` runs through `infrahub.api.query::execute_query`. It returns `{"data": data}`, builds the analyzer without `query_variables`, and turns every URL parameter except `branch`, `at`, `update_group` and `subscribers` into a variable.
- The only GraphQL middleware is `infrahub.graphql.middleware::raise_on_mutation_for_branch_status`. `dev/knowledge/backend/graphql-execution.md` says a check that runs once per request belongs in the request handler, and that per-field middleware must stay synchronous.
- Relationship fields resolve through `infrahub.graphql.resolvers.resolver::single_relationship_resolver` and `many_relationship_resolver`, which delegate to the per-request `SingleRelationshipResolver` and `ManyRelationshipResolver` objects on `GraphqlContext`. Top-level fields resolve through `default_paginated_list_resolver` or `ipam_paginated_list_resolver`. `ancestors` and `descendants` resolve through `hierarchy_resolver`.
- Every database read and write goes through `infrahub.database::InfrahubDatabase.execute_query_with_metadata`. No production code counts queries or rows for each request. The test helper `tests/helpers/db_query_counter.py::CountingInfrahubDatabase` counts queries and rows by query name.
- Batches of `PeerRelationshipsDataLoader` and `NodeDataLoader` (aiodataloader) are dispatched with `loop.call_soon(ensure_future, ...)`, which copies the context of the first `load()` call. A `ContextVar` set before execution is visible in resolvers and in batch functions.
- `NodeDataLoader` is keyed by `GetManyParams`, which has no relationship name, so one batch can serve several cardinality-one fields that select the same fields.
- `infrahub.graphql.analyzer::GraphQLQueryNode` keeps the peer model (`infrahub_model`), the concrete kinds under a generic (`infrahub_node_models`), the arguments and the context type (EDGE for cardinality many, NODE for cardinality one). It does not keep the relationship schema or the alias. `query_variables` is stored and never read.
- `infrahub.graphql.queries.graphql_query_report::resolve_graphql_query_report` builds the analyzer with no variables and runs no permission check on the kinds inside the submitted query, because the request's own analyzer skips the root field `InfrahubGraphQLQueryReport`.
- Relationships are stored as `(Node)-[:IS_RELATED]-(Relationship {name: identifier})-[:IS_RELATED]-(Node)`. The direction is the direction of the edges (`infrahub.core.query::Query.get_query_arrows`). Neo4j label counts cannot give peers for each relationship identifier, because the identifier is a property.
- `infrahub.services.adapters.cache::InfrahubCache` stores strings only. Redis is the default driver. The NATS driver limits a value to 1 MB by default and is marked "not recommended for production".
- Scheduled flows are `WorkflowDefinition` entries with a fixed `cron` string in `infrahub.workflows.catalogue`. No cron value comes from settings.
- `DatabaseSettings.query_size_limit` (5,000) pages any read that has no `limit`/`offset` through `Query.query_with_size_limit`.

## D1. Name and values of the cost-details header

- **Decision**: `X-Infrahub-Query-Cost: details`. The value is compared without case. A missing header, or any other value, leaves the request as it is today.
- **Rationale**: it follows the `X-Infrahub-` prefix of `X-Infrahub-Admission`. A named value leaves room for later values without a new header. A URL parameter is not possible because `/api/query` turns URL parameters into variables.
- **Alternatives considered**: `X-Infrahub-Cost: 1` (a boolean leaves no room for other values); a field in the request body (not available on `GET /api/query`).

## D2. Where the cost details go in the response

- **Decision**: a `query_cost` object under the top-level `extensions` key of the response, defined in [contracts/cost-details.schema.json](contracts/cost-details.schema.json). On `/graphql`, `extensions` sits next to `data` and `errors`. On `/api/query`, the response becomes `{"data": ..., "extensions": {...}}`, only when the header is present.
- **Rationale**: the GraphQL over HTTP specification reserves `extensions` for this kind of data, and clients that do not read it are not affected.
- **Alternatives considered**: a separate response header (too small for one entry per field).

## D3. How actual counts are recorded

- **Decision**: a `QueryCostRecorder` held in a `ContextVar`, set by the request handler only when the header is present and the operation is a query.
    - Nodes and resolver calls: recorded in the resolver wrappers (`single_relationship_resolver`, `many_relationship_resolver`, `hierarchy_resolver`, `default_paginated_list_resolver`, `ipam_paginated_list_resolver`) when a recorder is set. Each wrapper also sets a second `ContextVar` with the field's path, and resets it in `finally`.
    - Database rows: `InfrahubDatabase.execute_query_with_metadata` adds `len(results)` to the field in the second `ContextVar` when a recorder is set.
    - The counted first step runs with a reserved value in the field `ContextVar`, so its queries and rows go to `estimate_queries`. Queries that run while no field is set go to `unattributed` (critique E3).
- **Rationale**: no middleware is added, so the execution path of requests without the header does not change (FR-002). The only cost for those requests is one `ContextVar.get()` returning `None` for each resolver call and each database query, and no counting query runs. Reads caused by display labels, profiles and permission filtering happen inside the resolver of the field, so they are counted for that field (FR-014).
- **Known limit**: a `NodeDataLoader` batch that serves several cardinality-one fields with the same selection is counted for the field whose resolver started the batch. The contract states this. Splitting the loaders by field would change how many queries run when the header is present, which would break SC-003.
- **Alternatives considered**:
    - a synchronous graphql-core middleware: it wraps every field, including introspection fields, and the knowledge doc says to avoid it when the request handler can do the work
    - a subclass of `InfrahubDatabase`, as in the test helper: every `start_session()` copies the object through `get_context()`, and the resolvers open their own sessions, so the subclass would have to be passed through every session

## D4. Field paths in the cost details

- **Decision**: each entry is identified by the path of response keys from the top-level field, joined by `/`, without the `edges` and `node` levels and without list indexes. For example: `InfrahubDevice/interfaces/connected_endpoint`. An alias replaces the field name.
- **Rationale**: the same path is computed from the analyzer tree (for the estimate) and from `info.path` (for the actual counts), so both can be shown in one entry. Aliases keep two selections of the same relationship apart.
- **Change needed**: `GraphQLQueryNode` gains the response key, the relationship schema (identifier, cardinality, direction) and the selected `count` field.

## D5. Statistics store: content and cache layout

- **Decision**: the statistics are kept in the existing cache (`InfrahubCache`, Redis by default), outside the graph.
    - `graphql_cost:statistics:current` holds a small JSON pointer: version number, branch (`main`), computed time, schema hash of main.
    - `graphql_cost:statistics:v{version}:kind:{kind}` holds the statistics for one concrete kind as JSON.
    - The refresh writes all kind keys of the new version, then replaces the pointer, then deletes the keys of the previous version.
- **Rationale**: one key for each kind keeps every value well below the 1 MB default limit of the NATS driver. A schema with about 5,000 relationship sides would be about 10 MB in a single key. Writing the pointer last means a reader never sees half of a version.
- **Content for each concrete kind** (see [data-model.md](data-model.md)):
    - the label count at refresh time and the number of nodes active on main at refresh time
    - for each relationship identifier and side (outbound, inbound, bidirectional):
        - nodes with at least one peer
        - total peers, from which the mean is computed
        - [CLAUDE RECOMMENDED – based on FR-005 grouping by the concrete kind of the peers] total peers for each concrete peer kind, so that statistics below the first step can follow peers through a generic
        - a histogram of peers per node with powers-of-two buckets (0, 1, 2–3, 4–7, …); each bucket holds its node count and its maximum
        - the 20 nodes with the most peers, with their exact peer counts
- **Alternatives considered**: a graph vertex (crosses the "database schema or migration" gate and is versioned by branch, which the statistics do not need); a single JSON key (too large for NATS).

## D6. Copy of the statistics in each process

- **Decision**: each process keeps the last version it loaded in memory. A request that needs an estimate reads the pointer key (one cache read). When the version differs from the copy, the process loads the kind keys of that version with one `get_values` call. Requests without the header and report calls without the estimate field read nothing.
- **Rationale**: requests only read the statistics (FR-016). The pointer read keeps every process on the latest version without a message to every process.
- **Alternatives considered**: a `refresh.registry.*` message to every process (more moving parts for data that changes once a day); reading every kind key on every request (more cache traffic).

## D7. How the refresh computes the statistics without one large transaction

- **Decision**: a Prefect flow reads main in chunks of node IDs, following the pattern of `infrahub.core.diff.calculator::DiffCalculator._run_node_scoped_calculation_queries`:
    1. one query for the label count of each concrete kind, and `infrahub.telemetry.queries::CountNodesByKindsQuery` for the nodes active on main
    2. for each concrete kind, one read of the IDs of its nodes active on main (paged by `Query.query_with_size_limit`)
    3. for each relationship side of that kind and each chunk of `query_size_limit` IDs, one degree query with `n.uuid IN $ids`; it returns, for each node, its peer count for each concrete peer kind, with the same active-edge rules as `RelationshipGetPeerQuery`
    4. Python adds each chunk to the histogram, the totals and the list of nodes with the most peers, then drops the chunk
- Each chunk is a separate auto-commit read, so no transaction holds more than one chunk. The flow keeps one in-progress aggregate for each relationship side.
- The `uuid IN $ids` lookup uses the `node_uuid` index whatever the kind's size. The plan of the degree query is checked with `EXPLAIN` during implementation (Principle V).
- **Sides computed**: for each concrete kind K and each relationship on K, the side (identifier, direction, K), and for each concrete peer kind P, the opposite side (identifier, opposite direction, P). The opposite side gives the largest number of parents that can reach one peer, which the worst case needs, even when P declares no relationship back.
- **Rationale**: chunks of IDs keep each query to a fixed number of nodes and use the `node_uuid` index. The ID list of the largest kind in the brief (215,764 interfaces) is about 8 MB of strings in the flow's memory. `CALL … IN TRANSACTIONS` is used in this codebase for writes only.
- **Alternatives considered**:
    - keyset paging (`uuid > $after ORDER BY uuid LIMIT $page`): the `node_uuid` index is on the `Node` label, so the planner either scans that index across every kind or scans and sorts the kind's label on each page; which one it picks is not known (critique E7)
    - one aggregation query for each relationship: one transaction holds every node of the kind, which is the memory risk the brief names
    - sampling: rejected by the brief, because a sample can miss the maximum
    - one query for all relationships of a kind: fewer queries, but resolving the active edges for several identifiers and directions in one query is harder to keep correct; to revisit if the refresh is too slow

## D8. Refresh schedule

- **Decision**: [CLAUDE RECOMMENDED – based on existing daily flows such as `ANONYMOUS_TELEMETRY_SEND` and `WEBHOOK_CONFIGURE`] a `WorkflowDefinition` named `graphql-cost-statistics-refresh` with `cron=f"{randint(0, 59)} 4 * * *"` (once a day), `concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW` and low priority. Until the first run, every estimate has the reason "no statistics". The deployment can also be run on demand from the task manager.
- **Rationale**: node counts stay current through label counts (FR-017), so only the spread of peers ages. A daily run keeps the cost of reading every node to once a day. The brief leaves the acceptable age open (open question 1), so this default can change without changing the design.
- **Alternatives considered**: an interval in settings (no scheduled flow in this codebase reads its schedule from settings, and a new setting needs `docker-compose.yml` to be regenerated); a refresh when a share of a kind's nodes changes (out of scope in the brief).

## D9. The counted first step

- **Decision**: the first step is counted whenever variable values are given (FR-005):
    - On `/graphql` and `/api/query`, a request always runs with its variable values, so the first step is always counted.
    - On the report, the first step is counted only when the `variables` argument is given. An empty object counts as given, which is how a caller asks for counting on a query that declares no variables. Without the argument, the whole estimate is "statistics only" (FR-006), and no counting query runs.
    - Given values that do not match the declared types return the graphql-core coercion error.
- **Queries**:
    - one query for each top-level field: it applies the field's filters, `limit` and `offset` on the request's branch and `at` time (FR-013), and returns for each concrete kind the number of matching nodes and up to `query_size_limit` of their IDs, in one row for each kind. It also returns the current label count of each kind in the query (FR-017).
    - one query for each relationship field directly under a top-level field: it counts the peers of those IDs for each concrete peer kind, the number of distinct peers, and the largest number of top-level nodes that reach one peer. It is built on `RelationshipGetPeerQuery`, so it applies the same filters and active-edge rules as the resolver.
- **Limit**: when a top-level field matches more than `query_size_limit` nodes, its node count is still counted, and the relationship fields under it use statistics, with the source "statistics".
- **Statistics only**: one query reads the current label counts. No other database query runs.
- **Rationale**: this meets SC-003 (at most one extra query for the top-level node and one for each relationship field directly under it). Variables are coerced with graphql-core `get_variable_values` and `get_argument_values` (`graphql.execution.values`), so the counted filters match what execution uses. Tying the report's mode to the `variables` argument matches FR-006 literally, and lets a caller get a statistics-only estimate, with no counting query, for any query.
- **Alternative considered**: counting whenever every declared variable has a value, so that a query with no variables is always counted. Rejected by the critique (E1), because FR-006 expects a report call without variables to be "statistics only".

## D10. Estimate algorithm

- **Decision**: a pure function over an estimation tree built from the analyzer tree. For each field it carries, for each concrete kind of the parent nodes: the expected number of paths, the worst-case number of paths, and the worst-case number of paths that can reach one node.
    - Expected nodes: parent paths × mean peers of the parent's concrete kind, split into concrete peer kinds by the stored totals for each peer kind (FR-008).
    - Expected resolver calls: the expected number of parent nodes.
    - Worst-case nodes: [CLAUDE RECOMMENDED – based on SafeBound] the bound built from per-node peer counts (FR-008). The peer counts are taken in decreasing order: the exact counts of the listed nodes, then each histogram bucket at its maximum. Each node takes at most M paths, where M is the largest number of paths that can reach one parent node, until the parent's worst-case path count is used up. M for the next step is M × the largest number of parents of one peer (from the opposite side), capped by the worst-case path count. When a histogram is missing, the bound is the product of the maximum peers for each node at each step.
    - Worst-case paths for each peer kind: the smaller of the field's worst case and M × the total peers of that kind.
    - Listed node (FR-018): when the top-level field targets literal IDs and an ID is in the list of nodes with the most peers, its stored peer count is used for the expected and the worst-case figure of the fields directly under it.
    - Database rows: [CLAUDE RECOMMENDED – based on the resolver paths described in the facts above] a linear model for each resolver path: peer query rows, plus node information rows, plus one row for each selected attribute for each node, plus one row for each selected cardinality-one relationship for each node, plus one row for each parent node when `count` is selected. A cardinality-one field that selects only `id` has no rows. The actual rows show how far the model is off.
- **Top-level field in statistics-only mode**: a field that targets unique nodes (the analyzer's existing check) has as many nodes as supplied values. Any other field has the scaled node count of its kind, capped by a literal `limit`.
- **Scaling (FR-017)**: estimated nodes of a kind = active nodes at refresh × current label count ÷ label count at refresh.
- **Rationale**: the bound holds when many paths reach the same node, which "the sum of the k largest peer counts" does not. GraphQL queries are trees, so no linear-program solver is needed (no new dependency).
- **Alternatives considered**: LpBound (needs a solver for each query, out of scope); random walks (Wander Join, out of scope, would break SC-003).

## D11. The report query

- **Decision**:
    - `InfrahubGraphQLQueryReport(query: String!, variables: GenericScalar)` gains an optional `variables` argument.
    - `GraphQLQueryReport` gains a `cost_estimate` field with its own resolver. The estimate is computed only when the field is selected, so callers that select only `targets_unique_nodes` see no change.
    - The `cost_estimate` resolver runs the same permission checker pipeline as `/graphql` (`infrahub.graphql.api.dependencies::build_graphql_query_permission_checker`) on the analyzer of the submitted query, with the caller's account session and the request's branch. A denied account gets the same `PermissionDeniedError` that running the query would return (FR-010).
    - A submitted mutation returns a GraphQL error, because mutations are out of scope.
- **Rationale**: reusing the pipeline returns exactly the error that running the query returns. Putting the check on the new field keeps the existing field backward compatible.
- **Alternatives considered**: checking only `ObjectPermissionChecker` (skips the anonymous and branch checkers, so the error could differ from a real run).

## D12. Tests

- **Unit** (`backend/tests/unit/graphql/cost/`): histogram, percentiles, the worst-case bound (including a query from many nodes to one node and back out), splitting by concrete peer kind, scaling by label counts, the listed-node rule, the rows model, path building.
- **SC-002 and SC-003 method**: a test cannot run the code from before the feature. It runs the same request with and without the header, with `CountingInfrahubDatabase`. Without the header, no first-step query runs and no recorder is created. With the header, the extra queries equal `estimate_queries.queries`, which is at most 1 + the number of relationship fields directly under the top-level field.
- **Component** (`backend/tests/component/graphql/cost/`): the refresh on a fixture with a known peer distribution (FR-009, FR-016); `/graphql` and `/api/query` with and without the header (SC-002, SC-003); mutations (FR-015); the report with and without variables, and with a denied account (FR-003, FR-006, FR-010); a branch that adds peers (FR-013); label scaling (FR-017); a listed node (FR-018); a relationship without statistics (FR-012); `count` and `display_label` (FR-014); the worst case on an unchanged fixture (FR-008); finding the field that multiplies the rows (SC-004).
- **SC-001**: the customer-shaped data set and its check live in `infrahub-private-tests`, as the brief says. This repository provides the header, the report and the refresh flow it calls.
