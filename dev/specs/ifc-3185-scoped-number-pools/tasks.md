# Tasks: Scoped number pools — one pool serves every scope

**Input**: Design documents from `dev/specs/ifc-3185-scoped-number-pools/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/),
[critiques/critique-20261002.md](./critiques/critique-20261002.md)

**Tests**: required. Constitution IV and the spec's Testing Decisions mandate them, and every branch
case is written with two branches because a single-branch test cannot tell a union from an
allocating-branch read.

**Organization**: phases follow the plan's change sets so the delivery order is explicit:
**A** schema → **B** frozen GraphQL contract (unblocks frontend and SDK) → **C** seams →
**D1–D4** internals in parallel → **E** close. Each change set maps to the user story it delivers.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — can run in parallel (different files, no dependency on another incomplete task)
- **[Story]** — US1 (contract), US2 (scoped allocation), US3 (per-division utilization), US4
  (schema-declared scope), US5 (refusals), US6 (branch seam), US7 (consolidation, deferred), US8
  (measurement)
- Paths are exact. Code citations are `module::Symbol`, never line numbers.
- Nothing is committed by this run; the user commits when ready.

---

## Phase 1: Setup

**Purpose**: ground truth and the test fixture every later phase shares.

- [X] T001 Read `dev/knowledge/backend/database-schema.md` (edge activity, the Resource Pool
      Reservations section, the retention predicate) and `dev/knowledge/backend/query-pattern.md`
      (branch-aware edge resolution, result dataclasses, "keep Cypher readable inline") before
      touching any query. Read `dev/guidelines/backend/component-design.md` before adding a class.
- [X] T002 Read `backend/infrahub/core/query/resource_manager.py::reserved_values_query` and its two
      UNION legs in full, and `backend/infrahub/core/query/relationship.py::RelationshipGetPeerQuery`
      for how arrows are rendered from `direction`; D3's hop copies both.
- [ ] T003 [P] Add a scoped-pool test schema to `backend/tests/helpers/number_pool.py`: a kind with
      a **non-unique** `Number` attribute to pool, a required cardinality-one relationship (`site`
      → a site kind), a required scalar attribute (`role`, Dropdown), an optional attribute, a many
      relationship and a self-referencing cardinality-one relationship (for the direction case).
      Do not reuse `tests/helpers/schema/snow.py::SNOW_TASK`: its pooled attribute is `unique`, and
      the global taken-values scan masks scoped behaviour. Add a `scoped_pool_schema` fixture and a
      helper that creates N sites and M objects per site.
      Deferred by the user: nothing in change set A allocates, so the schema, fixture and helper
      are added by the first phase that uses them (D1).
- [X] T004 [P] Create `backend/tests/unit/pools/__init__.py` if absent and
      `backend/tests/component/core/constraint_validators/__init__.py` if absent, so the new test
      modules are collected.

---

## Phase 2: Foundational — change set A, the schema (blocks every story)

**Purpose**: the attribute and the parameters field every generated type derives from.

**⚠️ CRITICAL**: no story work starts until A is merged; it is one small PR.

- [X] T005 Add `allocation_scope` (`kind="List"`, `optional=True`, description "Fields of the kind
      that divide the pool's space; allocation returns the lowest free number within the writer's
      division", order after `pool_type`) to
      `backend/infrahub/core/schema/definitions/core/resource_pool.py::core_number_pool`. No branch
      support override: the pool is agnostic.
- [X] T006 [P] Add `allocation_scope: list[str] | None = Field(default=None, …,
      json_schema_extra={"update": UpdateSupport.ALLOWED.value})` to
      `backend/infrahub/core/schema/attribute_parameters.py::NumberPoolParameters` with the same
      description as T005 and "same notation as uniqueness constraints".
- [X] T007 [P] Add the `List` field to the hand-maintained
      `tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields` (the generated SDK,
      OpenAPI and REST models are not introspected from the Pydantic class).
- [ ] T008 Regenerate: `uv run invoke backend.generate`, `uv run invoke
      schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, `uv run invoke
      docs.generate`. Confirm `schema/schema.graphql` carries `allocation_scope: ListAttribute` on
      `CoreNumberPool` and `ListAttributeCreate` / `ListAttributeUpdate` on its three inputs, and
      `schema/openapi.json` carries it on `NumberPoolParametersWrite` / `Read`. Run `uv run pytest
      backend/tests/unit/core/schema/test_write_json_schema.py`.
      Partial: backend protocols, `schema.graphql` and docs regenerated; `openapi.json` still lacks
      the field because `NumberPoolParametersWrite`/`Read` are the SDK models and the `python_sdk`
      submodule regeneration is the separate SDK PR.
