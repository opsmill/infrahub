# Research: Number Pools P1 — Weighted Ranges

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-09-17

Code references are `module::Symbol` against branch `pmi-number-pools-part1` (based on `stable`).

## Current state, verified

| Concern | Where it lives today | Behaviour |
|---------|---------------------|-----------|
| Pool node | `backend/infrahub/core/schema/definitions/core/resource_pool.py::core_number_pool` | `Core` namespace, `branch=AGNOSTIC`, attributes `node`, `node_attribute`, `start_range` and `end_range` (Number, `optional=False`), `pool_type` (enum User/Schema, read-only). No relationships of its own. |
| Weighted generic | `resource_pool.py::core_weighted_pool_resource` | `CoreWeightedPoolResource`, `branch=AWARE`, one optional Number attribute `allocation_weight`. No core kind inherits it; customers add it to their prefix kinds. |
| Inheritance and branch support | `backend/infrahub/core/schema/schema_branch.py::SchemaBranch.process_branch_support` | An inherited attribute whose branch support equals the generic's is reset to the inheriting node's branch support. An agnostic node inheriting the aware generic gets an agnostic `allocation_weight`. |
| Weight ordering | `backend/infrahub/core/node/resource_manager/ip_prefix_pool.py::CoreIPPrefixPool.get_next` | `sorted(..., key=allocation_weight or 0, reverse=True)`; no secondary key, ties follow dict order. |
| Allocation | `backend/infrahub/core/node/resource_manager/number_pool.py::CoreNumberPool.get_next` | Effective span `max(start_range, min_value)` to `min(end_range, max_value)`; excluded singles and excluded ranges from the attribute parameters; on a unique attribute, `get_taken` adds hand-set values to the skip set; a `skip_excluded` closure walks past skipped values; `get_free` re-queried from the new cursor. Pool lock keyed `resource_pool.<pool_id>`. |
| Size and utilization | `backend/infrahub/pools/number.py::NumberUtilizationGetter` | `total_pool_size = end_range - start_range + 1 - nb_excluded`, where `nb_excluded` counts every excluded value whether or not it sits inside the span. Ignores `min_value` / `max_value`. Division by `total_pool_size` with no zero guard. |
| Free-number query | `backend/infrahub/core/query/resource_manager.py::NumberPoolGetFree` | Cypher gap walk over one contiguous span (`expected = idx - 1 + $start_range`); `limit = 1`. Cannot take a discontinuous span as written. |
| Used / allocated / taken | `resource_manager.py::NumberPoolGetUsed`, `NumberPoolGetAllocated`, `NumberPoolGetTaken` | All filter `value >= $start_range AND value <= $end_range`. Liveness join `n.uuid = res.identifier`. `GetTaken` uses the non-isolated branch filter, like the uniqueness validator. |
| GraphQL utilization | `backend/infrahub/graphql/queries/resource_manager.py::resolve_number_pool_utilization` | One synthetic edge with `weight: 1`; IP pools return one edge per resource. |
| Pool mutation | `backend/infrahub/graphql/mutations/resource_manager.py::InfrahubNumberPoolMutation` | Create validates the target attribute, `start_range <= end_range`, and the bounds against `min_value` / `max_value`. Update refuses `node` / `node_attribute` changes and refuses `start_range` / `end_range` on `pool_type == Schema` with "update the schema in the default branch instead". `data["start_range"]` is read unconditionally. |
| Mutation registration | `backend/infrahub/graphql/manager.py::generate_mutation_mixin` | Local `mutation_map` keyed by `InfrahubKind`; a kind without an entry receives the generic mutations. |
| Attribute parameters | `backend/infrahub/core/schema/attribute_parameters.py::NumberPoolParameters` | `start_range: int = 1`, `end_range: int = sys.maxsize`, both `update: VALIDATE_CONSTRAINT`; `number_pool_id`. `validate_ranges` refuses `start > end`. `get_pool_size()`. |
| Legacy parameter reconciliation | `schema_branch.py::SchemaBranch._reconcile_legacy_attr_params` | Text-kind only; `parameters` win silently over `regex` / `min_length` / `max_length`. Does nothing for NumberPool. |
| Constraint name derivation | `backend/infrahub/core/models.py::SchemaUpdateValidationResult._process_node_fields` | A changed field inside `parameters` derives `attribute.parameters.<field>.update`, using the nested field's own `update` marker. Precedent: `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE = "attribute.parameters.start_range.update"`. |
| Unregistered constraint | `models.py::SchemaUpdateValidationResult.validate_constraints` | Appends `VALIDATOR_NOT_AVAILABLE` ("Validator ... is not available yet"), failing the schema load. |
| Nested list diff | `models.py::HashableModel.diff`, `_get_signature_field` | A list field is `sorted()`; items that are `HashableModel` need `_sort_by`, otherwise `TypeError`. |
| Range checker | `backend/infrahub/core/validators/attribute/number_pool.py::AttributeNumberPoolChecker` | Registered for the start and end identifiers in `validators/__init__.py::CONSTRAINT_VALIDATOR_MAP`; query returns latest active values `< start OR > end`. |
| Schema pool creation | `backend/infrahub/pools/schema_number_pool_upserter.py::SchemaNumberPoolUpserter.upsert_number_pool` | Under a distributed lock, `Node.init(NUMBERPOOL).new(name, node, node_attribute, start_range, end_range, pool_type="Schema")`. Also called from `core/migrations/schema/node_attribute_add.py` which allocates for existing nodes right after. |
| Schema pool sync | `backend/infrahub/pools/schema_number_pool_synchronizer.py::SchemaNumberPoolSynchronizer._update_pool_from_schema` | Reads the default-branch declaration; compares the two scalars; saves when different. Triggered by the `validate-schema-number-pools` flow after every schema load and after branch merge. |
| Deprecation on schema fields | `core/schema/definitions/internal.py` (`deprecation` on attributes and relationships), `schema_branch.py::SchemaBranch.process_deprecations` | Forces `optional=True` and logs a warning. Nothing propagates it to GraphQL; `graphql/manager.py` never passes `deprecation_reason`. |
| Deprecation in graphene | graphene 3.4.3, graphql-core 3.2.8 | `Field`, `InputField`, `Argument` accept `deprecation_reason`; a required input field cannot be deprecated. Generated inputs are never `required=True`. |
| Schema-load warnings | `backend/infrahub/core/schema/__init__.py::SchemaRoot.gather_warnings` | Emits `SchemaWarning(type=DEPRECATION)` for legacy `regex` / `min_length` / `max_length`; consumed by `api/schema.py::load_schema` and `check_schema`. |
| "(required)" suffix | `graphql/manager.py::GraphQLSchemaManager.generate_graphql_object` | Appended to the description of non-optional attributes; the only site. |
| Published contract | `tasks/backend.py` (`number_pool_parameters_fields`, `_field`, `_sdk_extension_field`), ADR 0010 | SDK parameter families are hand-listed, scalar-only; generated into `python_sdk/infrahub_sdk/schema/generated/`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, `docs/docs/snippets/attribute-kind-params.mdx`. |
| Frontend readers | `frontend/app/src/entities/schema/ui/attribute-display.tsx`, `entities/resource-manager/ui/number-pool-form.tsx` | GraphQL types already `Maybe<>`; REST parameter types are non-optional; attribute display formats `parameters.start_range` without a null guard; the pool form tolerates missing values. |
| Migrations | `backend/infrahub/core/migrations/graph/`, `core/graph/__init__.py::GRAPH_VERSION = 78` | Next is `m079`, `minimum_version = 78`. Graph migrations run before `cli/db.py::update_core_schema`; `m073` bootstraps a new core kind inside the migration with `registry.schema.create_node_in_db`, guarded by a count query. |
| Benchmarks | `backend/tests/query_benchmark/` | No pool benchmark exists; `test_node_unique_attribute_constraint.py` is the pattern. |

