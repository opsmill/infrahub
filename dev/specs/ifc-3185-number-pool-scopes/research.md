# Research: Number pool allocation scopes

Each entry records a decision, the reason, and the alternatives considered. Sources: the Notion PRD (allocation scopes part), the Jira tickets of IFC-3185, the description and the diff of PR #10932, the thirteen decisions of the product owner, and the code of the branch `feature-number-pools-1.12`.

## R1. Where the scope is stored

**Decision**: The existing `List` attribute `allocation_scope` of `CoreNumberPool` (`backend/infrahub/core/schema/definitions/core/resource_pool.py`) keeps its kind and holds ordered objects `{"id": <schema element id>, "name": <element name>}` instead of the plain names it holds today.

**Rationale**: The attribute shipped with IFC-3334 and is read by the generic `CoreNumberPool` GraphQL node query like any other attribute. Keeping the `List` kind needs no schema change and no graph migration: no released version stores a scope, so the stored shape changes with the code. Storing the name beside the id satisfies decision 4 on every read, including the generic node query, without a schema lookup per read.

**Alternatives considered**:

- One `CoreNumberPoolScopeElement` node per element, like `CoreNumberPoolRange`: more nodes, a parent relationship and a migration for a list that never changes after creation. Rejected (simplicity).
- Storing ids only and resolving names on every read: the generic node query would show ids only, which contradicts decision 4; and every dedicated query would add a schema lookup. Rejected.
- Keeping the names that the attribute stores today: a rename would silently break the scope. Rejected by decision 3.

## R2. How a name stays current after a rename

**Decision**: `SchemaNumberPoolSynchronizer.run` (`backend/infrahub/pools/schema_number_pool_synchronizer.py`) gains a step that, on each schema update of the default branch, looks every stored element id up in the default branch's schema and rewrites the stored name when it differs. The step covers user-created and schema-created pools.

**Rationale**: The synchronizer already runs after every schema update (`backend/infrahub/schema/tasks.py` runs `backend/infrahub/pools/tasks.py::validate_schema_number_pools`), and already reads the default-branch schema for each schema-created pool. Schema element ids survive a rename: `backend/infrahub/core/migrations/schema/attribute_name_update.py` finds the previous attribute by id, `SchemaBranch.load_schema` matches a loaded item by id when the file carries one, and `BaseNodeSchema.get_attribute_by_id` and `get_relationship_by_id` resolve an element by id.

**Alternatives considered**:

- Refusing the rename of a scoped element (Jira IFC-3352): unnecessary once the id is the reference, and it would force the operator to recreate pools. Overridden by decision 6.
- Refreshing names lazily on read: leaves the stored value stale between the rename and the next read. Rejected.

## R3. What a scope element may reference

**Decision**: A required attribute of a scalar kind (any kind except `List`, `JSON` and `Any`), or a required cardinality-one relationship of the pool's kind, declared on that kind (on the generic itself when the pool's kind is a generic), given as the element id or the element name, not a path (no `__`), not the pool's own tracked attribute, not twice. A scope is refused on a pool whose tracked attribute is `unique: true`.

**Rationale**: PRD FR-015 gives the required and cardinality rules. Jira IFC-3348 adds the generic rule and the `unique: true` rule (a globally unique number cannot repeat per division). Decision 10, revised on 2026-10-09, refuses `List`, `JSON` and `Any` attributes, as Jira IFC-3348 did: a division then holds only scalar values, so Python equality, the Cypher comparison of stored values and the lock key agree without any normalisation. The name resolves within the kind because `SchemaBranch` validates that attribute and relationship names are unique together on one kind. The existing `SchemaBranch.validate_schema_path` with `SchemaElementPathType.ATTR_NO_PROP | REL_ONE_MANDATORY_NO_ATTR` gives the required and cardinality rules for a name, and the resolver reuses it.

**Alternatives considered**:

- Allowing a path into a related node (`site__region`): the division of a node would then depend on another node's attribute, which can change without touching the holding object; the PRD refuses it. Rejected.
- Storing `role__value` as `role` (Jira IFC-3348): a property path is neither a name nor an id. Refused instead (decision 12).
- Accepting `List` and `JSON` attributes and comparing their stored value: the database stores a document with its keys in write order, so a document written in two key orders would make two divisions in Cypher, while any normalisation in Python would make one. Rejected by the revision of decision 10.

## R4. Which schema the scope is resolved against

**Decision**: Always the schema of the default branch, read with `registry.schema.get_schema_branch(name=registry.default_branch)`. A pool created on a branch, or a schema loaded on a branch, that references an element absent from the default branch is refused. A request on a branch whose own schema lacks the element (a branch forked before the element was added, not rebased since) is refused with the element and the branch named.

