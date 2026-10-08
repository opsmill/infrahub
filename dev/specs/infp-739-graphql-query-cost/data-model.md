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
| `concrete_kinds` | list of strings | `kind` itself, or the concrete kinds behind a generic. An inline fragment narrows it. |
| `relationship` | `RelationshipRef` or none | None for a top-level field. |
| `cardinality` | `one` or `many` | `many` for a top-level field. |
| `selected_attribute_count` | integer | Attributes selected on the peer, used by the rows model. |
| `selected_cardinality_one_count` | integer | Cardinality-one relationships selected on the peer, used by the rows model. |
| `selects_count` | boolean | `count` is selected on a many-cardinality field. |
| `id_only` | boolean | A cardinality-one field that selects only `node { id }`; it reads nothing. |
| `arguments` | map | Coerced argument values (filters, `limit`, `offset`, `ids`). |
| `children` | list of `CostTreeField` | |

`RelationshipRef`: `identifier`, `direction`, `name` (the field name on the schema), `hierarchical` (true for `ancestors` and `descendants`, which have no statistics).

Tree rules (critique E2):

- Fields with the same path are merged into one `CostTreeField`, the way graphql-core merges selections with the same response key, for example a field selected directly and through a fragment.
- Root fields that do not map to a schema kind, such as `InfrahubSearchAnywhere` or `InfrahubGraphQLQueryReport`, have no tree field and no entry in the cost details.

## Estimate and actual counts

`CostFigures` (frozen): `nodes: int`, `resolver_calls: int`, `database_rows: int`.

`FieldDescription` (frozen): `kind`, `relationship_identifier` (none for a top-level field) and `cardinality`. The cost details show it for every field.

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
- `unattributed`: database queries and rows that ran while no field was set

## Rules taken from the requirements

- FR-001, FR-002: the recorder exists only for requests with the header whose operation is a query.
- FR-005, FR-006: `source = counted` requires variable values. Requests to `/graphql` and `/api/query` always have them. The report has them only when its `variables` argument is given; an empty object counts as given.
- FR-011: every estimate carries the branch and computed time of the statistics it used.
- FR-012: a field whose side has no statistics has `reason = "no statistics"`, and its actual counts are still filled.
- FR-014: `selects_count` adds one resolver call's worth of rows for each parent node. Display labels, profiles and permission filtering are not in the estimate, and their reads are in the actual counts.
- FR-017: estimated node counts use `active_count × current label count ÷ label_count`.
- FR-018: a top-level node listed in `top_nodes` uses its stored `peers`.