- [X] T009 Component test in `backend/tests/component/core/schema/test_attribute_parameters.py`:
      a `NumberPool` attribute declaring `parameters.allocation_scope: ["site"]` loads and the
      parameters round-trip through the schema API; absent and `[]` both read back as unscoped.
- [X] T010 Component test in
      `backend/tests/component/graphql/resource_manager/test_number_pool_mutation.py`: create a
      pool with `allocation_scope: {value: ["site"]}` and read it back; create without it and read
      `null`; update with `{value: null}` clears it. (Validation is not wired yet; this pins the
      round trip and the empty/null equivalence.)

**Checkpoint**: A merges. SDK regeneration PR opened on the SDK repo; pointer bump follows.

---

## Phase 3: US1 — The scope and the per-division figures are on the API (change set B, Priority: P1) 🎯 MVP

**Goal**: publish and freeze the contract so the frontend and SDK can start; the placeholder
`divisions` row is honest for an unscoped pool and transitional for a scoped one (FR-019).

**Independent Test**: export the GraphQL schema, regenerate the frontend types, round-trip a scope
through the three mutations, read `divisions` on an unscoped pool, on a scoped pool and on an IP pool.

### 3a. Tests first

- [ ] T011 [P] [US1] Unit tests in `backend/tests/unit/pools/test_scope.py` for
      `ScopeValidator`: every refusal row of `contracts/graphql-pool-scope.md` (optional attribute,
      optional relationship, many relationship, related-node path, list kind, JSON kind, the pool's
      own attribute, duplicate, unknown entry) names the entry; `role__value` normalises to `role`;
      a valid two-entry scope returns the normalised tuple. Build the `SchemaBranch` from T003's
      schema in memory.
- [ ] T012 [P] [US1] Component tests in
      `backend/tests/component/graphql/resource_manager/test_number_pool_scope_mutation.py`: each
      refused entry through `CoreNumberPoolCreate` and `CoreNumberPoolUpdate`; a valid scope through
      create, update and upsert; an **unchanged** scope re-sent whole through update and upsert is
      accepted; a scope change on a `pool_type: Schema` pool is refused with the existing
      default-branch message.
- [ ] T013 [P] [US1] Component tests in
      `backend/tests/component/graphql/queries/test_resource_pool_divisions.py`: `divisions` on an
      unscoped number pool is one row with `division: []` and figures equal to the headline; on a
      scoped pool (placeholder stage) also one row; on an IP prefix pool `[]`; every existing field
      of `PoolUtilization` unchanged.

### 3b. The validator

- [ ] T014 [US1] Create `backend/infrahub/pools/scope.py` with the frozen dataclasses `ScopeEntry`
      and `DivisionKey` (see `data-model.md` §3) and `ScopeValidator(schema_branch)` with
      `validate(kind, attribute_name, scope) -> tuple[str, ...]`: calls
      `SchemaBranch.validate_schema_path(allowed_path_types=SchemaElementPathType.ATTR |
      SchemaElementPathType.REL_ONE_MANDATORY_NO_ATTR)`, then checks `optional` on the field itself
      (relationships included, because the path validator exempts `ip_namespace`), the attribute
      kind against list and JSON, the pool's own attribute, duplicates; normalises `__value` away;
      raises `ValidationError({"allocation_scope": …})` naming the entry.
- [ ] T015 [US1] Wire it into
      `backend/infrahub/graphql/mutations/resource_manager.py::InfrahubNumberPoolMutation`:
      `mutate_create` validates when a scope is sent; `mutate_update` validates only when the
      normalised submitted scope differs from the stored one, and refuses any change on a
      `pool_type == Schema` pool with the existing default-branch message. The schema branch is
      `registry.schema.get_schema_branch(name=graphql_context.branch.name)`.

### 3c. The `divisions` field with the placeholder

- [ ] T016 [US1] Add `PoolDivisionEntry` and `PoolDivisionUtilization` object types and
      `divisions = Field(List(NonNull(PoolDivisionUtilization)), required=True)` to
      `backend/infrahub/graphql/queries/resource_manager.py::PoolUtilization`, exactly as
      `contracts/graphql-pool-utilization.md` defines them.
