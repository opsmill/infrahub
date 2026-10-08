# Data Model: Estimated and Actual Cost of GraphQL Queries

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

The feature adds no schema kind and no graph vertex. Everything below is either a cache entry or an in-memory value inside one request. Internal values are frozen dataclasses. Values that cross the API boundary are Pydantic models, defined in [contracts/](contracts/).

## Statistics store (cache)

### Pointer: `graphql_cost:statistics:current`

| Field | Type | Rule |
| --- | --- | --- |
| `version` | integer | Increases by one at each refresh. |
| `branch` | string | Always `main` in the first version. |
| `computed_at` | timestamp (UTC) | Time the refresh started reading main. |
| `schema_hash` | string | Hash of the main schema the refresh read. |
| `kinds` | list of strings | Concrete kinds that have a kind entry in this version. |

The refresh writes the pointer after every kind entry of the version is written. No expiry.

### Kind entry: `graphql_cost:statistics:v{version}:kind:{kind}`

`KindStatistics`, one for each concrete kind (node, profile and template kinds):

| Field | Type | Rule |
| --- | --- | --- |
| `kind` | string | A concrete kind. Generics have no entry; their count is the sum of their concrete kinds. |
| `label_count` | integer | Label count at refresh time. Includes deleted nodes and nodes that exist only on other branches. |
| `active_count` | integer | Nodes active on main at refresh time. |
| `relationships` | list of `RelationshipSideStatistics` | One for each relationship side read for this kind. |

`RelationshipSideStatistics`:

| Field | Type | Rule |
| --- | --- | --- |
| `identifier` | string | Relationship identifier (`Relationship.name` in the graph). |
| `direction` | `outbound`, `inbound` or `bidirectional` | The side, as the direction of the edges from a node of this kind. |
| `nodes_with_peers` | integer | Nodes of this kind active on main with at least one active peer. `nodes_with_peers ≤ active_count`. |
| `total_peers` | integer | Sum of active peers over all nodes of this kind. Mean = `total_peers / active_count`; 0 when `active_count` is 0. |
| `peers_by_kind` | map of concrete kind to integer | Total peers for each concrete peer kind. The values add up to `total_peers`. |
| `histogram` | list of `HistogramBucket` | Non-empty buckets only, in increasing order. The node counts add up to `active_count`. |
| `top_nodes` | list of `TopNode` | At most 20 entries, in decreasing order of peers. When `active_count ≤ 20`, it lists every node with at least one peer. |

`HistogramBucket`:

| Field | Type | Rule |
| --- | --- | --- |
| `lower` | integer | 0, 1, 2, 4, 8, … |
| `upper` | integer | 0, 1, 3, 7, 15, … (`upper = 2 × lower − 1`, except the buckets 0 and 1) |
| `node_count` | integer | Nodes whose peer count is in `[lower, upper]`. |
| `max` | integer | Largest peer count among those nodes. `lower ≤ max ≤ upper`. |

The median, the 95th percentile and the maximum are read from the histogram: the percentile is the `max` of the bucket that contains it.

`TopNode`:

| Field | Type |
| --- | --- |
| `node_id` | string (UUID) |
| `peers` | integer |

### Lifecycle

```text
(no pointer) --first refresh--> version 1 --refresh--> version 2 --refresh--> ...
```

- Before writing version n+1, the refresh deletes any kind entries already stored under version n+1, which a failed earlier run can leave (critique E4).
- After writing version n+1 and moving the pointer, the refresh deletes the kind entries of version n.
- A reader that read pointer n and finds a kind entry missing reads the pointer again once. If the entry is still missing, the fields of that kind have the reason "no statistics".

### In-process copy: `StatisticsSnapshot`

| Field | Type | Rule |
| --- | --- | --- |
| `pointer` | `StatisticsPointer` | The pointer of the version loaded: version, branch, computed time and schema hash. |
| `kinds` | map of kind to `KindStatistics` | Kinds whose entry was loaded. |

Lookup: `snapshot.side(identifier, direction, kind) -> RelationshipSideStatistics | None`.

## Estimation tree (inside one request)

Built from `GraphQLQueryNode` (the analyzer tree) and the coerced argument values.

`CostTreeField`:

| Field | Type | Rule |
| --- | --- | --- |
| `path` | string | Response keys from the top-level field joined by `/`, without `edges`, `node` and list indexes (research D4). |
| `kind` | string | Peer kind of the field, or the kind of a top-level field. |
| `concrete_kinds` | list of strings | `kind` itself, or the concrete kinds behind a generic. |
| `parent_kinds` | list of strings | Concrete kinds of the parent nodes the field is selected on. An inline fragment around the field narrows them. The fragment does not change which nodes the field returns, so it does not narrow `concrete_kinds`. Empty for a top-level field. |
| `relationship` | `RelationshipRef` or none | None for a top-level field. |
| `cardinality` | `one` or `many` | `many` for a top-level field. |
| `selected_attribute_count` | integer | Attributes selected on the peer, used by the rows model. |
| `selected_cardinality_one_count` | integer | Cardinality-one relationships selected on the peer, used by the rows model. |
| `selects_count` | boolean | `count` is selected on a many-cardinality field. |
| `selects_nodes` | boolean | False for a many-cardinality field that selects only `count`: its resolver returns before it reads a node. |
| `id_only` | boolean | A cardinality-one field that selects only `node { id }`; it reads nothing. |
| `max_matching_nodes` | integer or none | For a top-level field: the number of IDs given, or 1 when the filters pin one node (the analyzer's single-target check). None otherwise. |
| `arguments` | map | Coerced argument values (filters, `limit`, `offset`, `ids`). |
| `children` | list of `CostTreeField` | |

`RelationshipRef`: `identifier`, `direction`, `name` (the field name on the schema), `hierarchical` (true for `ancestors` and `descendants`, which have no statistics).

Tree rules (critique E2):

- Fields with the same path are merged into one `CostTreeField`, the way graphql-core merges selections with the same response key, for example a field selected directly and through a fragment.
- Root fields that do not map to a schema kind, such as `InfrahubSearchAnywhere` or `InfrahubGraphQLQueryReport`, have no tree field and no entry in the cost details.
- Nothing below `ancestors` and `descendants` is in the tree. Those fields have no statistics, and the fields recorded below them are listed from the actual counts.
- A field whose alias is `edges` or `node` gets the path of its parent, as the recorded paths do. The estimate adds its figures to the entry of that path.

## First-step counts (inside one request)

`FirstStepCounts` (frozen) holds what the counted first step reads on the request's branch and `at` time. It is defined in `models.py`, so that the estimator imports nothing from the code that runs the queries. `None` in its place means a statistics-only estimate.

| Field | Type | Rule |
| --- | --- | --- |
| `top_level` | map of path to `FirstStepTopLevelCount` | One entry for each counted top-level field. A top-level field filtered by `hfid` is not counted. |
| `relationships` | map of path to list of `FirstStepPeerCount` | One entry for each relationship field directly under a counted top-level field, with one item for each concrete peer kind. Only the top-level nodes of the field's `parent_kinds` are counted, with the field's filters and without its `offset` and `limit`. A field under a top-level field that exceeds `query_size_limit` has no entry, and neither do `ancestors`, `descendants` and a field with `include_descendants: true`. |
| `label_counts` | map of kind to integer | Current label count of each kind in the query, read by the same queries. |

`FirstStepTopLevelCount`: `kinds` (one `FirstStepKindCount` for each concrete kind with nodes) and `exceeds_size_limit` (the field returns more than `query_size_limit` nodes, so nothing under it is counted).

`FirstStepKindCount`: `kind`, `node_count` (after the filters, `offset` and `limit`) and `node_ids` (at most `query_size_limit` of them).

`FirstStepPeerCount`: `peer_kind`, `paths` (pairs of a top-level node and one of its peers of that kind), `distinct_peers` and `max_parents` (the largest number of top-level nodes that reach one peer).

## Estimate and actual counts

`CostFigures` (frozen): `nodes: int`, `resolver_calls: int`, `database_rows: int`.

`FieldDescription` (frozen): `kind`, `relationship_identifier` (none for a top-level field) and `cardinality`. The cost details show it for every field. The resolvers fill it from the schema objects they already hold, and the estimation tree must give the same values for the same path:

- a relationship field: the peer kind declared on the relationship (the generic, for a generic peer), the relationship identifier and the relationship's cardinality
- a top-level field: the kind of the field, no identifier and `many`
- `ancestors` and `descendants`: the hierarchy kind that the field returns, `parent__child` and `many`

`FieldEstimate`:

| Field | Type | Rule |
| --- | --- | --- |
| `field` | `FieldDescription` | The field the estimate is for. |
| `expected` | `CostFigures` or none | None when `reason` is set. |
| `worst_case` | `CostFigures` or none | None when `reason` is set. `worst_case ≥ expected` for each figure. |
| `source` | `counted`, `statistics` or none | `counted` only for top-level fields and the fields directly under them, when the first step is counted. |
| `worst_case_is_bound` | boolean | True only when the statistics describe the request's branch (main) and the request has no `at` time. Otherwise the worst case promises nothing (FR-008). |
| `reason` | `no statistics` (`EstimateReason`) or none | Set when a kind or relationship side has no statistics (FR-012). When it is set, `source` is none and `worst_case_is_bound` is false. |

`FieldActual`: `field` (the `FieldDescription` given by the resolver calls of the path, none until the first call), `nodes`, `resolver_calls`, `database_rows` (integers, start at 0). A path with rows and no resolver call has no description, so a resolver records its call even when its body raises.

`QueryCostRecorder` (mutable, one for each request with the header): a map of field path to `FieldActual`. It records separately the queries and rows of the counted first step (`estimate_queries`), and the queries and rows that run while no field is set (`unattributed`).

`QueryCostDetails` (the response content; see [contracts/cost-details.schema.json](contracts/cost-details.schema.json)):

- `estimate_mode`: `counted_first_step` or `statistics_only`
- `statistics`: branch, computed time, version, or `null` when no statistics exist
- `fields`: one entry for each field of the estimation tree, in tree order, with its estimate and its actual counts
- `estimate_queries`: database queries and rows that the counted first step ran, or the label-count read in statistics-only mode
- `unattributed`: database queries and rows that ran while no field was set, from the point where the request handler starts the recorder

## Rules taken from the requirements

- FR-001, FR-002: the recorder exists only for requests with the header whose operation is a query.
- FR-005, FR-006: `source = counted` requires variable values. Requests to `/graphql` and `/api/query` always have them. The report has them only when its `variables` argument is given; an empty object counts as given.
- FR-011: every estimate carries the branch and computed time of the statistics it used.
- FR-012: a field whose side has no statistics has `reason = "no statistics"`, and its actual counts are still filled.
- FR-014: `selects_count` adds one resolver call's worth of rows for each parent node. Display labels, profiles and permission filtering are not in the estimate, and their reads are in the actual counts.
- FR-017: estimated node counts use `active_count × current label count ÷ label_count`.
- FR-018: a top-level node listed in `top_nodes` uses its stored `peers`.