**Rationale**: Decision 1 and decision 7. Together they remove the "scope in force on the request's branch" variability of PR #10932 and of Jira IFC-3348, IFC-3352 and IFC-3354: an element is either in the branch's schema, and the scope applies whole, or it is not, and the request is refused.

**Alternatives considered**:

- Validation against the branch where the pool is saved (Jira IFC-3348) and a scope that applies only on the branches whose schema defines it (Jira IFC-3354): more states to test and a scope that can change meaning per branch. Overridden by decision 1.
- Applying the elements the branch defines and ignoring the others: a pool would allocate pool-wide on one branch and per site on another. Overridden by decision 7.

## R5. How the division of a record is read

**Decision**: Not stored. Derived in Cypher from the holding object of the tracked attribute: for each element, the peer id of the relationship (matched by the relationship identifier on the `Relationship` vertex) or the value of the attribute as stored, read on the branch of the request with the normal branch filter (`Branch.get_query_filter_path`, the same one `NumberPoolGetAllocated` already uses), so that a holding object not changed on the branch reads as on the default branch. A holding object with no peer or no value for an element contributes an empty string. A holding object that exists only on another branch has no division on the request branch and is not counted.

**Rationale**: Decision 7 and PRD FR-013 (the unavailable numbers are worked out in the database): the division filter has to be a Cypher fragment next to `reserved_values_query()` (`backend/infrahub/core/query/resource_manager.py`). Deriving the division keeps the record model untouched (PRD FR-009) and makes a node that moves to another site count under its new site on the branch of the move.

**Known limitation (decision 7)**: `reserved_values_query()` counts a value held on any live branch, but the division of its holding object is read on the request branch. A holding object created on `b2` only is invisible from `b1`: its number is not counted in its division on `b1`, so R1 (on `b2`, site A) and R2 (on `b1`, site A) can both receive 1, and both keep it after the merge. The quickstart asserts this case instead of fixing it; the user documentation and the knowledge entry state it.

**Alternatives considered**:

- Reading the division on the branch that holds the counted value, with the default branch as fallback (earlier version of this research): a value is then counted under a division that depends on where the value lives, not on where the request runs, and the figures of two queries on the same branch can disagree. Replaced by decision 7.
- A union over branches, counting a value in every division its holding object occupies on any branch (Jira IFC-3347, IFC-3329): one value in several divisions, the divisions' figures not summing to the pool's. Replaced by decision 7.
- Storing the division on the `IS_RESERVED` edge at allocation time: cheap to read, wrong as soon as the holding object changes site or the value is read on another branch. Rejected.
- Reading the division in Python per candidate value: one round trip per candidate, memory proportional to the tracked values. Rejected by PRD FR-013.
- Two anchor orders for the Cypher (start from the pool's records, or start from the holding objects of the division): Jira IFC-3349 leaves the choice to measurement. The plan starts from the pool's records, since the free-number fragment already does; the quickstart measurement decides whether the other order is kept.

## R6. When the writer's division is read

**Decision**: After every field of the node is processed. On create, `Node._process_fields` (`backend/infrahub/core/node/__init__.py`) processes relationships before attributes, and `Node._process_fields_attributes` calls `AttributePoolApplier.apply` inside the attribute loop, so an attribute element that comes later in the kind's attribute order is not set yet. The allocation of every pooled attribute, scoped or not, therefore moves to one second pass after the attribute loop; the loop keeps resolving the pool (`AttributePoolApplier.apply` with `allocate=False` normalises `from_pool` to the pool id). On update, `Node.from_graphql` applies each payload key in order, and `BaseAttribute.from_graphql` (`backend/infrahub/core/attribute.py`) calls the applier with `allocate=True` as soon as it meets `from_pool`, and not at all when `process_pools` is false. It changes to the create order: the applier with `allocate=False` inside the key loop for each attribute whose payload carries `from_pool`, then, when `process_pools` is true, the applier with `allocate=True` for those attributes once every key is applied. This also gives the lock-name preview of an update a resolved pool, which it does not have today (a pool named by name is locked under its name).

**Rationale**: Spec FR-011. Whether a pool is scoped is only known once the pool node is read, so a deferral limited to scoped pools would mean two orders in one method. One order keeps one code path, and the existing number-pool suites prove the unscoped behaviour is unchanged.

The lock names of the mutation are computed from a preview node before the node is saved: `backend/infrahub/core/node/create.py::create_node` runs `Node.new(process_pools=False)` and `backend/infrahub/graphql/mutations/main.py::InfrahubMutation._call_mutate_update` runs `lock_utils.apply_payload_for_lock_names`; both then call the synchronous `lock_utils.get_lock_names_on_object_mutation`, which has no database access. The division key is therefore computed in the asynchronous step that resolves the pool with `allocate=False` (on create today, on update once the previous paragraph lands): when the resolved pool carries a scope, the step reads the writer's division from the preview node as the allocation will read it (an attribute value from the node, a peer the payload, a template or a profile set from the relationship manager, a peer the payload did not set with one relationship read, since the preview node leaves its stored peers unread) and stores the key beside the pool id on the attribute (`from_pool = {"id": ..., "division": ...}`). The synchronous function then builds the per-division name without a read.

**Alternatives considered**:

- Reading the division from the raw input dictionary: misses values the node already holds on an update, and bypasses the relationship manager that resolves a peer given by hfid. Rejected.
- Dropping the mutation-level pool lock on a scoped pool and relying on the lock of `CoreNumberPool.get_resource` alone (Jira IFC-3349): on create the record is written at node save, after `get_resource` returns, so two creates in one division could receive the same number between the allocation and the save. Rejected.

## R7. The lock key

**Decision**: `<pool id>` for an unscoped pool, `<pool id>.<division key>` for a scoped one, where the division key is a stable hash of the JSON form of the division tuple. Used by `CoreNumberPool.get_resource` (`backend/infrahub/core/node/resource_manager/number_pool.py`, today `lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE)`) and by the mutation-level lock names of `lock_utils.get_lock_names_on_object_mutation` (today `resource_pool.<pool id>`).

**Rationale**: PRD ("The allocator") and Jira IFC-3349: one scoped pool must not serialise every division that a pool per scope used to run in parallel. A hash keeps the lock name short whatever the values hold.

**Alternatives considered**:

- Keeping one lock per pool: correct but serialises all divisions. Rejected.

## R8. How a breaking schema change is refused

**Decision**: A constraint checker, `backend/infrahub/core/validators/pool/scope.py::NumberPoolScopeChecker`, built like the other checkers of `backend/infrahub/core/validators/` and added to the list of `backend/infrahub/dependencies/builder/constraint/schema/aggregated.py`. It supports the constraint names `attribute.optional.update`, `relationship.optional.update`, `relationship.cardinality.update`, `attribute.unique.update`, `node.attribute.remove`, `node.relationship.remove`, `attribute.name.update`, `relationship.name.update` and `attribute.parameters.allocation_scope.update`. It loads the scoped pools of the kind (and of the generics the kind inherits from) in one query, indexes them by element id, and returns one violation per dependent pool when the change makes a scoped element optional, changes a relationship's cardinality, removes an element or sets `unique: true` on a tracked attribute. For the two rename names and the parameter name it applies decision 9 (R9). It runs on every branch, through the schema load and schema check endpoints.

**Rationale**: `AggregatedConstraintChecker.run_constraints` (`backend/infrahub/core/validators/aggregated_checker.py`) runs every registered checker whose `supports` accepts the request, so a second checker under a name that already has one (`attribute.optional.update` maps to `AttributeOptionalChecker`) needs no composite and no change to the map's shape. `CONSTRAINT_VALIDATOR_MAP` (`backend/infrahub/core/validators/__init__.py`) only has to carry the new names so that `SchemaUpdateValidationResult.validate_constraints` (`backend/infrahub/core/models.py`) accepts them: `node.attribute.remove`, `node.relationship.remove` and `attribute.name.update` are migrations, and `SchemaUpdateValidationResult.add_validator_for_migration` turns a migration into a constraint once its name is in the map; `relationship.name.update` yields neither a migration nor a constraint today because the relationship's `name` carries `UpdateSupport.ALLOWED` in `backend/infrahub/core/schema/definitions/internal.py`, so that field moves to `UpdateSupport.VALIDATE_CONSTRAINT` and `backend/infrahub/core/schema/generated/relationship_schema.py` is regenerated. The checkers run in the `SCHEMA_VALIDATE_MIGRATION` workflow for both endpoints, on every branch, which is what spec FR-028 asks.

**Alternatives considered**:

- A dedicated step in `backend/infrahub/api/schema.py` after the diff and before `_validate_migrations` (earlier version of this research): a second validation path beside the one the schema load already runs, duplicated between the load and the check endpoints. Rejected.
- Refusing only on the default branch: the refusal would then wait for the merge. Rejected (decision 1 makes every element apply on every branch).

## R9. Declaring the scope in the schema

**Decision**: `NumberPoolParameters.allocation_scope: list[str] | None` (`backend/infrahub/core/schema/attribute_parameters.py`) keeps its type and its description, and its update marker moves from `UpdateSupport.NOT_SUPPORTED` to `UpdateSupport.VALIDATE_CONSTRAINT`, which makes a change of the declaration raise the constraint `attribute.parameters.allocation_scope.update` (the same mechanism `ranges` uses with `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_RANGES_UPDATE`). `SchemaBranch._validate_number_pool_parameters` (`backend/infrahub/core/schema/schema_branch.py`) applies the rules of R3 to the declaration against the candidate schema: for an attribute whose pool does not exist yet (`number_pool_id` unset) every name must resolve; for an attribute whose pool exists (`number_pool_id` set by the synchronizer) a name that resolves to nothing is left to the checker of R8, which has the stored scope and can name a rename. The checker, for `attribute.parameters.allocation_scope.update`, `attribute.name.update` and `relationship.name.update` on a kind that declares a scope, resolves each declared name to an element id on the candidate schema and compares the list of ids with the stored scope of the schema-created pool: same ids in the same order is accepted (the synchronizer of R2 then rewrites the names); a name that resolves to nothing while the stored scope holds an id whose element now carries another name is refused with "`site` was renamed to `location`, update `allocation_scope`"; any other difference, a cleared declaration included, is refused with "the scope cannot change after the pool is created". `SchemaNumberPoolUpserter.upsert_number_pool` (`backend/infrahub/pools/schema_number_pool_upserter.py`) creates the pool with the resolved scope; `SchemaNumberPoolSynchronizer._update_pool_from_schema` leaves the scope untouched.

**Rationale**: PRD FR-043 asks for the declaration; decision 2 forbids changing it; decision 9 allows the one change that is not a change (the new name of a renamed element). With `NOT_SUPPORTED`, `SchemaUpdateValidationResult._process_field` refuses every change of the list before the ids can be compared, so the rename case of decision 9 could not pass. The comparison by id needs the stored scope, so it runs where the database is available: in the checker of R8, which also sees the candidate schema and the previous schema (`registry.schema.get_schema_branch(name=branch)`), and which the rename constraints trigger even when the declaration itself did not change. Names are the only form a schema author can write, since ids are assigned at load.

**Alternatives considered**:

- Keeping `NOT_SUPPORTED` and asking the author to remove the entry before a rename (Jira IFC-3352): overridden by decisions 6 and 9.
- A list of ids in the schema: unwritable by hand. Rejected.
- Applying a changed declaration to the pool (PRD FR-043 "may be changed on a later schema load"): overridden by decision 2.

## R10. Which divisions the list returns

**Decision**: Only the divisions that hold at least one tracked value, ordered by utilization descending then by display label, as PR #10932 states and decision 8 confirms.

**Rationale**: Decision 8. Listing every division that has nodes would need a scan of the holding object's kind that the pool does not otherwise perform, and the PRD forbids a pool from inspecting its attribute (FR-011).

**Alternatives considered**:

- Every division that has nodes (one reading of PRD FR-020): a scan of the kind per query. Rejected by decision 8.

## R11. The changes to the contract of PR #10932

**Decision**: `allocation_scope` becomes `[NumberPoolScopeElement!]!` with `id: String!` and `name: String!` in `NumberPoolUtilization` and `NumberPoolDivisions`. `NumberPoolDivisionEntry` gains `id: String!` and keeps `path` (the element name). `NumberPoolDivisionEntryInput` keeps `path` and `value`. The descriptions and the refusal messages drop "in force on the request's branch" and name the branch only in the refusal of FR-016. Everything else is unchanged. PR #10932 is rebased onto `feature-number-pools-1.12` and its fixed dataset and tests are updated to this contract before the resolvers read the database, so that the frontend team builds on the final shape.

**Rationale**: Decision 5 allows only the change of decision 4 unless a reason is documented. Adding `id` to the division entry is the reason-documented addition: the entry describes one scope element, and the frontend needs the id to match it with the pool's scope. The input keeps `path` by name because the frontend builds the filter from the entries it displays and because a name is readable in a hand-written query; the name is unique within the kind and kept current by R2. The wording change follows decisions 1 and 7, which leave no partial scope per branch.

## R12. Test fixtures

**Decision**: Reuse the scoped-pool test schema that PR #10932 adds to `backend/tests/helpers/number_pool.py` (`SCOPED_SITE`, `SCOPED_DEVICE`, `SCOPED_POOL_SCHEMA`), extended with a required `Text` attribute, an optional relationship, a many relationship and a `List` attribute, so that one-element, two-element and `List` scopes are tested with one schema. Reuse `backend/tests/helpers/schema/device.py` (`INTERFACE` with a required cardinality-one `device` relationship) where it fits, and `backend/tests/helpers/schema/ticket.py` (`TICKET`, used by the existing scope test) for refusals that need no relationship. The component conftest of `backend/tests/component/core/resource_manager/` already builds pools and holding objects (`serial_pool`, `pooled_holder`) and is extended with a scoped pool fixture.

**Rationale**: Constitution IV: reuse fixtures, add a schema only when no existing one suffices. No existing fixture carries a pooled `Number` attribute next to a required relationship; the schema of PR #10932 is the one the mock task lands first.