- [ ] T017 [US1] In `resolve_number_pool_utilization`, return `divisions` as one row with
      `division: []` and the headline figures (the FR-019 placeholder); in the IP branch of
      `PoolUtilization.resolve`, set `response["divisions"] = []`.
- [ ] T018 [US1] Write the schema-declared scope onto the pool:
      `backend/infrahub/pools/schema_number_pool_upserter.py::SchemaNumberPoolUpserter.upsert_number_pool`
      sets `allocation_scope` from the parameters at creation;
      `backend/infrahub/pools/schema_number_pool_synchronizer.py::SchemaNumberPoolSynchronizer._update_pool_from_schema`
      copies it from the default-branch schema when it differs, as it does the bounds. Component
      test in `backend/tests/component/pools/test_schema_number_pool_upserter.py`: the created pool
      reads back the declared scope.

### 3d. Freeze

- [ ] T019 [US1] Regenerate (`uv run invoke backend.generate schema.generate-graphqlschema
      schema.generate-jsonschema docs.generate`; `cd frontend/app && pnpm codegen`). Diff
      `schema/schema.graphql` against the two GraphQL contracts and confirm no existing field moved.
      Run `uv run invoke docs.validate`.
- [ ] T020 [US1] Add a snapshot test in
      `backend/tests/unit/graphql/test_pool_utilization_contract.py` pinning the SDL of
      `PoolUtilization`, `PoolDivisionUtilization`, `PoolDivisionEntry` and the three
      `CoreNumberPool` inputs' `allocation_scope` field, so a later phase cannot rename, retype or
      remove what this phase published (FR-018).

**Checkpoint**: B merges. Frontend and SDK start from the exported schemas. Everything below changes
no published field.

---

## Phase 4: Change set C — the seams (serves US2 and US3)

**Purpose**: the division resolver and the two entry points the internals plug into, so D1 and D2
can be built concurrently.

- [ ] T021 [P] [US2] Unit tests in `backend/tests/unit/pools/test_scope.py` for
      `DivisionResolver.entries_in_force`: an entry the branch's schema does not define is dropped;
      all unknown → empty tuple; order preserved; relationship entries carry the relationship
      identifier.
- [ ] T022 [P] [US2] Component tests in
      `backend/tests/component/core/resource_manager/test_division_resolver.py` for
      `DivisionResolver.division_of`: relationship entry (peer set by id, by object, by
      human-friendly id), attribute entry, enum attribute unwrapped, two entries in scope order.
- [ ] T023 [US2] Add `DivisionResolver` to `backend/infrahub/pools/scope.py`:
      `entries_in_force(scope, schema_branch, kind)` (pure) and
      `async division_of(db, node, entries) -> DivisionKey` (peer id through
      `RelationshipManager.get_peer_id`, attribute `.value`, enum unwrapped, `None` kept as `None`).
- [ ] T024 [US2] Thread `division: DivisionKey | None = None` through
      `backend/infrahub/core/node/resource_manager/number_pool.py::CoreNumberPool.get_resource`,
      `get_next`, `get_free` and `get_used`, down to `NumberPoolGetFree` / `NumberPoolGetUsed`
      constructors. The queries ignore it in this phase; the unscoped text is unchanged.
- [ ] T025 [US2] In `backend/infrahub/core/node/__init__.py::Node.handle_pool`, resolve the entries
      against `registry.schema.get_schema_branch(name=self._branch.name)` from
      `number_pool.allocation_scope.value`, compute the division from `self`, and pass it to
      `get_resource`. Keep every existing refusal and message.
- [ ] T026 [US2] Defer pool handling on update in `Node.from_graphql`: apply every attribute with
      `process_pools=False`, collect the attributes whose payload carried `from_pool`, then call
      `handle_pool` for each after the loop. `BaseAttribute.from_graphql` keeps assigning
      `from_pool` inline (the mutation lock names are read from it). Assert `Node.from_graphql` still
      has exactly its two callers.
- [ ] T027 [US2] Defer pool handling on template create: in
      `backend/infrahub/templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship`,
      record the pool id and mark the attribute pending in `TemplatePoolFields.pending` instead of
      allocating through `pools/default_allocator.py::DefaultPoolAllocator`; in
      `Node._process_fields_attributes`, run `handle_pool` for pending attributes after the
      relationships are applied. Remove `DefaultPoolAllocator.allocate_for_attribute` if it has no
      other caller; otherwise leave it and note the caller.
