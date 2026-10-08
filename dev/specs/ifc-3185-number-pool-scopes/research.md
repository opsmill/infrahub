# Research: Number pool allocation scopes

Each entry records a decision, the reason, and the alternatives considered. Sources: the Notion PRD (allocation scopes part), the Jira tickets of IFC-3185, the description of PR #10932, the five decisions of the product owner, and the code of the working tree.

## R1. Where the scope is stored

**Decision**: A `List` attribute `allocation_scope` on `CoreNumberPool`, holding ordered objects `{"id": <schema element id>, "name": <element name>}`.

**Rationale**: The pool is one node; its scope is a short, ordered, immutable list. A `List` attribute keeps the pool self-contained, needs no new kind and no graph migration (an optional attribute added to a core node is applied by the internal schema update at startup), and is read by the generic `CoreNumberPool` GraphQL node query like any other attribute. Storing the name beside the id satisfies decision 4 on every read, including the generic node query, without a schema lookup per read.

**Alternatives considered**:

- One `CoreNumberPoolScopeElement` node per element, like `CoreNumberPoolRange`: more nodes, a migration path and a parent relationship for a list that never changes after creation. Rejected (simplicity).
- Storing ids only and resolving names on every read: the generic node query would show ids only, which contradicts decision 4; and every dedicated query would add a schema lookup. Rejected.
- Storing names only (what the PRD FR-015 reads as): a rename would silently break the scope. Rejected by decision 3.

## R2. How a name stays current after a rename

**Decision**: `SchemaNumberPoolSynchronizer` gains a step that, on each schema update of the default branch, looks every stored element id up in the default schema and rewrites the stored name when it differs. The step covers user-created and schema-created pools.

**Rationale**: The synchronizer already runs after every schema update (`backend/infrahub/schema/tasks.py::schema_updated` calls `backend/infrahub/pools/tasks.py::validate_schema_number_pools`), and already reads the default-branch schema. Schema element ids survive a rename: `backend/infrahub/core/migrations/schema/attribute_name_update.py` finds the previous attribute by id, and `backend/infrahub/core/schema/manager.py` resolves attributes and relationships by id when it updates the schema in the database.

**Alternatives considered**:

- Refusing the rename of a scoped element (Jira IFC-3352): unnecessary once the id is the reference, and it would force the operator to recreate pools. Overridden by decision 3.
- Refreshing names lazily on read: leaves the stored value stale between the rename and the next read. Rejected.

## R3. What a scope element may reference

**Decision**: A required attribute or a required cardinality-one relationship of the pool's kind, declared on that kind (on the generic itself when the pool's kind is a generic), given as the element id or the element name, not a path into a peer, not the pool's own tracked attribute, not twice. A scope is refused on a pool whose tracked attribute is `unique: true`.

**Rationale**: PRD FR-015 gives the required and cardinality rules. Jira IFC-3348 adds the generic rule and the `unique: true` rule (a globally unique number cannot repeat per division). The name resolves within the kind because `SchemaBranch` validates that attribute and relationship names are unique together on one kind. The existing path validation (`SchemaBranch.validate_schema_path` with `SchemaElementPathType.ATTR_NO_PROP | REL_ONE_MANDATORY_NO_ATTR`) gives the same rules for a path written as a string, and the resolver reuses it for name entries.

**Alternatives considered**:

- Allowing a path into a related node (`site__region`): the division of a node would then depend on another node's attribute, which can change without touching the holder; the PRD refuses it. Rejected.
- Allowing attributes of kind `List` or `JSON`: their values are not single scalars; the sources do not ask for them. Not refused explicitly, but the value is stored as its text form, which is what PR #10932 specifies for attribute entries.

## R4. Which schema the scope is resolved against

**Decision**: Always the schema of the default branch. A pool created on a branch, or a schema loaded on a branch, that references an element absent from the default branch is refused.