## Decisions

### D1. Range is a new core kind inheriting the weighted generic

**Decision**: `CoreNumberPoolRange` (`Core` namespace, `branch=AGNOSTIC`, `inherit_from=[CoreWeightedPoolResource]`, `include_in_menu=False`, `generate_profile=False`), attributes `start` and `end` (Number, required), relationship `pool` (peer `CoreNumberPool`, cardinality one, required, kind `PARENT`, agnostic). `CoreNumberPool` gains `ranges` (peer `CoreNumberPoolRange`, cardinality many, optional, kind `COMPONENT`, agnostic, identifier `numberpool__range`). New constant `InfrahubKind.NUMBERPOOLRANGE`.

**Rationale**: the PRD asks for a kind, not a list attribute, so ranges can be added and removed one at a time and carry the same weight semantics as IP pool resources. `process_branch_support` makes the inherited `allocation_weight` agnostic, so the aware generic needs no change.

**Alternatives**: a JSON list attribute on the pool (no per-range identity, no per-range edit, no weight generic); a new generic for number ranges (a second word for the same idea).

### D2. The shorthand scalars stay stored and mirror the range set

**Decision**: `start_range` / `end_range` remain attributes on `CoreNumberPool`, `optional=True`, with a `deprecation` message. One helper, `sync_shorthand_from_ranges(pool)` in `core/node/resource_manager/number_pool.py`, writes them from the range set: the single range's bounds when the pool holds exactly one range, `None` otherwise. Every write path that changes ranges calls it: the range mutation class, the pool mutation, the schema upserter and synchronizer, and the data migration.