- [ ] T028 [US2] Pass the division from the two remaining allocation callers:
      `backend/infrahub/core/node/create.py` (template allocation after `obj.new()`) and
      `backend/infrahub/core/migrations/schema/node_attribute_add.py` (the backfill: load the scoped
      fields in the same query that loads `{"id", attr}` so there is no per-node round trip).
- [ ] T029 [US2] Functional tests in `backend/tests/functional/pools/test_numberpool_lifecycle.py`
      (extend): a scoped field changed and `from_pool` sent in one update allocates after the
      relationship is applied and the pool lock `resource_pool.<id>` is taken; a template-created
      object allocates after its relationships exist. These pass with an unscoped pool in this phase
      and gain scoped assertions in Phase 5.
- [ ] T030 [US3] Reduce `backend/infrahub/pools/number.py::NumberUtilizationGetter` to a seam: it
      loads rows and hands them to `DivisionReporter`; add
      `backend/infrahub/pools/division_report.py` with `DivisionFigures`, `DivisionReport`,
      `DivisionReporter.report(rows, divisions, effective_size, entries)` and
      `fullest_within(start, end)`. With no entries it returns one division with an empty key and
      today's figures. `utilization`, `utilization_default_branch`, `utilization_branches` on the
      getter keep their values for an unscoped pool.
- [ ] T031 [P] [US3] Unit tests in `backend/tests/unit/pools/test_division_report.py`: fullest
      selection; a division with objects and no records reports 0; branch split per division;
      unscoped single division equals the whole; `fullest_within` picks a different division than
      the headline when another range's holder is fuller (spec User Story 3, scenario 3).
- [ ] T032 [US3] Regression: run `uv run pytest backend/tests/component/core/resource_manager/
      backend/tests/component/graphql/resource_manager/ backend/tests/component/graphql/queries/
      backend/tests/functional/pools/` and confirm identical figures (FR-005, SC-003).

**Checkpoint**: C merges. D1, D2, D3 and D4 proceed in parallel.

---

## Phase 5: US2 — One pool, every site (change set D1, Priority: P1)

**Goal**: allocation returns the lowest free number within the writer's division, as a union over
live branches, with the unscoped query unchanged.

**Independent Test**: the scoped pool fixture; devices in several sites through the ordinary
allocation path, on one branch and on two.

### 5a. Tests first

- [ ] T033 [P] [US2] Snapshot test in
      `backend/tests/component/core/resource_manager/test_number_pool_query.py`: the text
      `reserved_values_query` renders with `division=None, with_branch=False` is byte-for-byte
      today's (capture it before T036).
- [ ] T034 [P] [US2] Component tests in
      `backend/tests/component/core/resource_manager/test_number_pool_scoped_query.py`
      (`NumberPoolGetFree` / `NumberPoolGetUsed` with a division): one relationship entry; one
      attribute entry; two entries; the FR-001 two-branch case (D1 holds 5 in A on the default
      branch, moved to C on `b1`: default branch reads 6 free in A, 6 in C, 5 in D; delete `b1` → 5
      free in C with no write); the fork-window case on the hop (D1 moved from A to C **on the
      default branch** after `b0` forked: `b0` still reads 5 as taken in A); a self-referencing
      relationship entry collects only the forward peers; every entry unknown → the unscoped
      result.
- [ ] T035 [P] [US2] Functional tests in
      `backend/tests/functional/pools/test_numberpool_scoped_allocation.py` through GraphQL: the
      User Story 2 scenarios 1, 2, 3, 7, 8 and 9 of `spec.md`; fifty concurrent creates in site A
      yield fifty distinct numbers and fifty in A plus fifty in B yield 1–50 twice (FR-004); the
      Phase 4 deferral tests gain their scoped assertions.

### 5b. The scoped fragment

