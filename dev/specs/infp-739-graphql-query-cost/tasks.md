---

description: "Task list for estimated and actual cost of GraphQL queries (INFP-739)"
---

# Tasks: Estimated and Actual Cost of GraphQL Queries for Each Relationship Field

**Input**: Design documents from `dev/specs/infp-739-graphql-query-cost/`

**Prerequisites**:

- `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/` and `quickstart.md`
- `critiques/critique-20261007-184332.md`, whose findings are applied to the files above

**Tests**: included. Every functional requirement in `spec.md` names its test, and constitution Principle IV requires tests written before or alongside the code.

**Branch**: `fac/graphql-proactive-analyzer-rrake`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1, US2)
- Exact file paths in every description; sites inside a file are named by symbol, never by line

## Path Conventions

- Backend only. Source under `backend/infrahub/`, tests under `backend/tests/{unit,component}/`, user docs under `docs/docs/`.
- New code goes in the package `backend/infrahub/graphql/cost/` (plan, "Source Code").
- Test directories get an `__init__.py` only where the sibling directories have one (`backend/tests/unit/graphql/` and `backend/tests/component/graphql/` do).

## Before the PR leaves draft

`AGENTS.md` **Boundaries → Ask First** lists three gates that this feature crosses. The INFP-739 brief records them as decided:

- a GraphQL schema change: `variables` and `cost_estimate` on `InfrahubGraphQLQueryReport`
- an API contract change: the `X-Infrahub-Query-Cost` header and the `extensions.query_cost` content
- an authorization change: a read-permission check on the report's estimate

T001 asks a maintainer to confirm them. Implementation does not wait for it, but the PR is not marked ready before it.

## Delivery order

The phases follow the plan's "Delivery order":

1. Actual counts (Phase 3). They need no statistics and can be checked against `CountingInfrahubDatabase`.
2. Statistics refresh (Phase 4).
3. Estimate (Phase 5).
4. Report (Phase 6).
5. Generated files and docs (Phase 7).

User Story 1 spans Phases 3 to 5. User Story 2 reuses the estimator from Phase 5.

---

## Phase 1: Setup

**Purpose**: governance and the new package.