**Rationale**: a derived read would need a custom resolver inside the generic GraphQL generator and would leave the SDK's generic node queries without a value. Mirroring keeps the read shape generic and the invariant lives in one function.

**Alternatives**: derive on read (generator special case, rejected for the same reason the addendum rejects field-specific deprecation); drop the scalars (breaks every existing consumer).

**Rollback property**: a server running the previous release reads the populated shorthand on every single-range pool and ignores `ranges`, so rolling back after m079 loses nothing for pools that have not been given a second range.

### D3. Effective-space calculator, pure Python

**Decision**: new module `backend/infrahub/pools/number_ranges.py` with frozen dataclasses `PoolRange(start, end, weight, id)` and `EffectiveSegment(start, end, range_id)` and a class `EffectiveSpace` built from ranges plus the attribute's `NumberAttributeParameters`. It exposes `segments` in allocation order (weight desc, start asc; a range clipped to nothing yields no segment), `size`, `contains(value)`, `range_for(value)`, and `segments_of(range_id)`. Excluded singles and excluded ranges split the clipped ranges into segments, so a segment never contains a statically excluded value. Weight `None` counts as 0.

**Rationale**: PRD principle "one arithmetic". Size, utilization, allocation order and fullness read the same object. The `ZeroDivisionError` disappears because size is a sum of segment sizes and callers guard `size == 0`.

**Alternatives**: keep the closure-based skip in `get_next` and patch `total_pool_size` (three implementations remain).

### D4. Allocation walks segments with the existing single-span gap query

**Decision**: `CoreNumberPool.get_next` builds the `EffectiveSpace`, loads hand-set values once over the whole segment list when the attribute is unique (`NumberPoolGetTaken` with a `$ranges` parameter), then for each segment in order runs `NumberPoolGetFree(min_value=cursor, max_value=segment.end)`; a candidate that is hand-set advances the cursor and re-queries; a segment with no free value falls through to the next; no segment left raises `PoolExhaustedError`. `NumberPoolGetFree` keeps its contiguous-span arithmetic, with both bounds required.

**Rationale**: gap detection stays in Cypher; a fully allocated heavy range costs one query returning no free value before fall-through; the number of segments is small. No new discontinuous gap arithmetic in Cypher. A hand-set value hit inside a segment costs one re-query, as today; the benchmark records it.

**Alternatives**: one query taking `$ranges` and running the gap walk per range in an `UNWIND` (more Cypher, same round trip count in the common case; revisit if the benchmark in SC-005 says so).

### D5. Read queries take a range list

**Decision**: `NumberPoolGetUsed`, `NumberPoolGetAllocated`, `NumberPoolGetTaken` replace `$start_range` / `$end_range` with `$ranges: list[list[int]]` and filter `any(r IN $ranges WHERE v >= r[0] AND v <= r[1])`. Callers pass the effective segments. Callers short-circuit on an empty list and never run the query.

**Rationale**: records outside every segment become invisible without any write (FR-003); re-adding a covering range makes them visible again.

### D6. Utilization per range, zero-size guard