- [ ] T036 [US2] Extend `backend/infrahub/core/query/resource_manager.py::reserved_values_query`
      with `division: DivisionKey | None = None` and `with_branch: bool = False`. Lift the two-leg
      visibility predicate into a named module constant (open now on a non-deleting branch; or
      closed on the default branch, still inside a live fork window, with no hiding edge on the same
      vertex) and use it for the value read and for each entry hop. With a division: match
      `(n:Node)-[:HAS_ATTRIBUTE]->(attr)`, one `CALL` per entry collecting the peer uuids
      (relationship, arrows from `direction`, `Relationship {name: $identifier}`) or the values
      (attribute), then `WHERE $entry_i_value IN entry_i_values` for every entry, before the value
      read. Bind every name and value as a parameter. With `with_branch`, project `branch` from both
      legs and end `WITH DISTINCT res, value, branch`.
- [ ] T037 [US2] Render the division-side anchor as a second shape behind the same parameter (match
      the writer's peer or value vertex, walk to the objects holding it, then to their reserved
      attributes for this pool), selected by a module-level switch, so T063 can profile both. Both
      must pass T034.
- [ ] T038 [US2] Pass the division from `get_free` / `get_used` into the fragment; `get_next` keeps
      its structure (P1's range walk lands around it, not inside the fragment).
- [ ] T039 [US2] Run T033–T035 and the full regression set from T032.

**Checkpoint**: User Story 2 is functional; scoped pools allocate per division.

---

## Phase 6: US3 — Which site is about to run out (change set D2, Priority: P2)

**Goal**: real per-division figures on the utilization query: headline from the fullest division,
every division listed including empty ones, per-range rows from the fullest division within the
range.

**Independent Test**: uneven occupancy across sites on the scoped fixture; compare the headline, the
per-division rows and the per-range rows against the records.

- [ ] T040 [P] [US3] Component tests in
      `backend/tests/component/core/resource_manager/test_number_pool_divisions_query.py` for
      `NumberPoolDivisions`: distinct tuples over objects on the default branch and on `b1`; an
      object with no record still yields its division; a deleted object's division disappears; a
      `DELETING` branch's objects are excluded; two entries.
- [ ] T041 [P] [US3] Extend `backend/tests/component/graphql/queries/test_resource_pool_divisions.py`:
      the spec's User Story 3 scenario 1 (A 50 records, B two objects no records, C no objects →
      headline 50 %, A 50/100, B 0/100, no row for C); scenario 2 (branch split over the fullest
      division); scenario 3 (per-range rows: 1–50 reports A's 80 %, 51–100 reports B's 60 %, headline
      A's 40 of 100); scenario 4 (a division keyed by a site that exists only on `b1`, read from the
      default branch, is listed with `display_label` falling back to the id and `peer_kind` null);
      `InfrahubResourcePoolAllocated` count, offset and limit unchanged across the fragment move;
      `divisions` on an IP pool still `[]`.
- [ ] T042 [US3] Add `NumberPoolDivisions` to `backend/infrahub/core/query/resource_manager.py`:
      over `(n:Node:<kind>)-[:IS_PART_OF]->(:Root)` with the visibility constant on the
      `IS_PART_OF` edge and one `CALL` per entry (same shape as T036), return the distinct tuple of
      entry values with `count(DISTINCT n.uuid)`; frozen dataclass result; `ORDER BY` on the tuple.
- [ ] T043 [US3] Move `NumberPoolGetAllocated` onto the shared fragment with `with_branch=True`
      and, when scoped, the per-entry value lists per row; keep `n.uuid`, `res.identifier`, `value`,
      `branch` in the result dataclass because `resolve_number_pool_allocation` shares the class.
- [ ] T044 [US3] Complete `NumberUtilizationGetter.load_data`: run both queries, resolve the entries
      in force on the reading branch, hand everything to `DivisionReporter`; expose
      `report.divisions` and `report.fullest`.
- [ ] T045 [US3] Replace the placeholder in `resolve_number_pool_utilization`: headline and branch
      split from `fullest`; `_range_edge` from `fullest_within(start, end)`; `divisions` from the
      report, ordered by utilization descending then entry values; peer display labels and kinds from
      one `NodeManager.get_many(..., branch_agnostic=True)` over the distinct peer ids, falling back
      to the id; attribute values as text; a missing value as `""`.
- [ ] T046 [US3] Run T040, T041, T020 (the contract snapshot must not change) and the regression set.

**Checkpoint**: User Stories 2 and 3 work; the FR-019 placeholder is gone.

---

## Phase 7: US4 — Scope declared in the schema (change set D3, Priority: P2)