**Rationale**: Decision 1. It also removes the "scope in force on the request's branch" variability of PR #10932: since the guard (R8) refuses, on every branch, a schema change that breaks a scoped element, a branch schema always defines every element of a scope.

**Alternatives considered**:

- Validation against the branch where the pool is saved (Jira IFC-3348, 2026-10-08) and a scope that applies only on the branches whose schema defines it (Jira IFC-3354): more states to test and a scope that can change meaning per branch. Overridden by decision 1.

## R5. How the division of a record is read

**Decision**: Not stored. Derived in Cypher from the holder node of the tracked attribute: for each element, the peer id of the relationship (matched by the relationship identifier on the `Relationship` vertex) or the value of the attribute as text, read on the branch that holds the counted value, with the default branch as fallback, using the usual edge precedence (`branch_level DESC, from DESC, status ASC`). A holder with no peer or no value for an element contributes an empty string.

**Rationale**: PRD FR-013 requires the unavailable numbers to be worked out in the database, so the division filter has to be a Cypher fragment next to `reserved_values_query()`. Deriving the division keeps the record model untouched (PRD FR-009, "the scope changes how a number is picked, not what the pool records") and makes a node that moves to another site count under its new site on the branch of the move.

**Known limitation**: `reserved_values_query()` also counts a value closed on the default branch when a branch forked while it was open and has not overridden it. The scope values of such a holder are read with the same branch fallback, not through that fork window, so a site change made on the default branch after the fork is reflected in the division of the value the old branch still sees. The quickstart asserts this case instead of fixing it (Jira IFC-3354 keeps two branch limitations asserted, not fixed).

**Alternatives considered**:

- Storing the division on the `IS_RESERVED` edge at allocation time: cheap to read, wrong as soon as the holder changes site or the value is read on another branch. Rejected.
- Reading the division in Python per candidate value: one round trip per candidate, memory proportional to the tracked values. Rejected by PRD FR-013.
- Two anchor orders for the Cypher (start from the pool's records, or start from the holder nodes of the division): Jira IFC-3349 leaves the choice to measurement. The plan starts from the pool's records, since the free-number fragment already does; the quickstart measurement decides whether the other order is kept.

## R6. When the writer's division is read

**Decision**: After every field of the node is processed. `Node._process_fields` processes relationships before attributes, so a relationship element is always available in memory; an attribute element that comes later in the kind's attribute order is not. The allocation of every pooled attribute, scoped or not, therefore runs in one second pass over the pooled attributes after `_process_fields_attributes`, while the pool resolution and the normalisation of `from_pool` stay in the loop. `Node.from_graphql` applies all keys of the update payload first and allocates afterwards.

**Rationale**: Spec FR-011. Whether a pool is scoped is only known once the pool node is read, so a deferral limited to scoped pools would mean two orders in one method. One order keeps one code path, and the existing number-pool suites prove the unscoped behaviour is unchanged.

The lock name of the mutation is computed from a preview node by `lock_utils.get_lock_names_on_object_mutation`, which is synchronous. The division key is therefore computed one step earlier, in `lock_utils.apply_payload_for_lock_names`, which has database access: it resolves the pool of each pooled attribute (`Node.handle_pool` with `allocate_resources=False`) and stores the division key on the attribute beside the pool id when the pool is scoped.

**Alternatives considered**:

- Reading the division from the raw input dictionary: misses values the node already holds on an update, and bypasses the relationship manager that resolves a peer given by hfid. Rejected.

## R7. The lock key

**Decision**: `<pool id>` for an unscoped pool, `<pool id>.<division key>` for a scoped one, where the division key is a stable hash of the JSON form of the division tuple. Used both by `CoreNumberPool.get_resource` and by the mutation-level lock names.

**Rationale**: PRD ("The allocator") and Jira IFC-3349: one scoped pool must not serialise every division that a pool per scope used to run in parallel. A hash keeps the lock name short whatever the values hold.

**Alternatives considered**:

- Keeping one lock per pool: correct but serialises all divisions. Rejected.

## R8. How a breaking schema change is refused

**Decision**: A guard in `backend/infrahub/pools/scope_guard.py`, called from the schema load and schema check endpoints after the schema diff is computed and before migrations are validated. It loads the scoped pools once, indexes element ids to pools, and refuses when the diff makes an element optional, changes a relationship's cardinality, removes an element, or sets `unique: true` on a pool's tracked attribute. The error names every dependent pool and the element. It runs on every branch.

**Rationale**: `CONSTRAINT_VALIDATOR_MAP` in `backend/infrahub/core/validators/__init__.py` maps one checker per constraint name, and the names needed here (`relationship.optional.update`, `relationship.cardinality.update`, `attribute.optional.update`, `attribute.unique.update`) already map to data checkers. Removal of a field is not a constraint but a migration. A dedicated step over the schema diff covers all four cases in one place and reads the pools in one query.

**Alternatives considered**:

- Composing a second checker under the existing constraint names: changes the checker map's shape for one feature. Rejected.
- Refusing only on the default branch: the refusal would then wait for the merge (Jira IFC-3352 wanted the branch load not refused when the entry does not apply there; decision 1 makes every entry apply on every branch). Rejected.

## R9. Declaring the scope in the schema

**Decision**: `NumberPoolParameters.allocation_scope: list[str] | None`, element names, with the update marker `not_supported`. Validation happens in `SchemaBranch._validate_number_pool_parameters` through the resolver, and the upserter creates the pool with the resolved scope.

**Rationale**: PRD FR-043 asks for the declaration; decision 2 forbids changing it. `number_pool_id` already uses `not_supported` on the same model, and `backend/infrahub/core/models.py` refuses a change of such a field when update support is enforced, so immutability costs no new code. Names are the only form a schema author can write, since ids are assigned at load.

**Alternatives considered**:

- A list of ids in the schema: unwritable by hand. Rejected.
- Applying a changed declaration to the pool (PRD FR-043 "may be changed on a later schema load"): overridden by decision 2.

## R10. Which divisions the list returns

**Decision**: Only the divisions that hold at least one tracked value, ordered by utilization descending then by display label, as PR #10932 states.

**Rationale**: PR #10932 is the contract communicated to the frontend team. Listing every division that has nodes would need a scan of the holder kind that the pool does not otherwise perform, and the PRD forbids a pool from inspecting its attribute (FR-011).

**Alternatives considered**:

- Every division that has nodes (one reading of PRD FR-020): a scan of the kind per query. Rejected, recorded as an open point settled by judgment in the spec.

## R11. The changes to the contract of PR #10932

**Decision**: `allocation_scope` becomes `[NumberPoolScopeElement!]!` with `id: String!` and `name: String!` in `NumberPoolUtilization` and `NumberPoolDivisions`. `NumberPoolDivisionEntry` gains `id: String!` and keeps `path` (the element name). `NumberPoolDivisionEntryInput` keeps `path` and `value`. Everything else is unchanged.

**Rationale**: Decision 5 allows only the change of decision 4 unless a reason is documented. Adding `id` to the division entry is the reason-documented addition: the entry describes one scope element, and the frontend needs the id to match it with the pool's scope. The input keeps `path` by name because the frontend builds the filter from the entries it displays and because a name is readable in a hand-written query; the name is unique within the kind and kept current by R2.

## R12. Test fixtures

**Decision**: Reuse `backend/tests/helpers/schema/device.py` where it fits (an `Interface` with a required cardinality-one `device` relationship) and add one schema fixture under `backend/tests/helpers/schema/` holding a kind with a `Number` attribute, a required cardinality-one relationship and a required `Text` attribute, so that one-element and two-element scopes are tested with one schema. The component conftest of `backend/tests/component/core/resource_manager/` already builds pools and holders by name and is extended with a scoped pool fixture.

**Rationale**: Constitution IV: reuse fixtures, add a schema only when no existing one suffices. No existing fixture carries a pooled `Number` attribute next to a required relationship.