**Decision**: `NumberUtilizationGetter` takes the `EffectiveSpace`; `total_pool_size = space.size`; every ratio returns `0.0` when size is 0; used values are grouped by `range_for(value)`. `resolve_number_pool_utilization` returns one edge per range (`kind: CoreNumberPoolRange`, `display_label: "<start>-<end>"`, `weight: allocation_weight or 0`, per-range ratios) and pool totals; `count` is the number of ranges. `get_attribute_nb_excluded_values` is deleted.

**Rationale**: matches the IP pool shape that the frontend already renders, and gives the deferred frontend what it needs without a second contract change.

### D7. Data migration m079 bootstraps the range kind and materialises one range per pool

**Decision**: `m079_number_pool_ranges` is an `ArbitraryMigration`. It bootstraps `CoreNumberPoolRange` and the `ranges` relationship into the database schema the way `m073` bootstraps the IP pool generic, then, through the Node API, creates one range (`start = start_range`, `end = end_range`, no weight) for every live `CoreNumberPool` that has no range peer. `validate_migration` counts pools without ranges. `GRAPH_VERSION` becomes 79.

**Rationale**: graph migrations run before the core schema update, so the kind must exist before ranges can be written. The "has a range → skip" guard makes re-runs create nothing (SC-004).

**Alternatives**: raw Cypher node creation (easy to miss metadata edges); deferring materialisation to the first schema sync (pools created by users would stay range-less until then).

### D8. Attribute parameters: `ranges` list, shorthand optional, conflicts are errors

**Decision**: `NumberPoolParameters` gains `ranges: list[NumberPoolRangeParameters] = []` with `update: VALIDATE_CONSTRAINT`; `NumberPoolRangeParameters(HashableModel)` has `start: int`, `end: int`, `weight: int | None = None`, `_sort_by = ["start", "end"]`. `start_range` and `end_range` become `int | None = None`, keep their marker, and gain a deprecation note in their description. `validate_ranges` refuses: both spellings; `start > end` on any range; overlap between ranges. A new method `effective_ranges()` returns the normalised list: the explicit list, or a single range built from the shorthand with a missing bound resolved to `1` / `sys.maxsize`, or an empty list. Fields are never rewritten during validation. `get_pool_size()` sums the effective ranges.

**Rationale**: leaving the user's fields untouched lets `gather_warnings` detect the shorthand and keeps the hash stable. The error on both spellings is FR-031 and diverges on purpose from the Text-kind reconciliation.

### D9. Schema-change validation for `ranges`

**Decision**: add `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_RANGES_UPDATE = "attribute.parameters.ranges.update"`, register `AttributeNumberPoolChecker` for it, extend `supports()`, and rewrite `AttributeNumberPoolUpdateValidatorQuery` to bind `$ranges` from `effective_ranges()` and return values where `none(r IN $ranges WHERE value >= r[0] AND value <= r[1])`. The two legacy identifiers stay registered; they fire when a shorthand bound changes and the query reads the effective range set either way. Zero declared ranges with held values refuses the load, which is FR-025 applied literally.

**Rationale**: verified derivation in `_process_node_fields`; without the registration a change to `ranges` fails every schema load with "Validator ... is not available yet".

### D10. Upserter and synchronizer own the range nodes of schema pools

**Decision**: `SchemaNumberPoolUpserter.upsert_number_pool` creates the range nodes from `effective_ranges()` right after the pool, under the same lock and timestamp, then calls `sync_shorthand_from_ranges`. `SchemaNumberPoolSynchronizer._update_pool_from_schema` reconciles: desired ranges sorted by start are matched positionally to existing ranges sorted by start; matched ranges are updated in place (bounds and weight), extra ranges are deleted, missing ranges are created; then the shorthand is synced. The `pool_type == Schema` gate is unchanged.

**Rationale**: in-place update keeps range identity for the common case (one range edited); the migration in `node_attribute_add.py` allocates immediately after upsert, so ranges must exist at that point.

### D11. GraphQL mutations and guards