**Goal**: a number-pool attribute's `allocation_scope` is validated on load, reconciled from the
default branch, and the attribute-add size check is per division.

**Independent Test**: load the scoped schema, allocate from two sites, change the declaration on the
default branch, reload, attempt a direct edit on the pool.

- [ ] T047 [P] [US4] Component tests in `backend/tests/component/pools/test_schema_number_pool_scope.py`:
      `vlan_id` with ranges 100–200 and scope `["site"]` → two sites both receive 100; clearing the
      scope on the default branch and reloading → next allocation 102; a scope declared on `b1` only
      does not change the pool until merge; a direct `CoreNumberPoolUpdate` of the scope is refused
      with the default-branch message; a declaration naming an optional field, a many relationship,
      a related-node path or an unknown field is refused at load naming the entry.
- [ ] T048 [P] [US4] Component test in
      `backend/tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py`
      (extend): adding a scoped `NumberPool` attribute of size 10 to a kind with 25 objects spread
      over three sites (max 9 per site) is accepted; with 11 in one site it is refused with the
      division count in the message.
- [ ] T049 [US4] Call `ScopeValidator` from
      `backend/infrahub/core/schema/schema_branch.py::SchemaBranch._validate_number_pool_parameters`
      with `self` as the schema branch when `parameters.allocation_scope` is set.