- [X] T001 Write the PR description draft in `dev/specs/infp-739-graphql-query-cost/pr-description.md`. It lists the three Ask First gates above with a link to [INFP-739](https://opsmill.atlassian.net/browse/INFP-739), the known limits from `contracts/cost-details-header.md` (rows of shared `NodeDataLoader` batches) and `plan.md` "Risks", and asks a maintainer to confirm the gates.
- [X] T002 Create `backend/infrahub/graphql/cost/__init__.py` (empty, per `dev/knowledge/backend/package-init-files.md`) and `backend/infrahub/graphql/cost/constants.py` with:
    - `QUERY_COST_HEADER = "X-Infrahub-Query-Cost"` and `QUERY_COST_HEADER_VALUE = "details"`
    - `STATISTICS_POINTER_KEY = "graphql_cost:statistics:current"` and `STATISTICS_KIND_KEY_TEMPLATE = "graphql_cost:statistics:v{version}:kind:{kind}"`
    - `TOP_NODES_LIMIT = 20`
    - `NO_STATISTICS_REASON = "no statistics"`
    - `ESTIMATE_FIELD_PATH`, a reserved value that does not collide with a GraphQL response key: `"<estimate>"`. Angle brackets cannot appear in a GraphQL name, while `"__estimate__"` is accepted as an alias.

---

## Phase 2: Foundational

**Purpose**: the value types and the response model that both stories use.

**⚠️ CRITICAL**: Phases 3 to 6 import these modules.

- [X] T003 [P] Write unit tests in `backend/tests/unit/graphql/cost/test_models.py` (with `__init__.py`). Using the dataclass test case pattern of `dev/guidelines/backend/testing.md`, check:
    - `KindStatistics` survives a round trip through its JSON form
    - `StatisticsSnapshot.side(identifier, direction, kind)` returns the matching `RelationshipSideStatistics`, and `None` for an unknown kind, identifier or direction
    - `CostFigures` rejects negative values
- [X] T004 [P] Create `backend/infrahub/graphql/cost/models.py` with the frozen dataclasses of `data-model.md`:
    - `CostFigures`, `HistogramBucket`, `TopNode`, `RelationshipSideStatistics`, `KindStatistics`, `StatisticsPointer` and `StatisticsSnapshot` (with `side()`)
    - `RelationshipRef` and `CostTreeField`
    - `FieldDescription` (kind, relationship identifier, cardinality), `FieldEstimate` (with its `FieldDescription`) and `QueryEstimate` (mode, statistics pointer or `None`, estimates by path in tree order)
    - the enums `EstimateMode` (`counted_first_step`, `statistics_only`), `EstimateSource` (`counted`, `statistics`) and `EstimateReason` (`no statistics`). The relationship side uses the existing `infrahub.core.constants.RelationshipDirection` (`outbound`, `inbound`, `bidirectional`) instead of a new `RelationshipSide` enum with the same values.
    - `to_json()` / `from_json()` on the statistics types
    - mutable counters live in `recorder.py` (T013), not here
- [X] T005 [P] Write unit tests in `backend/tests/unit/graphql/cost/test_details.py`:
    - a `QueryCostDetails` built from a sample estimate and sample actual counts dumps (`model_dump(mode="json")`) to exactly the keys and nesting of `contracts/cost-details.schema.json`, including `estimate_queries`, `unattributed` and a field with `reason = "no statistics"`
    - entries come in tree order, followed by recorded paths missing from the tree, in the order they were first recorded
- [X] T006 [P] Create `backend/infrahub/graphql/cost/details.py`:
    - Pydantic models with `extra="forbid"` that match `contracts/cost-details.schema.json`: `QueryCostFigures`, `QueryCostFieldEstimate`, `QueryCostField`, `QueryCostTotals`, `QueryCostStatistics` and `QueryCostDetails`
    - `build_query_cost_details(estimate: QueryEstimate | None, recorder: QueryCostRecorder) -> QueryCostDetails`
    - when `estimate` is `None`, every recorded field gets `reason = "no statistics"`, `estimate_mode = "statistics_only"` and `statistics = null`
    - the `QueryCostRecorder` class it reads, in `backend/infrahub/graphql/cost/recorder.py`, with its counters `FieldActual` and `QueryTotals` (T011 adds the rest of that module)

**Checkpoint**: models and the response model are tested. The user stories can start.

---

## Phase 3: User Story 1 (P1), part A: actual counts for each field 🎯 MVP

**Goal**: a request to `/graphql` or `/api/query` with `X-Infrahub-Query-Cost: details` returns `extensions.query_cost` with the actual nodes, resolver calls and database rows of each field. Requests without the header and mutations do not change.

Requirements: FR-001, FR-002, FR-015, the actual-count part of FR-014, and SC-002.

**Independent Test**: send the same query to `/graphql` with and without the header on a fixture with known peers. Compare `data`, the presence of `extensions`, and each field's actual counts with values computed by hand.

### Tests for part A

- [X] T007 [P] [US1] Write unit tests in `backend/tests/unit/graphql/cost/test_recorder.py`:
    - `field_path_from_response_keys(["TestPerson", "edges", 0, "node", "cars", "edges", 3, "node", "owner"]) == "TestPerson/cars/owner"`, and an alias key replaces the field name
    - `QueryCostRecorder` adds calls, nodes and rows for each path
    - rows recorded while the field `ContextVar` holds `ESTIMATE_FIELD_PATH` go to the estimate totals
    - rows recorded with no field go to `unattributed`
    - `activate_recorder()` and `resolving_field()` restore the previous `ContextVar` values when the block exits, including on an exception
- [X] T008 [P] [US1] Write component tests in `backend/tests/component/graphql/cost/test_actual_counts.py` (with `__init__.py`). Use the HTTP client pattern of `backend/tests/component/api/test_20_graphql.py` and data on `car_person_schema` with known counts, for example 3 persons owning 0, 2 and 5 cars. Check:
    - without the header, the response has no `extensions` key (FR-001, FR-002)
    - with the header, `data` is identical to the response without the header (FR-001)
    - each path has exact `actual.nodes` and `actual.resolver_calls`, for example `TestPerson`, `TestPerson/cars` and `TestPerson/cars/owner` (FR-001)
    - with `CountingInfrahubDatabase` (`backend/tests/helpers/db_query_counter.py`): the sum of every field's `database_rows`, `estimate_queries.database_rows` and `unattributed.database_rows` equals the total rows the counter recorded during the request, minus the rows read before the handler starts the recorder (authentication and permission loading, measured with a request that resolves no field)
    - a query that selects `display_label` and `count` has the rows of those reads in the actual counts of the fields that read them (FR-014)
    - a mutation sent with the header has no `extensions` key, and its response equals the response without the header (FR-015)
- [X] T009 [P] [US1] Write component tests in `backend/tests/component/graphql/cost/test_query_counts.py` (SC-002). With `CountingInfrahubDatabase`, run the same query with and without the header, and check that the queries counted without the header equal the queries counted with the header minus `extensions.query_cost.estimate_queries.queries`.
- [X] T010 [P] [US1] Write component tests in `backend/tests/component/api/test_query_cost_header.py`. Use the stored-query pattern of `backend/tests/component/api/test_10_query.py`:
    - `GET /api/query/{name}?<variable>=<value>` with the header returns `{"data": ..., "extensions": {"query_cost": ...}}`, with an entry for each relationship field
    - without the header it returns `{"data": ...}` only
    - `POST /api/query/{name}` behaves the same

### Implementation for part A

- [X] T011 [US1] Create `backend/infrahub/graphql/cost/recorder.py` with:
    - `QueryCostRecorder`, created with T006: mutable totals for each path, plus estimate and unattributed totals; methods `record_call(path, field, nodes)`, where `field` is the field's `FieldDescription`, and `record_query(path, rows)`, where `path` is the current field path, `ESTIMATE_FIELD_PATH` or `None`
    - two `ContextVar`s, the recorder and the current field path, with accessors `get_cost_recorder()` and `get_current_field()`
    - context managers `activate_recorder(recorder)` and `resolving_field(path)`, both resetting by token in `finally`
    - `field_path_from_info(info)`, which uses `info.path.as_list()` with `field_path_from_response_keys` and drops `edges`, `node` and list indexes
    - `count_returned_nodes(result)`: `len(result["edges"])` for paginated results, 1 or 0 for a `{"node": ...}` result
- [X] T012 [US1] In `backend/infrahub/database/__init__.py::InfrahubDatabase.execute_query_with_metadata`, after the results are read: call `recorder.record_query(path=get_current_field(), rows=len(results))` when `get_cost_recorder()` returns a recorder, and do nothing more when it returns `None` (FR-002). Read `dev/knowledge/backend/query-pattern.md` first; this is the single path for every query.
- [X] T013 [US1] In `backend/infrahub/graphql/resolvers/resolver.py` (`single_relationship_resolver`, `many_relationship_resolver`, `hierarchy_resolver`, `default_paginated_list_resolver`) and `backend/infrahub/graphql/resolvers/ipam.py::ipam_paginated_list_resolver`, when `get_cost_recorder()` returns a recorder:
    - run the existing body inside `resolving_field(field_path_from_info(info))`
    - call `record_call(path, field=<the field's FieldDescription>, nodes=count_returned_nodes(result))` in a `finally` block, with 0 nodes when the body raises, so that a failed attempt still counts as a call and every path with rows has a field description
    - keep the path without a recorder exactly as it is
    - record inside the function that `retry_db_transaction` wraps, so that a retry counts as a call
- [X] T014 [US1] In `backend/infrahub/graphql/app.py::InfrahubGraphQLApp._handle_http_request`:
    - read `QUERY_COST_HEADER` from the request and compare its value with `QUERY_COST_HEADER_VALUE` without case
    - when it matches and `analyzed_query.contains_mutation` is false, run `execute_graphql_query` inside `activate_recorder(...)`
    - then set `response["extensions"] = {"query_cost": build_query_cost_details(estimate=None, recorder=...).model_dump(mode="json")}`
    - in every other case, leave the response unchanged
- [X] T015 [US1] In `backend/infrahub/api/query.py`, do the same as T014 in `execute_query`, with the header read in `graphql_query_get` and `graphql_query_post` from the `Request`. Return `{"data": data, "extensions": {...}}` only when the header is present.

**Checkpoint**: T007 to T010 pass. The actual counts can be used to diagnose a query, with every estimate marked "no statistics".

---

## Phase 4: User Story 1 (P1), part B: statistics refresh and store

**Goal**: a scheduled flow computes the statistics from main and publishes a new version in the cache. Requests only read them.

Requirements: FR-009, FR-011, FR-016, and critique finding E4.

**Independent Test**: run the flow on a fixture with a known peer distribution and compare every stored statistic with values computed by hand.

### Tests for part B

- [X] T016 [P] [US1] Write unit tests in `backend/tests/unit/graphql/cost/test_histogram.py`, with nodes added in several chunks. Check:
    - powers-of-two buckets (0, 1, 2–3, 4–7, …) with the node count and the maximum of each bucket
    - `nodes_with_peers`, `total_peers` and `peers_by_kind`
    - the 20 nodes with the most peers, in decreasing order
    - for a kind with fewer than 20 nodes, every node with at least one peer
    - the median, the 95th percentile and the maximum read from the histogram
    - an empty kind (`active_count = 0`, mean 0)
- [X] T017 [P] [US1] Write unit tests in `backend/tests/unit/graphql/cost/test_statistics_store.py` with `backend/tests/adapters/cache.py::MemoryCache`. Check:
    - `publish` writes every kind key before the pointer
    - it deletes the keys of the previous version
    - it deletes keys already stored under the version it writes (E4)
    - the snapshot holder loads a version once and reloads only when the pointer changes (a new version, or the same version number written by another refresh)
    - a missing kind key makes the holder read the pointer once more, then treat that kind as without statistics
    - no pointer means no snapshot
- [X] T018 [P] [US1] Write component tests in `backend/tests/component/graphql/cost/test_refresh.py`. Build persons owning 0, 1, 3 and 10 cars on `car_person_schema_generics`, with two concrete car kinds, plus:
    - one person deleted on main
    - one person that exists only on a branch

    Run the flow function and check that:
    - `label_count` includes both of those persons, `active_count` excludes both, and every other statistic of both sides of the `cars`/`owner` relationship equals the values computed by hand (FR-009)
    - the pointer has `branch = "main"`, a `computed_at` within the run, and version 1, then version 2 after a second run (FR-011)
    - a request with the header, run before the flow, leaves the pointer absent (FR-016)

### Implementation for part B

- [X] T019 [P] [US1] Create `backend/infrahub/graphql/cost/histogram.py` with `RelationshipSideAccumulator(identifier, direction, kind)`. Its `add_chunk(rows)` takes `(node_id, peer_kind, peers)` rows for the nodes of one chunk, and `build(active_count) -> RelationshipSideStatistics` counts nodes with no row as 0 peers. Add percentile helpers that read a `RelationshipSideStatistics`.
- [X] T020 [US1] Create the refresh queries in `backend/infrahub/graphql/cost/queries.py`. Follow `dev/knowledge/backend/query-pattern.md`: parameters only, `get_data()` returning frozen dataclasses, and kind labels taken from the schema, never from user input.
    - `KindLabelCountQuery`: the label count of each concrete kind given, in one query
    - `KindActiveNodeIdsQuery`: one page of a kind's nodes, taken before the active-edge check, each with whether its latest `IS_PART_OF` edge on the default branch is active
    - `RelationshipSideDegreeQuery`: for `n.uuid IN $ids`, an identifier and a `RelationshipDirection`, it returns `(node_id, peer_kind, peers)`. It uses `Query.get_query_arrows`, and the same active-edge rule as `infrahub.core.query.relationship::RelationshipGetPeerQuery`: the latest edge of both `IS_RELATED` edges must be active.
- [X] T021 [US1] Create `backend/infrahub/graphql/cost/collector.py` with `StatisticsCollector(db, branch, schema_branch, chunk_size)` and its method `collect(at) -> CollectedStatistics`, which returns the `KindStatistics` list and the query count. It:
    - lists every relationship side to read: for each concrete kind K (node, profile and template kinds) and each relationship R of K, the side `(R.identifier, R.direction, K)`, and for each concrete peer kind P, the side `(R.identifier, opposite direction, P)`, without duplicates
    - reads label counts with `KindLabelCountQuery`
    - reads active counts with `infrahub.telemetry.queries::CountNodesByKindsQuery`
    - reads each kind's IDs once, then runs `RelationshipSideDegreeQuery` for each chunk of `chunk_size` IDs (research D7)
- [X] T022 [US1] Create `backend/infrahub/graphql/cost/statistics_store.py` with:
    - `StatisticsStore(cache: InfrahubCache)`, with `publish(kinds, branch, computed_at, schema_hash) -> StatisticsPointer`, `read_pointer()` and `read_kinds(version, kinds)`, following the cache layout of `data-model.md`
    - `StatisticsSnapshotHolder`, one for each process, with `get(store) -> StatisticsSnapshot | None`, implementing research D6 and the retry rule of `data-model.md`
- [X] T023 [US1] Create `backend/infrahub/graphql/cost/tasks.py` with the flow `refresh_query_cost_statistics` (`@flow(name="graphql-cost-statistics-refresh")`). It:
    - gets the database and the cache from the existing worker dependencies (`infrahub.workers.dependencies`)
    - takes the main schema branch and its hash at the entry point
    - builds `StatisticsCollector(chunk_size=config.SETTINGS.database.query_size_limit)`
    - publishes through `StatisticsStore`
    - logs the duration and the number of kinds, sides and queries, and the version written
    - returns `None` (`dev/guidelines/backend/prefect-payloads.md`)
- [X] T024 [US1] Add `GRAPHQL_COST_STATISTICS_REFRESH` to `backend/infrahub/workflows/catalogue.py`:
    - `cron=f"{randint(0, 59)} 4 * * *"`, `concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW` and low priority, following `ANONYMOUS_TELEMETRY_SEND`
    - add it to the workflows list there

**Checkpoint**: T016 to T018 pass. Statistics exist in the cache after a run.

---

## Phase 5: User Story 1 (P1), part C: estimate in the cost details

**Goal**: each field in `extensions.query_cost` carries an expected and a worst-case estimate next to its actual counts. The top-level nodes and the fields directly under them are counted on the request's branch and time.

Requirements: FR-004, FR-005, FR-007, FR-008, FR-012, FR-013, FR-014, FR-017, SC-003 and SC-004.

**Independent Test**: refresh the statistics on a fixture, run queries with the header, and compare each field's expected and worst-case figures with values computed by hand and with the actual counts.

### Tests for part C

- [X] T025 [P] [US1] Write unit tests in `backend/tests/unit/graphql/cost/test_estimator.py`, with dataclass test cases and hand-built snapshots. Check:
    - expected nodes = paths × mean; cardinality-one fields use the share of nodes with a peer
    - expected paths are split by `peers_by_kind` (FR-005, FR-008)
    - the worst-case bound equals the largest value found by brute force over every assignment of paths to nodes on small degree sequences, and over every way to give 4 cars to 3 persons for a query from many nodes to one node and back out (FR-008)
    - with 3, 2 and 1 cars, the bound for that query (15) is above the largest value (14), because it keeps only the largest number of paths that reach one node
    - when a histogram is missing, the worst case is the product of the maximum peers at each step
    - `worst_case ≥ expected` for each figure (FR-007)
    - label scaling: `active_count × current label count ÷ label_count` (FR-017)
    - a listed node uses its stored peer count (FR-018)
    - a side without statistics gives `reason = "no statistics"` (FR-012)
    - `selects_count` adds one row for each parent node (FR-014)
    - a nested `limit` caps the peers of each parent
    - the rows model of research D10, for each resolver path, including a cardinality-one field that selects only `id` (0 rows)
    - `worst_case_is_bound` is false on a branch other than main or with an `at` time
- [X] T026 [P] [US1] Write unit tests in `backend/tests/unit/graphql/cost/test_tree.py` on queries over `car_person_schema_generics`. Check:
    - paths are equal to those the recorder computes for the same response
    - fields with the same path are merged (E2)
- [X] T027 [P] [US1] Write component tests in `backend/tests/component/graphql/cost/test_estimate.py`. Refresh the statistics first, then run queries with the header:
    - every field has both an estimate and actual counts (FR-004)
    - two concrete car kinds under one generic with very different peer counts are counted for each concrete kind (FR-005)
    - a branch that adds cars to the target person gives counted figures that match the branch (FR-013)
    - on unchanged data, no actual count exceeds the worst case on any field, including for a query `TestPerson/cars/owner/cars` (FR-008)
    - a relationship added to the schema after the refresh has `reason = "no statistics"` and filled actual counts (FR-012)
    - a `count` field and a `display_label` field: the estimate covers `count` and not the display label reads (FR-014)
    - nodes created after the refresh are in the estimated node count of a statistics-only top level (FR-017)
    - `estimate_queries.queries ≤ 1 + the number of relationship fields directly under the top-level field` (SC-003)
    - on a fixture where one person owns far more cars than the others, the field with the most `actual.resolver_calls` is the field under `cars` (SC-004)
    - with `query_size_limit` pinned below the number of matching top-level nodes, the fields under the top level have `source = "statistics"` (research D9)

### Implementation for part C

- [X] T028 [US1] In `backend/infrahub/graphql/analyzer.py`, change `GraphQLQueryNode` and `_populate_field_node`:
    - keep the response key (the alias, or the field name)
    - keep the `RelationshipSchema` already looked up for relationship fields, which is discarded today
    - mark whether `count` is selected under a many-cardinality field
    - keep every existing output the same; `backend/tests/component/graphql/test_query_analyzer.py` must still pass
- [X] T029 [US1] Create `backend/infrahub/graphql/cost/tree.py` with `build_cost_tree(analyzer, schema, schema_branch, variable_values: dict | None) -> list[CostTreeField]`:
    - coerce variables with `graphql.execution.values.get_variable_values` and arguments with `get_argument_values`
    - merge fields with the same path
    - skip root fields that do not map to a kind
    - count the selected attributes and cardinality-one relationships
    - set `id_only`
    - mark `ancestors`/`descendants` as hierarchical (no statistics)
    - narrow the parent kinds (`parent_kinds`) of the fields selected inside an inline fragment; the fragment does not change which nodes the field returns, so `concrete_kinds` stays whole
    - set `selects_nodes` (false for a field that selects only `count`) and `max_matching_nodes` (the IDs given, or one for a single-target filter)
- [X] T030 [US1] Add the first-step queries to `backend/infrahub/graphql/cost/queries.py`:
    - `FirstStepNodesQuery`: built on the filter logic of `infrahub.core.query.node::NodeGetListQuery`, for one top-level field with its filters, `limit` and `offset`, on the request's branch and `at`. It returns one row for each concrete kind, with the count, up to `query_size_limit` IDs, and the current label counts of the kinds in the tree, in one query.
    - `FirstStepPeerCountQuery`: a subclass of `RelationshipGetPeerQuery` with the same filters and active-edge rules. For each concrete peer kind it returns the paths, the distinct peers and the largest number of top-level nodes that reach one peer.
- [X] T031 [US1] Create `backend/infrahub/graphql/cost/first_step.py` with `FirstStepCounter(db, branch, at)`. Its `count(tree) -> FirstStepCounts` runs inside `resolving_field(ESTIMATE_FIELD_PATH)`: one `FirstStepNodesQuery` for each top-level field, then one `FirstStepPeerCountQuery` for each relationship field directly under it. A top-level field that matches more than `query_size_limit` nodes is not counted below its own count. Add `read_label_counts(kinds)`, which uses `KindLabelCountQuery` in statistics-only mode.
- [X] T032 [US1] Create `backend/infrahub/graphql/cost/estimator.py` with a pure function `estimate(tree, snapshot, first_step, label_counts, reads_main_now) -> QueryEstimate`, implementing research D10. It has no I/O and no imports from `infrahub.database`. `FirstStepCounts` and its value types are in `backend/infrahub/graphql/cost/models.py` (`data-model.md`, "First-step counts").
- [X] T033 [US1] Create `backend/infrahub/graphql/cost/service.py` with `QueryCostEstimator(db, branch, at, schema_branch, store, snapshot_holder)`. Its method `estimate(analyzer, schema, variable_values: dict | None) -> QueryEstimate` builds the tree, then either counts the first step (`variable_values` given) or reads label counts (statistics-only), then loads the snapshot and calls `estimator.estimate`.
- [X] T034 [US1] In `backend/infrahub/graphql/app.py::InfrahubGraphQLApp._handle_http_request` and `backend/infrahub/api/query.py::execute_query`:
    - after the permission check and inside `activate_recorder`, call `QueryCostEstimator.estimate(...)` with the request's variables (always given on these endpoints; research D9)
    - pass the result to `build_query_cost_details` in place of `None`
    - use one `StatisticsSnapshotHolder` for each process

**Checkpoint**: T025 to T027 and every Phase 3 test pass. User Story 1 is complete.

---

## Phase 6: User Story 2 (P1): estimate from the report without running the query

**Goal**: `InfrahubGraphQLQueryReport` accepts `variables` and returns `cost_estimate` to accounts that can read every kind in the submitted query.

Requirements: FR-003, FR-006, FR-010, FR-011 and FR-018.

**Independent Test**: submit a fixture query to the report with and without `variables`, with an account that can read every kind and with one that cannot.

### Tests for User Story 2

- [ ] T035 [P] [US2] Add tests to `backend/tests/component/graphql/queries/test_graphql_query_report.py`, keeping the existing ones unchanged:
    - with `variables`, `mode = COUNTED_FIRST_STEP` and each field's figures equal the values computed by hand (FR-003)
    - without `variables`, `mode = STATISTICS_ONLY`, every `source = STATISTICS`, and `CountingInfrahubDatabase` records no query other than the label-count read (FR-006)
    - `variables: {}` on a query that declares no variables gives `COUNTED_FIRST_STEP`
    - `statistics.branch == "main"` and `statistics.computed_at` equals the pointer's time (FR-011)
    - a statistics-only estimate for a query on literal `ids` of a person in `top_nodes` uses that person's stored peer count for `cars` (FR-018)
    - a mutation returns exactly "The cost estimate covers queries only."
    - a variable of the wrong type returns the graphql-core coercion error
    - selecting only `targets_unique_nodes` runs no counting query
- [ ] T036 [P] [US2] Write component tests in `backend/tests/component/graphql/queries/test_graphql_query_report_permissions.py`, using `permissions_helper` from `backend/tests/component/graphql/conftest.py`:
    - an account without view permission on `TestCar` gets, from the report's `cost_estimate`, the same `PermissionDeniedError` message that running the submitted query through `/graphql` returns, and no counts (FR-010)
    - an account with permission gets the estimate

### Implementation for User Story 2

- [ ] T037 [US2] In `backend/infrahub/graphql/queries/graphql_query_report.py`, add the graphene types of `contracts/graphql_query_report.graphql`:
    - `GraphQLQueryCostEstimateMode`, `GraphQLQueryCostSource`, `GraphQLQueryCostStatistics`, `GraphQLQueryCostFigures`, `GraphQLQueryFieldCostEstimate` and `GraphQLQueryCostEstimate`
    - a `cost_estimate` field on `GraphQLQueryReport` with its own resolver
    - `variables = GenericScalar(required=False)` on `InfrahubGraphQLQueryReport`
    - `resolve_graphql_query_report` returns what the child resolver needs (analyzer, variables, whether `variables` was given) next to `targets_unique_nodes`, and computes nothing extra
- [ ] T038 [US2] Implement the `cost_estimate` resolver in `backend/infrahub/graphql/queries/graphql_query_report.py`. In order, it:
    - raises a GraphQL error "The cost estimate covers queries only." when the submitted analyzer contains a mutation
    - runs the permission checker pipeline built by `infrahub.graphql.api.dependencies::build_graphql_query_permission_checker` on the submitted query's analyzer, with the request's account session, branch and database (FR-010)
    - calls `QueryCostEstimator.estimate(...)` with `variable_values` set only when `variables` was given (research D9)
    - maps the `QueryEstimate` to the graphene types

**Checkpoint**: T035 and T036 pass. Both user stories work on their own.

---

## Phase 7: Polish and cross-cutting concerns

- [ ] T039 Regenerate `schema/schema.graphql` with `uv run invoke schema.generate-graphqlschema`. Then regenerate the frontend types with `cd frontend/app && pnpm codegen:graphql` and commit `frontend/app/src/shared/api/graphql/generated/graphql-env.d.ts` and `graphql-cache.d.ts` (`dev/knowledge/backend/code-generation.md`).
- [ ] T040 [P] Write `docs/docs/development-resources/graphql/query-cost.mdx` with the content listed in `plan.md` "User documentation". Add it to `docs/sidebars.ts` next to `development-resources/graphql/single-target-queries`, link it from `single-target-queries.mdx`, and run `uv run invoke docs.lint`. Use the `opsmill-docs:writing-infrahub-docs` skill.
- [ ] T041 [P] Write `dev/knowledge/backend/graphql-query-cost.md` and list it in `dev/README.md` next to `graphql-execution.md` (`dev/guidelines/documentation.md`). It covers:
    - the recorder `ContextVar`s and why no middleware is used
    - the statistics cache layout and versioning
    - the refresh by chunks of IDs
    - the estimator
    - the known limits: shared `NodeDataLoader` batches, statistics of main only, correlation between steps
- [ ] T042 [P] Add the changelog fragment `changelog/+graphql-query-cost.added.md` with the `creating-changelog-entries` skill.
- [ ] T043 Run `EXPLAIN` on `RelationshipSideDegreeQuery`, `FirstStepNodesQuery` and `FirstStepPeerCountQuery` against a database seeded with at least 100,000 nodes of one kind. Check that `n.uuid IN $ids` uses the `node_uuid` index and that the first-step queries do not scan every node of a kind they do not need. Record the plans in `dev/specs/infp-739-graphql-query-cost/pr-description.md` (constitution Principle V).
- [ ] T044 Run steps 1 to 8 of `dev/specs/infp-739-graphql-query-cost/quickstart.md` on a development stack. Record the results in `dev/specs/infp-739-graphql-query-cost/pr-description.md`.
- [ ] T045 Run `/pre-ci`: format, lint (including `ruff check . --exclude python_sdk`), mypy, unit tests of the changed areas, `uv run invoke docs.validate` and generated-file validation. Fix what it reports, and list the checks run in `dev/specs/infp-739-graphql-query-cost/pr-description.md`.
- [ ] T046 Outside this repository: in `opsmill/infrahub-private-tests`, open a PR with:
    - a synthetic data set that reproduces the customer's distribution, including the correlation between steps
    - a check that the estimated single-relationship resolver calls of a `CablingPlanLogical`-shaped query, with the first step counted, are between half and twice the actual count (SC-001)

  Spec open question 2 asks whether that repository's CI needs a change. Record the PR link in `pr-description.md`. The implement phase in this repository does not run this task.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after T002.
- **Phase 3 (US1 part A)**: after Phase 2. It delivers the MVP on its own.
- **Phase 4 (US1 part B)**: after Phase 2. It can run in parallel with Phase 3 (different files), but the delivery order puts it after Phase 3.
- **Phase 5 (US1 part C)**: after Phases 3 and 4.
- **Phase 6 (US2)**: after Phase 5 (T029 to T033). It does not depend on T034.
- **Phase 7**: after Phase 6. T046 is outside this repository.

### Task dependencies inside phases

- T012, T013, T014 and T015 depend on T011. T014 and T015 also depend on T006.
- T021 depends on T019 and T020. T023 depends on T021 and T022. T024 depends on T023.
- T029 depends on T028. T031 depends on T030. T033 depends on T029, T031, T032 and T022. T034 depends on T033.
- T038 depends on T037 and T033.
- T039 depends on T037. T040 to T042 start after Phase 6.

### Parallel opportunities

- Phase 2: T003, T004, T005 and T006 (two test files, two source files).
- Phase 3: T007, T008, T009 and T010 together, before T011.
- Phase 4: T016, T017 and T018 together, and T019 in parallel with T020.
- Phase 5: T025, T026 and T027 together. T032 (pure function) in parallel with T030 and T031.
- Phase 6: T035 and T036 together.
- Phase 7: T040, T041 and T042 together.

### Parallel example: Phase 4

```text
Task: "T016 [P] [US1] Unit tests for the histogram in backend/tests/unit/graphql/cost/test_histogram.py"
Task: "T017 [P] [US1] Unit tests for the statistics store in backend/tests/unit/graphql/cost/test_statistics_store.py"
Task: "T018 [P] [US1] Component tests for the refresh in backend/tests/component/graphql/cost/test_refresh.py"
Task: "T019 [P] [US1] RelationshipSideAccumulator in backend/infrahub/graphql/cost/histogram.py"
```

---

## Implementation Strategy

### MVP first

1. Phases 1 and 2.
2. Phase 3: actual counts on `/graphql` and `/api/query`.
3. Stop and check: an engineer can find the field that multiplies the rows from the actual counts alone.

### Incremental delivery

1. Phase 3: actual counts, with every estimate marked "no statistics".
2. Phase 4: statistics in the cache, refreshed daily.
3. Phase 5: estimates next to the actual counts. User Story 1 is complete.
4. Phase 6: the report. User Story 2 is complete.
5. Phase 7: generated files, docs, checks.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T008, T010, T011–T015 |
| FR-002 | T008, T009, T012, T013 |
| FR-003 | T035, T037, T038 |
| FR-004 | T027, T034 |
| FR-005 | T025, T027, T030, T031 |
| FR-006 | T035, T033, T038 |
| FR-007 | T025, T032 |
| FR-008 | T025, T027, T032 |
| FR-009 | T016, T018, T019–T021 |
| FR-010 | T036, T038 |
| FR-011 | T018, T035, T022 |
| FR-012 | T025, T027, T032 |
| FR-013 | T027, T030 |
| FR-014 | T008, T025, T027, T029 |
| FR-015 | T008, T014, T015 |
| FR-016 | T018, T023, T024 |
| FR-017 | T025, T027, T030 |
| FR-018 | T025, T035, T032 |
| SC-001 | T046 (outside this repository) |
| SC-002 | T009 |
| SC-003 | T027 |
| SC-004 | T027 |

## Notes

- [P] tasks touch different files and depend on no unfinished task.
- Write each test before the code it covers, and check that it fails first.
- Commit after each task or logical group.
- Comments and docstrings follow `.agents/rules/code-doc-style.md`: no references to spec IDs, tickets or callers.