**Decision**: new `InfrahubNumberPoolRangeMutation` in `graphql/mutations/resource_manager.py`, registered under `InfrahubKind.NUMBERPOOLRANGE` in the `mutation_map`. Create, update and delete take the pool lock (`resource_pool.<pool_id>`, the same lock allocation holds), load the parent pool, and refuse with the existing default-branch message when `pool_type == Schema`; create and update validate `start <= end` and refuse overlap with the pool's other ranges naming the clashing ranges; a range partly or wholly outside the attribute's `[min_value, max_value]` is accepted and clamped by the calculator; after the write, `sync_shorthand_from_ranges`. `InfrahubNumberPoolMutation` changes: create accepts the shorthand, `ranges`, or neither; shorthand plus `ranges` is refused; shorthand alone creates the pool and one range; existing bound checks against `min_value` / `max_value` stay. Update: the schema-pool guard also covers `ranges`; the shorthand follows the range count rule (0 creates, 1 rewrites in place, more than 1 is refused with the range list); a `ranges` edit on a user pool is followed by overlap validation and the shorthand sync. Any update that touches the shorthand or `ranges` runs under the pool lock, so validation, write and allocation are serialised.

**Rationale**: both writable surfaces are guarded (addendum 3.1); clamping is the single rule for ranges outside the attribute domain (FR-008), so no new refusal is added; the pool lock closes the read-validate-write race between two range writes and between a range write and an allocation.

### D12. Deprecation reaches GraphQL by general propagation

**Decision**: `graphql/manager.py` passes `deprecation_reason=attr.deprecation` and `rel.deprecation` in `generate_graphql_object`, `generate_interface_object`, the relationship field construction in `generate_object_types`, and the three input generators. Filter arguments are left alone. `SchemaRoot.gather_warnings` adds one `DEPRECATION` warning per NumberPool attribute whose `start_range` or `end_range` is not `None`, pointing at `parameters.ranges`. `SchemaBranch.process_deprecations` keeps forcing `optional=True` but logs only for kinds outside the `Core` namespace.

**Rationale**: the addendum's resolved finding 6.1; restricting the log keeps the customer-facing reminder meaningful once a core attribute is deprecated.

### D13. Published contract and SDK

**Decision**: in `tasks/backend.py`, add a `NumberPoolRange` family (`start`, `end` Number required, `weight` Number optional) and change `number_pool_parameters_fields`: `start_range` and `end_range` optional with no default and a deprecation description, `ranges` as a list of the new family through `_sdk_extension_field`. Regenerate SDK models, `schema/openapi.json`, frontend REST types, the docs snippet. The SDK change is a separate PR on `opsmill/infrahub-sdk-python` (branch `stable`) that must land before the submodule pointer bump.

**Rationale**: ADR 0010 makes the parameter shape a contract; the generator today only knows scalars.

### D14. Frontend: tolerance only

**Decision**: null-guard `attribute-display.tsx` and render `ranges` when present; regenerate GraphQL and REST types; update the schema-viewer fixture. No range management UI.

### D15. Tie-breaking and weight semantics

**Decision**: order by `(-weight, start)`. Weight `None` is 0. Within a segment, lowest free first. Fall-through is automatic from the ordered segment list.

**Rationale**: FR-004. IP pools keep their dict-order ties; a shared helper is not extracted because the IP pool order is a different data shape and the constitution asks for two callers before extraction.

### D16. Benchmark

**Decision**: `backend/tests/query_benchmark/test_number_pool_allocation.py` builds a 4094-number pool split into four ranges, allocates it fully, then benchmarks one `get_next` call (exhausted heaviest range, fall-through) and prints `EXPLAIN` of `NumberPoolGetFree` on the last segment. Recorded, not gated.

## Resolved unknowns

| Question | Answer |
|----------|--------|
| Constraint name for a nested parameter field | `attribute.parameters.ranges.update` (derived by `_process_node_fields`, precedent `attribute.parameters.start_range.update`). |
| Can an agnostic node inherit the aware weighted generic | Yes; `process_branch_support` resets the inherited attribute to the node's branch support. |
| Deprecation log for core attributes | Restricted to non-`Core` namespaces (D12). |
| Migration ordering versus core schema update | Migration bootstraps the kind (D7, `m073` precedent). |
| Whether legacy start/end constraint identifiers stay registered | Yes (D9). |
| Detecting the shorthand for the schema-load warning | Fields are not rewritten by validation; `start_range is not None or end_range is not None` on the incoming model (D8, D12). |