- [ ] T050 [US4] In `backend/infrahub/core/validators/node/attribute.py::NodeAttributeAddChecker`,
      when the added `NumberPool` attribute declares a scope, compare the pool size against the
      largest per-division object count from `NumberPoolDivisions` (entries resolved with
      `DivisionResolver.entries_in_force` against `request.node_schema`'s branch).
- [ ] T051 [US4] Run T047, T048 and `backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py`.

**Checkpoint**: schema-created pools carry and honour a declared scope.

---

## Phase 8: US5 — A scope that has no answer is refused (change set D4, Priority: P2)

**Goal**: a schema load that would make a scoped field optional, absent or cardinality many is
refused naming the pool.

**Independent Test**: load schemas that invalidate an entry a pool depends on through the component
checker and through the schema-load API.

- [ ] T052 [P] [US5] Unit test in `backend/tests/unit/core/validators/test_scoped_pool_dependency.py`:
      `ScopedPoolDependencyChecker.check` with a `node_schema` that no longer holds the field reads
      kind and field from `request.schema_path` and does not raise on the lookup itself.
- [ ] T053 [P] [US5] Component tests in
      `backend/tests/component/core/constraint_validators/test_scoped_pool_dependency.py`: a pool
      scoped by `site`; three loads (optional, removed, cardinality many) → three refusals naming the
      pool; a pool scoped by `["site", "pod"]` from `b1` and a default-branch load that never had
      `pod` → accepted; `node_attribute` itself removed → the existing attribute-removal path still
      governs (no double refusal).
- [ ] T054 [P] [US5] Component tests in `backend/tests/component/pools/test_pools_referencing_field.py`
      for `PoolsReferencingField.get`: pools on the kind, on a generic the kind inherits from, by
      scope entry and by `node_attribute`; a pool on an unrelated kind is not returned.
- [ ] T055 [US5] Create `backend/infrahub/pools/referencing.py::PoolsReferencingField` (repository,
      `db` in the constructor, `get(kind, field_name, branch) -> list[CoreNumberPool]`) using
      `NodeManager.query(CoreNumberPool, filters={"node__values": [kind, *generics]})` and a Python
      filter on `allocation_scope` and `node_attribute`.
- [ ] T056 [US5] Create `backend/infrahub/core/validators/pool/__init__.py` and
      `backend/infrahub/core/validators/pool/scope.py::ScopedPoolDependencyChecker` (name
      `pool.scope.dependency`; `supports` for the five constraint names; `check` raises
      `ValueError` naming each pool, skipping entries absent from the branch's schema). Register it
      in `backend/infrahub/core/validators/__init__.py::CONSTRAINT_VALIDATOR_MAP` for
      `attribute.optional.update`, `relationship.optional.update`,
      `relationship.cardinality.update`, `node.attribute.remove`, `node.relationship.remove`. Do not
      touch `core/models.py`: `add_validator_for_migration` already turns the removal migrations
      into constraints. The map holds one checker class per name and
      `core/validators/determiner.py` instantiates it by name, so for the three update names that
      already map to a checker add a `CompositeConstraintChecker` in
      `backend/infrahub/core/validators/composite.py` that takes the checker classes in its
      constructor, instantiates each with the same `db` and `branch`, `supports` when any does, and
      concatenates their `check` results (a raised `ValueError` propagates as it does today); map the
      two removal names, unmapped today, to the new checker directly. Unit-test the composite in
      `backend/tests/unit/core/validators/test_composite_checker.py`.
- [ ] T057 [US5] Integration-docker test
      `backend/tests/integration_docker/test_number_pool_scope_schema_load.py` (shard marker as the
      other tests in that folder): the removal refusal through the schema-load API names the pool.

**Checkpoint**: every refusal of User Story 5 ships and names what the user must change.

---

## Phase 9: US6 — Schema and pool changes travel together through branches (Priority: P3)

**Goal**: the branch seam end to end: unknown entries dropped per read, validation on the mutation
branch, the full scope after merge.

**Independent Test**: every scenario uses two branches.

- [ ] T058 [US6] Functional tests in `backend/tests/functional/pools/test_numberpool_scoped_branch.py`
      (`workflow_awaited_only` for the merge): `pod` declared required on Device in `b1` only;
      `["site", "pod"]` saves on `b1` and is refused on the default branch naming `pod`; the default
      branch allocates per site and `b1` per site and pod; the default branch's utilization groups
      by site only and `divisions` rows carry one entry there and two on `b1`; after `b1` merges
      every branch allocates per the full scope; an object deleted on `b1` but live on the default
      branch still counts in its division on both; the unchanged scope re-sent whole from the
      default branch is accepted.
- [ ] T059 [US6] Extend `backend/tests/component/core/resource_manager/test_number_pool_branch_liveness.py`
      with the two lifecycle rows the spec adds: the scoped-field move on a branch (record counts in
      both divisions until merge or delete) and schema divergence (the transient double-1 under the
      coarser reading is accepted and documented in the test name by behaviour, not by issue).

**Checkpoint**: the branch cases in the spec's edge list each have a two-branch test.

---

## Phase 10: US7 — Replace a pool per site with one scoped pool (Priority: P3, deferred)

**Goal**: none in this slice. Gated on P2 attach, which is not built.

- [ ] T060 [US7] When attach lands on this branch, add the consolidation scenario to
      `backend/tests/functional/pools/test_numberpool_scoped_allocation.py`: P_A and P_B each handed
      out 1–10; scope P_A by site, attach the ten site-B objects → A 10/100, B 10/100, next in B is
      11, P_B deletable. Until then this task is blocked and is not part of the slice's definition of
      done.

---

## Phase 11: US8 — The cost of a scoped pool is measured before it ships (change set E, Priority: P3)

**Goal**: SC-005 and SC-006 figures recorded; the anchor order chosen on numbers.

- [ ] T061 [P] [US8] Query benchmark `backend/tests/query_benchmark/test_number_pool_scoped_allocation.py`:
      a 4094-number pool with a three-entry scope (two relationships, one attribute), five live
      branches, fully occupied; one allocation; record latency and the `EXPLAIN`/`PROFILE` of the
      scoped free query (SC-006).
- [ ] T062 [P] [US8] Timed functional scenario
      `backend/tests/functional/pools/test_numberpool_scoped_throughput.py` marked `measurement`
      (excluded from the default run in `backend/pytest.ini` or the folder's `conftest.py`): one
      scoped pool versus N per-site pools serving the same objects under concurrent allocation;
      record throughput for both (SC-005).
- [ ] T063 [US8] Run T061 against both anchor orders from T037 at the SC-006 shape and at a hub
      shape (one site holding most objects); keep the better one, delete the other and its switch.
- [ ] T064 [US8] Write `dev/specs/ifc-3185-scoped-number-pools/measurements.md`: both figures, the
      plans, the anchor order kept, and the occupancy at which a stored division key would be
      needed. State whether SC-005 argues for a per-division lock; take no lock change in this
      slice.

---

## Phase 12: Polish & cross-cutting

- [ ] T065 [P] Changelog fragments in `changelog/` (use the `creating-changelog-entries` skill):
      scoped allocation and per-division utilization (feature); `parameters.allocation_scope`
      (feature); `divisions` on the utilization query (additive read-shape change); the pool-save
      refusals (new refusal); the schema-load refusal naming the pool (new refusal); the in-use list
      no longer showing a deleting branch's values (changed behaviour, from the allocated read moving
      onto the shared fragment).
- [ ] T066 [P] User docs: a "Scope a pool" section in `docs/docs/resource-manager/allocate-number.mdx`
      (web and GraphQL tabs, the refusal list, the branch note) and an `allocation_scope` example in
      `docs/docs/schema/number-pool.mdx`; regenerate `docs/docs/snippets/attribute-kind-params.mdx`
      and `docs/docs/reference/schema/attribute.mdx` with `uv run invoke docs.generate`; run
      `uv run invoke docs.lint`.
- [ ] T067 [P] Knowledge: in `dev/knowledge/backend/database-schema.md`, beside the Resource Pool
      Reservations section, describe the division read (entries in force per branch, the per-entry
      union, the shared visibility rule) in a few lines; no spec or ticket references.
- [ ] T068 Run `/pre-ci`; confirm `uv run invoke docs.validate` passes with every generated file
      committed-ready and the SDK submodule pointer plan is recorded (SDK PR first, pointer bump
      after).
- [ ] T069 Run `quickstart.md` scenarios 1 to 6 and the regression guard; record the outcome in the
      PR description, not in the docs.

---

## Dependencies & execution order

```text
Phase 1 (setup) ─┬─> Phase 2 (A: schema) ─┬─> Phase 3 (B: contract, US1)  ──┐
                 │                         ├─> Phase 4 (C: seams) ──┬─> Phase 5 (D1, US2) ─┬─> Phase 9 (US6)
                 │                         │                        └─> Phase 6 (D2, US3) ─┤
                 │                         ├─> Phase 7 (D3, US4) ─────────────────────────┤
                 │                         └─> Phase 8 (D4, US5) ─────────────────────────┤
                 │                                                                         ├─> Phase 11 (E, US8) ─> Phase 12
                 └─────────────────────────────────────────────────────────────────────────┘
Phase 10 (US7): blocked on P2 attach; outside this slice's definition of done.
```

- **Phase 2 blocks everything**: every generated type derives from the attribute and the field.
- **Phase 3 unblocks the frontend and the SDK** and freezes the contract; T020 guards it.
- **Phase 4 is the fan-out point**: once the seams exist, D1 and D2 are different files and can be
  built by two people; D3 and D4 depend only on A and can start as soon as it merges.
- **Phase 6 depends on Phase 3** (the field exists) and **Phase 4** (the reporter), not on Phase 5:
  the allocated read and the enumeration are their own queries.
- **Phase 9** needs D1, D2 and D3 to assert allocation, utilization and the schema-load path on two
  branches.
- **Phase 11** needs D1 and D2; T063 decides between the two anchor orders T037 rendered.

## Parallel opportunities

| After | In parallel |
|---|---|
| Phase 1 | T003, T004 |
| Phase 2 merged | Phase 3 (B), Phase 4 (C), Phase 7 (D3), Phase 8 (D4) |
| Phase 4 merged | Phase 5 (D1) and Phase 6 (D2) |
| Within Phase 5 | T033, T034, T035 before T036 |
| Within Phase 6 | T040, T041 before T042 |
| Within Phase 8 | T052, T053, T054 before T055 |
| Phase 12 | T065, T066, T067 |

## Implementation strategy

1. **MVP = Phase 2 + Phase 3**: the schema and the frozen contract. Frontend and SDK work starts
   here; an unscoped pool already reports its single division.
2. **Capability = Phase 4 + Phase 5**: scoped allocation through the ordinary, template and update
   paths.
3. **Operability = Phase 6, 7, 8**: real per-division figures, schema-declared scope, every refusal.
   Three people can take these three concurrently.
4. **Confidence = Phase 9, 11**: the two-branch suites and the measurements.
5. **Ship = Phase 12**.

## Summary

| Metric | Value |
|---|---|
| Tasks | 69 |
| Setup / foundational (A) | 10 |
| US1 (B, contract) | 10 |
| US2 (C seams + D1) | 16 (T021–T029, T033–T039) |
| US3 (C reporter + D2) | 10 (T030–T032, T040–T046) |
| US4 (D3) | 5 |
| US5 (D4) | 6 |
| US6 | 2 |
| US7 (deferred) | 1 |
| US8 (E) | 4 |
| Polish | 5 |
| Parallel-marked tasks | 24 |
