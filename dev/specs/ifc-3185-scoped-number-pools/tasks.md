# Tasks: Scoped number pools — one pool serves every scope

**Input**: Design documents from `dev/specs/ifc-3185-scoped-number-pools/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/),
[critiques/critique-20261002.md](./critiques/critique-20261002.md)

**Tests**: required. Constitution IV and the spec's Testing Decisions mandate them, and every branch
case is written with two branches because a single-branch test cannot tell a union from an
allocating-branch read.

**Organization**: phases follow the plan's change sets so the delivery order is explicit:
**A** schema → **B** dedicated GraphQL surface (unblocks frontend and SDK) → **C** seams →
**D1–D4** internals in parallel → **E** mock removal → **F** close. Each change set maps to the
user story it delivers.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — can run in parallel (different files, no dependency on another incomplete task)
- **[Story]** — US1 (contract), US2 (scoped allocation), US3 (division reads), US4
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
      UNION legs in full, `NumberPoolGetAllocated` (shorthand bounds filter, result dataclass), and
      `backend/infrahub/core/query/relationship.py::RelationshipGetPeerQuery` for how arrows are
      rendered from `direction`; D3's hop copies both. Read
      `backend/infrahub/graphql/queries/resource_manager.py` in full: the dedicated surface
      reuses its `NodeNotFoundError` pattern and changes nothing else there but descriptions. Read
      `backend/infrahub/pools/number_pool_repository.py::NumberPoolRepository.get_ranges`,
      `backend/infrahub/pools/number_pool_shorthand.py::NumberPoolShorthandMirror` (why
      `start_range` / `end_range` is null on a pool holding several ranges) and
      `backend/infrahub/graphql/mutations/resource_manager/number_pools/pool.py` (where the scope
      validation of Phase 7 goes).
- [ ] T003 [P] Add a scoped-pool test schema to `backend/tests/helpers/number_pool.py`: a kind with
      a **non-unique** `Number` attribute to pool, a required cardinality-one relationship (`site`
      → a site kind), a required scalar attribute (`role`, Dropdown), an optional attribute, a many
      relationship and a self-referencing cardinality-one relationship (for the direction case).
      Do not reuse `tests/helpers/schema/snow.py::SNOW_TASK`: its pooled attribute is `unique`, and
      the global taken-values scan masks scoped behaviour. Add a `scoped_pool_schema` fixture, a
      helper that creates N sites and M nodes per site, and a helper that creates a pool with two
      ranges (`1 - 50` weighted 10, `51 - 100` unweighted) so the contract examples can be
      reproduced.
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
- [X] T008 Regenerate: `uv run invoke backend.generate`, `uv run invoke
      schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, `uv run invoke
      docs.generate`. Confirm `schema/schema.graphql` carries `allocation_scope: ListAttribute` on
      `CoreNumberPool` and `ListAttributeCreate` / `ListAttributeUpdate` on its three inputs, and
      `schema/openapi.json` carries it on `NumberPoolParametersWrite` / `Read`. Run `uv run pytest
      backend/tests/unit/core/schema/test_write_json_schema.py`.
- [X] T009 Component test in `backend/tests/component/core/schema/test_attribute_parameters.py`:
      a `NumberPool` attribute declaring `parameters.allocation_scope: ["site"]` loads and the
      parameters round-trip through the schema API; absent and `[]` both read back as unscoped.
- [X] T010 Component test in
      `backend/tests/component/graphql/resource_manager/number_pools/test_pool_scope.py` (new,
      using that folder's `helpers.py`): create a pool with `allocation_scope: {value: ["site"]}`
      and read it back; create without it and read `null`; update with `{value: null}` clears it.
      (Validation is not wired yet; this pins the round trip and the empty/null equivalence, User
      Story 1 scenario 1.)

**Checkpoint**: A merges. SDK regeneration PR opened on the SDK repo; pointer bump follows.

---

## Phase 3: US1 — The number-pool GraphQL surface is published and frozen (change set B, Priority: P1) 🎯 MVP

**Goal**: publish and freeze the three dedicated root fields with real pool, range and allocation
data and the mock partition for a scoped pool's divisions
([contract](./contracts/graphql-number-pool-surface.md)); add the description notes to the generic
queries; regenerate; pin the SDL. This phase is one change set the frontend starts from.

**Independent Test**: export the GraphQL schema, regenerate the frontend types, read the three
queries on an unscoped pool, a scoped pool and an IP pool, diff the generic types for description
changes only.

### 3a. Tests first

- [ ] T011 [P] [US1] Unit tests in `backend/tests/unit/pools/test_division_mock.py`: the partition
      is stable for one holder id across calls, uses exactly the three names `mock-1..3`, and builds
      one entry per path in force with `value` and `display_label` equal to the division's name and
      `peer_kind` None; with no path in force it is never consulted (the caller guards).
- [ ] T012 [P] [US1] Component tests in
      `backend/tests/component/graphql/queries/test_number_pool_surface.py` on the unscoped
      two-range pool of T003 (its shorthand `start_range` / `end_range` is null, which today's
      generic queries cannot handle) holding 1 and 51 on the default branch, 7 on `b1` only, 500
      provided on the default branch and held by no range, and 40 provided on the default branch
      while the attribute lists 40 in `excluded_values`: `InfrahubNumberPoolUtilization` returns
      `allocation_scope: []`, `figures` `{size: 99, used: 3, used_default_branch: 2, used_branches: 1}`
      with the three percentages, two ranges ordered by start with id, display label, start, end,
      weight (10 and 0) and figures `{50, 2, 1, 1}` and `{50, 1, 1, 0}`, `out_of_space_count: 2`;
      `InfrahubNumberPoolDivisions` returns one division with `entries: []`, `display_label: ""`
      and the pool's figures; `InfrahubNumberPoolAllocations` returns
      five rows ordered by value then branch then holder id, each with `holder {id hfid kind
      display_label}` read on the row's branch, `identifier`, `provenance` (`PROVIDED` for 40 and
      500, `ALLOCATED` otherwise), `in_space` (false for 40 and 500), `range` (`1 - 50` for 40,
      `null` for 500) and `division: []`; the filters `in_space: false`, `branch: "b1"`,
      `provenance: PROVIDED`, `range_id` of `51 - 100` each return the expected rows with `count`
      before pagination; `offset` and `limit` page the ordered list; `division` on this pool is
      refused with the contract's message, and so is `division` on `InfrahubNumberPoolUtilization`.
      A second case with the attribute's `max_value` below a range's end checks `in_space: false`
      with `range` set for a value above the limit.
- [ ] T013 [P] [US1] Component tests in the same file on a pool scoped by `["site"]` at contract
      time: `allocation_scope: ["site"]` on utilization and divisions; the divisions list holds
      the mock divisions holding at least one row, ordered by utilization descending then label,
      each entry with `path: "site"`; the utilization query with `[{path: "site", value:
      "mock-2"}]` reports `mock-2` over the pool and over each range, and its `out_of_space_count`
      equals the `count` of the allocation list filtered on `mock-2` with `in_space: false`; every
      row's `division` is one of the listed divisions; filtering on `[{path: "site", value:
      "mock-2"}]` returns rows whose `division` is `mock-2`, and the number of distinct values
      among them equals `mock-2`'s `used` (SC-010); `[{path: "site", value: "nope"}]` returns an
      empty list with `count: 0`; `[{path: "role", value: "x"}]` (not in the scope) and
      `[{path: "site", value: "a"}, {path: "site", value: "b"}]` are refused naming the entry; read
      on a branch whose schema lacks `site`, `allocation_scope` is `[]` and the division filter is
      refused; without `division` the pool's `figures` are pool-wide.
- [ ] T014 [P] [US1] Component tests in the same file for refusals: an IP prefix pool as
      `pool_id` and a random uuid both raise `NodeNotFoundError` naming the id; `range_id` of
      another pool's range raises `ValidationError` naming the pool and the range; an unknown
      `branch` raises `BranchNotFoundError`.
- [ ] T015 [P] [US1] Regression tests in
      `backend/tests/component/graphql/queries/test_resource_pool.py`: `InfrahubResourcePoolUtilization`
      and `InfrahubResourcePoolAllocated` on the same unscoped pool return exactly what they
      return before this phase (count, percentages, edges, the 500 row absent); on the scoped pool
      they return pool-wide figures and the whole pool's values (FR-029).

### 3b. The allocated rows query

- [ ] T016 [US1] Extend `backend/infrahub/core/query/resource_manager.py::NumberPoolGetAllocated`:
      constructor arguments `ranges: Sequence[tuple[int, int]] | None` (the bounds to filter on:
      None lists every tracked value; the dedicated callers pass the pool's range set or the one
      range of `range_id`; absent, the generic callers keep today's `start_range` / `end_range`
      filter), `in_space: bool | None = None` (True: inside the given bounds, not in the
      attribute's `excluded_values`, within its `min_value` / `max_value`; False: the complement
      over every tracked value; limits and exclusions bound as parameters), `branch_name: str |
      None = None`, `provenance: PoolRecordProvenance | None = None`; project
      `coalesce(ir.provenance, $allocated_provenance) AS provenance`; add `provenance:
      PoolRecordProvenance` to `NumberPoolAllocatedResult`; keep `ORDER BY av.value, hv.branch,
      n.uuid`. The generic callers (`resolve_number_pool_allocation`, `NumberUtilizationGetter`)
      pass nothing new and render the same text as today. Component test in
      `backend/tests/component/core/resource_manager/test_number_pool.py` (extend): each filter
      alone and combined; two ranges with a null shorthand; the default renders today's rows.
- [ ] T016a [US1] Create `backend/infrahub/pools/effective_space.py` (pure): `in_space(value,
      ranges, excluded_values, excluded_ranges, min_value, max_value) -> bool` and `space_size(...)
      -> int` over a range set and the attribute's `NumberAttributeParameters`, with the definition
      of the contract's Vocabulary table. One-sentence module docstring: it stands in until the
      shared effective-space calculation exists. Unit tests in
      `backend/tests/unit/pools/test_effective_space.py`: value in a range, excluded single value,
      value in an excluded range, value above `max_value`, no range → size 0, two ranges.

### 3c. The mock partition

- [ ] T017 [US1] Create `backend/infrahub/pools/division_mock.py` with
      `division_of_row(holder_id: str, entries: tuple[ScopeEntry, ...]) -> DivisionKey` and
      `divisions(entries) -> tuple[DivisionKey, ...]`, assigning `mock-{int(UUID(holder_id)) % 3 + 1}`
      and building one `ScopeEntry` value per path in force. A one-sentence module docstring says
      it stands in for the division reads until they exist. Create `backend/infrahub/pools/scope.py`
      with the frozen dataclasses `ScopeEntry` and `DivisionKey` (`data-model.md` §3) and the pure
      `entries_in_force(scope, schema_branch, kind)` if Phase 4 has not created them yet.

### 3d. The dedicated surface

- [ ] T018 [US1] Create `backend/infrahub/graphql/queries/number_pool.py` with the object types
      `NumberPoolUtilization`, `NumberPoolUtilizationFigures`, `NumberPoolRangeUtilization`,
      `NumberPoolDivisions`, `NumberPoolDivision`, `NumberPoolDivisionEntry`,
      `NumberPoolAllocations`, `NumberPoolAllocation`, `NumberPoolHolder`, `NumberPoolRangeRef`,
      the input `NumberPoolDivisionEntryInput` and the graphene `Enum` `NumberPoolProvenance`
      (`ALLOCATED`, `PROVIDED`), with the field descriptions of the contract verbatim. Add a shared
      `_load_number_pool(graphql_context, pool_id) -> CoreNumberPool` raising
      `NodeNotFoundError(node_type="CoreNumberPool", identifier=pool_id)` for any other kind, a
      shared `_ranges(db, pool, branch, at)` ordered by `start`, and a shared
      `_scope_in_force(pool, branch) -> tuple[ScopeEntry, ...]` over `entries_in_force`.
- [ ] T019 [US1] Add `_figures(size, used_default_branch, used_branches) -> dict` in the same
      module (absolute counts plus the three percentages, 0 when `size` is 0) and the resolver
      `resolve_number_pool_utilization_surface`: rows from `NumberPoolGetAllocated(ranges=<range
      set>, in_space=True)` split into default-branch and other-branch value sets as
      `NumberUtilizationGetter.load_data` does today (do not call the getter: it reads the null
      shorthand); pool `figures` with `size` from `effective_space.space_size` over the range set;
      each range's figures from the values within its bounds and `end - start + 1`;
      `out_of_space_count` from `NumberPoolGetAllocated(in_space=False).count`; `allocation_scope`
      from `_scope_in_force`; `id` and `display_label` from the pool. Validate `division` as T021
      does and also refuse one that omits a path in force, naming the missing paths; with it, keep
      the rows of that mock division before computing every figure and the count. Pool-wide
      figures on a scoped pool read without `division` at this phase.
- [ ] T020 [US1] Add `resolve_number_pool_divisions`: with an empty scope in force return one
      division `{display_label: "", entries: [], figures: <pool figures>}`; otherwise partition the
      rows with `division_mock.division_of_row`, list the mock divisions holding at least one row,
      compute each division's figures over the pool's space, build `entries` with `value` and
      `display_label` from the key and `peer_kind` None, join labels with `" / "`, order by
      `utilization` descending then `display_label`, set `count`.
- [ ] T021 [US1] Add `resolve_number_pool_allocations`: validate `range_id`; translate it to the
      one range's bounds, otherwise pass no bounds (every tracked value); validate `division`
      (non-empty scope in force, every path in force, no duplicate; messages of the contract); run
      `NumberPoolGetAllocated` with `ranges`, `in_space`, `branch_name` (after
      `registry.get_branch` so an unknown branch raises `BranchNotFoundError`), `provenance`,
      `offset`, `limit`; when `division` is given, run without `offset`/`limit`, keep rows whose
      `division_mock.division_of_row` matches every given entry, then slice; `count` accordingly;
      build each row: `holder` from one `NodeManager.get_many(ids, branch=<row branch>, at)` per
      distinct branch (`display_label`, `hfid` via `get_hfid`, `kind` from the pool's `node`),
      `range` from `_ranges` by bounds, `in_space` from `effective_space.in_space`, `division`
      from the mock or `[]`.
- [ ] T022 [US1] Register the three root fields in
      `backend/infrahub/graphql/schema.py::InfrahubBaseQuery` as `InfrahubNumberPoolUtilization`,
      `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`, each a `Field` with the
      arguments and the root-field descriptions of the contract, `required=True`.

### 3e. The generic queries' description notes

- [ ] T023 [P] [US1] In `backend/infrahub/graphql/queries/resource_manager.py`, add
      `description=` to the root `Field`s `InfrahubResourcePoolUtilization` and
      `InfrahubResourcePoolAllocated` and a `class Meta: description = …` to `PoolUtilization`,
      `PoolAllocated` and `PoolAllocatedNode`, with the two note texts of the contract's "Generic
      queries frozen for number pools" table. No other change in the file.

### 3f. Freeze

- [ ] T024 [US1] Regenerate: `uv run invoke schema.generate-graphqlschema`, then
      `cd frontend/app && pnpm codegen`. Diff `schema/schema.graphql` against the contract's SDL
      and confirm that `PoolUtilization`, `PoolAllocated`, `PoolAllocatedNode`,
      `IPPrefixUtilizationEdge`, `IPPoolUtilizationResource` and the two generic root fields differ
      from the previous export in description text only (SC-009). Run `uv run invoke docs.validate`.
- [ ] T025 [US1] Add the snapshot test
      `backend/tests/unit/graphql/test_number_pool_surface_contract.py` pinning the printed SDL of
      the ten object types, the input, the enum, the three root fields and the `allocation_scope`
      field of the three `CoreNumberPool` inputs, so a later phase cannot rename, retype or remove
      what this phase published (FR-018).
- [ ] T026 [US1] Run T011–T016, T025 and
      `uv run pytest backend/tests/component/graphql/queries/test_resource_pool.py`.

**Checkpoint**: B merges. Frontend and SDK start from the exported schema. Everything below changes
no published field; the only later visible change is the mock partition giving way to real
divisions.

---

## Phase 4: Change set C — the seams (serves US2 and US3)

**Purpose**: the division key and the two entry points the internals plug into, so D1 and D2 can
be built concurrently.

- [ ] T027 [US2] Complete `backend/infrahub/pools/scope.py` (created in T017 if B landed first):
      `ScopeEntry`, `DivisionKey`, and `DivisionResolver.entries_in_force(scope, schema_branch,
      kind)` (pure) dropping every entry the branch's schema does not define on the kind, keeping
      scope order, carrying the relationship identifier for relationship entries.
- [ ] T028 [P] [US2] Unit tests in `backend/tests/unit/pools/test_scope.py` for
      `entries_in_force`: an entry the branch's schema does not define is dropped; all unknown →
      empty tuple; order preserved; relationship entries carry the relationship identifier.
- [ ] T029 [US2] Thread `division: DivisionKey | None = None` through
      `backend/infrahub/core/node/resource_manager/number_pool.py::CoreNumberPool.get_resource`,
      `get_next`, `get_free` and `get_used`, down to `NumberPoolGetFree` / `NumberPoolGetUsed`
      constructors. The queries ignore it in this phase; the unscoped text is unchanged.
- [ ] T030 [US2] Defer pool handling on update in `Node.from_graphql`
      (`backend/infrahub/core/node/__init__.py`): apply every attribute with
      `process_pools=False`, collect the attributes whose payload carried `from_pool`, then call
      `handle_pool` for each after the loop. `BaseAttribute.from_graphql` keeps assigning
      `from_pool` inline (the mutation lock names are read from it). Assert `Node.from_graphql` still
      has exactly its two callers.
- [ ] T031 [US2] Defer pool handling on template create: in
      `backend/infrahub/templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship`,
      record the pool id and mark the attribute pending in `TemplatePoolFields.pending` instead of
      allocating through `pools/default_allocator.py::DefaultPoolAllocator`; in
      `Node._process_fields_attributes`, run `handle_pool` for pending attributes after the
      relationships are applied. Remove `DefaultPoolAllocator.allocate_for_attribute` if it has no
      other caller; otherwise leave it and note the caller.
- [ ] T032 [US2] Functional tests in `backend/tests/functional/pools/test_numberpool_lifecycle.py`
      (extend): a scoped field changed and `from_pool` sent in one update allocates after the
      relationship is applied and the pool lock `resource_pool.<id>` is taken; a template-created
      node allocates after its relationships exist. These pass with an unscoped pool in this phase
      and gain scoped assertions in Phase 5.
- [ ] T033 [US3] Reduce `backend/infrahub/pools/number.py::NumberUtilizationGetter` to a seam: it
      loads rows and hands them to `DivisionReporter`; add
      `backend/infrahub/pools/division_report.py` with `Figures`, `DivisionFigures`,
      `DivisionReport` (`divisions`, `of(key)`, `of_within(key, start, end)`) and
      `DivisionReporter.report(rows, divisions, size, entries)`. With no entries it returns one
      division with an empty key and today's figures. `utilization`, `utilization_default_branch`,
      `utilization_branches`, `used_default_branch` and `used_branches` on the getter keep their
      values for an unscoped pool, so the generic resolver and the dedicated resolvers of Phase 3
      read unchanged figures.
- [ ] T034 [P] [US3] Unit tests in `backend/tests/unit/pools/test_division_report.py`: divisions
      ordered by utilization; a division with nodes and no records is not listed; branch split per
      division; absolute counts (`size`, `used`, `used_default_branch`, `used_branches`) per
      division; unscoped single division equals the whole; `of_within` reports `used` 0 for a range
      in which the division holds no value (spec User Story 3, scenario 3).
- [ ] T035 [US3] Regression: run `uv run pytest backend/tests/component/core/resource_manager/
      backend/tests/component/graphql/resource_manager/ backend/tests/component/graphql/queries/
      backend/tests/functional/pools/` and confirm identical figures (FR-005, SC-003) and an
      unchanged SDL snapshot (T025).

**Checkpoint**: C merges. D1, D2, D3 and D4 proceed in parallel.

---

## Phase 5: US2 — One pool, every site (change set D1, Priority: P1)

**Goal**: allocation returns the lowest free number within the writer's division, as a union over
live branches, with the unscoped query unchanged.

**Independent Test**: the scoped pool fixture; devices in several sites through the ordinary
allocation path, on one branch and on two.

### 5a. Tests first

- [ ] T036 [P] [US2] Snapshot test in
      `backend/tests/component/core/resource_manager/test_number_pool_query.py`: the text
      `reserved_values_query` renders with `division=None, with_branch=False` is byte-for-byte
      today's (capture it before T040).
- [ ] T037 [P] [US2] Component tests in
      `backend/tests/component/core/resource_manager/test_division_resolver.py` for
      `DivisionResolver.division_of`: relationship entry (peer set by id, by node, by
      human-friendly id), attribute entry, enum attribute unwrapped, two entries in scope order.
- [ ] T038 [P] [US2] Component tests in
      `backend/tests/component/core/resource_manager/test_number_pool_scoped_query.py`
      (`NumberPoolGetFree` / `NumberPoolGetUsed` with a division): one relationship entry; one
      attribute entry; two entries; the FR-001 two-branch case (D1 holds 5 in A on the default
      branch, moved to C on `b1`: default branch reads 6 free in A, 6 in C, 5 in D; delete `b1` → 5
      free in C with no write); the fork-window case on the hop (D1 moved from A to C **on the
      default branch** after `b0` forked: `b0` still reads 5 as taken in A); a self-referencing
      relationship entry collects only the forward peers; every entry unknown → the unscoped
      result.
- [ ] T039 [P] [US2] Functional tests in
      `backend/tests/functional/pools/test_numberpool_scoped_allocation.py` through GraphQL: the
      User Story 2 scenarios 1, 2, 3, 7, 8 and 9 of `spec.md`; fifty concurrent creates in site A
      yield fifty distinct numbers and fifty in A plus fifty in B yield 1–50 twice (FR-004); the
      Phase 4 deferral tests gain their scoped assertions.

### 5b. The division resolver and the scoped fragment

- [ ] T040 [US2] Add `DivisionResolver.division_of(db, node, entries) -> DivisionKey` to
      `backend/infrahub/pools/scope.py` (peer id through `RelationshipManager.get_peer_id`,
      attribute `.value`, enum unwrapped, `None` kept as `None`). In
      `backend/infrahub/core/node/__init__.py::Node.handle_pool`, resolve the entries against
      `registry.schema.get_schema_branch(name=self._branch.name)` from
      `number_pool.allocation_scope.value`, compute the division from `self`, and pass it to
      `get_resource`. Keep every existing refusal and message.
- [ ] T041 [US2] Pass the division from the two remaining allocation callers:
      `backend/infrahub/core/node/create.py` (template allocation after `obj.new()`) and
      `backend/infrahub/core/migrations/schema/node_attribute_add.py` (the backfill: load the scoped
      fields in the same query that loads `{"id", attr}` so there is no per-node round trip).
- [ ] T042 [US2] Extend `backend/infrahub/core/query/resource_manager.py::reserved_values_query`
      with `division: DivisionKey | None = None` and `with_branch: bool = False`. Lift the two-leg
      visibility predicate into a named module constant (open now on a non-deleting branch; or
      closed on the default branch, still inside a live fork window, with no hiding edge on the same
      vertex) and use it for the value read and for each entry hop. With a division: match
      `(n:Node)-[:HAS_ATTRIBUTE]->(attr)`, one `CALL` per entry collecting the peer uuids
      (relationship, arrows from `direction`, `Relationship {name: $identifier}`) or the values
      (attribute), then `WHERE $entry_i_value IN entry_i_values` for every entry, before the value
      read. Bind every name and value as a parameter. With `with_branch`, project `branch` from both
      legs and end `WITH DISTINCT res, value, branch`.
- [ ] T043 [US2] Render the division-side anchor as a second shape behind the same parameter (match
      the writer's peer or value vertex, walk to the nodes holding it, then to their reserved
      attributes for this pool), selected by a module-level switch, so T077 can profile both. Both
      must pass T038.
- [ ] T044 [US2] Pass the division from `get_free` / `get_used` into the fragment; `get_next` keeps
      its structure (P1's range walk lands around it, not inside the fragment).
- [ ] T045 [US2] Run T036–T039 and the full regression set from T035.

**Checkpoint**: User Story 2 is functional; scoped pools allocate per division.

---

## Phase 6: US3 — Which site is about to run out, and which numbers it holds (change set D2, Priority: P2)

**Goal**: the three dedicated queries read real divisions: the divisions holding a value listed
from the fullest, the utilization of one division over the pool and each range, the division
filter in Cypher, one value visible in two divisions.

**Independent Test**: uneven occupancy across sites on the scoped fixture; compare the headline, the
division rows, the range rows and the filtered allocation list against the records.

- [ ] T046 [P] [US3] Component tests in
      `backend/tests/component/core/resource_manager/test_number_pool_divisions_query.py` for
      `NumberPoolDivisions`: distinct tuples over nodes on the default branch and on `b1`; a
      node with no record still yields its division; a deleted node's division disappears; a
      `DELETING` branch's nodes are excluded; two entries.
- [ ] T047 [P] [US3] Extend `backend/tests/component/graphql/queries/test_number_pool_surface.py`
      with the real-division cases, replacing the T013 mock assertions: the spec's User Story 3
      scenario 1 (A 50 records, B two nodes no records, C no nodes → A alone listed with 50 of
      100, no division for B or C, utilization without `division` refused); scenario 2 (branch
      split over the division read); scenario 3 (the division of A reports 40 of 100, `1 - 50` 40
      of 50 and `51 - 100` 0 of 50; the division of B reports 30 of 100, `1 - 50` 0 of 50 and
      `51 - 100` 30 of 50); scenario 4 (a division keyed by a site that exists
      only on `b1`, read from the default branch, is listed with `display_label` falling back to the
      id and `peer_kind` null); scenario 5 (D1 holding 5 in A on the default branch and moved to C
      on `b1`: the allocation list filtered on A returns D1's two rows, the `b1` row's `division`
      naming C; filtered on C, the same two rows; SC-010 holds for both); a partial two-entry filter
      on a `["site", "role"]` pool; `InfrahubResourcePoolAllocated` count, offset and limit
      unchanged across the fragment move.
- [ ] T048 [US3] Add `NumberPoolDivisions` to `backend/infrahub/core/query/resource_manager.py`:
      over `(n:Node:<kind>)-[:IS_PART_OF]->(:Root)` with the visibility constant on the
      `IS_PART_OF` edge and one `CALL` per entry (same shape as T042), return the distinct tuple of
      entry values with `count(DISTINCT n.uuid)`; frozen dataclass result; `ORDER BY` on the tuple.
- [ ] T049 [US3] Move `NumberPoolGetAllocated` onto the shared fragment with `with_branch=True`
      and, when scoped, the per-entry value lists per row and a `division` filter rendered like the
      writer's division in T042 (requested entries instead of the writer's); keep `n.uuid`,
      `res.identifier`, `value`, `branch`, `provenance` and the T016 filters in the result and
      constructor because `resolve_number_pool_allocation` and the dedicated resolvers share the
      class.
- [ ] T050 [US3] Complete `NumberUtilizationGetter.load_data`: run both queries, resolve the entries
      in force on the reading branch, hand everything to `DivisionReporter`; expose
      `report.divisions`, `report.of` and `report.of_within`.
- [ ] T051 [US3] Replace the mock in `backend/infrahub/graphql/queries/number_pool.py`: pool
      `figures` from `of(key)`; each range's figures from `of_within(key, start, end)`; the
      divisions list from `report.divisions`; a row's `division`
      from the per-entry values the query returns for the row's branch; the `division` filter
      passed to `NumberPoolGetAllocated` so `count`, `offset` and `limit` are Cypher-side again;
      peer display labels and kinds from one `NodeManager.get_many(..., branch_agnostic=True)` over
      the distinct peer ids, falling back to the id; attribute values as text; a missing value as
      `""`. The module no longer imports `division_mock`.
- [ ] T052 [US3] Run T046, T047, T025 (the SDL snapshot must not change) and the regression set.

**Checkpoint**: User Stories 2 and 3 work; the three queries return real divisions.

---

## Phase 7: US4 and US5 — The scope write path and the schema-declared scope (change set D3, Priority: P2)

**Goal**: a scope is validated when saved on the pool and when declared in a schema, a
schema-created pool carries and refuses direct edits of its scope, and the attribute-add size check
is per division.

**Independent Test**: save pools with every invalid entry; load the scoped schema, allocate from two
sites, change the declaration on the default branch, reload, attempt a direct edit on the pool.

### 7a. Tests first

- [ ] T053 [P] [US5] Unit tests in `backend/tests/unit/pools/test_scope.py` (extend) for
      `ScopeValidator`: every refusal row of `contracts/graphql-pool-scope.md` (optional attribute,
      optional relationship, many relationship, related-node path, list kind, JSON kind, the pool's
      own attribute, duplicate, unknown entry) names the entry; `role__value` normalises to `role`;
      a valid two-entry scope returns the normalised tuple. Build the `SchemaBranch` from T003's
      schema in memory.
- [ ] T054 [P] [US5] Component tests in
      `backend/tests/component/graphql/resource_manager/number_pools/test_pool_scope.py` (extend
      T010's file): each refused entry through `CoreNumberPoolCreate` and `CoreNumberPoolUpdate`; a
      valid scope through create, update and upsert; an **unchanged** scope re-sent whole through
      update and upsert is accepted; a scope change on a `pool_type: Schema` pool is refused with
      the message of the scope contract, of the same form as the shorthand refusal in
      `test_schema_pools.py`.
- [ ] T055 [P] [US4] Component tests in `backend/tests/component/pools/test_schema_number_pool_scope.py`:
      `vlan_id` with ranges 100–200 and scope `["site"]` → the created pool reads back the scope and
      two sites both receive 100; clearing the scope on the default branch and reloading → next
      allocation 102; a scope declared on `b1` only does not change the pool until merge; a direct
      `CoreNumberPoolUpdate` of the scope is refused with the default-branch message; a declaration
      naming an optional field, a many relationship, a related-node path or an unknown field is
      refused at load naming the entry.
- [ ] T056 [P] [US4] Component test in
      `backend/tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py`
      (extend): adding a scoped `NumberPool` attribute of size 10 to a kind with 25 nodes spread
      over three sites (max 9 per site) is accepted; with 11 in one site it is refused with the
      division count in the message.

### 7b. The validator and its callers

- [ ] T057 [US5] Add `ScopeValidator(schema_branch)` to `backend/infrahub/pools/scope.py` with
      `validate(kind, attribute_name, scope) -> tuple[str, ...]`: calls
      `SchemaBranch.validate_schema_path(allowed_path_types=SchemaElementPathType.ATTR |
      SchemaElementPathType.REL_ONE_MANDATORY_NO_ATTR)`, then checks `optional` on the field itself
      (relationships included, because the path validator exempts `ip_namespace`), the attribute
      kind against list and JSON, the pool's own attribute, duplicates; normalises `__value` away;
      raises `ValidationError({"allocation_scope": …})` naming the entry.
- [ ] T058 [US5] Wire it into
      `backend/infrahub/graphql/mutations/resource_manager/number_pools/pool.py::InfrahubNumberPoolMutation`:
      `mutate_create` validates when a scope is sent (after `_resolve_target_attribute`, which
      already loads the kind); `mutate_update` validates only when the normalised submitted scope
      differs from the stored one, and refuses any change on a `pool_type == Schema` pool with
      the scope contract's message, beside `_refuse_shorthand_conflicts`. The schema branch is
      `registry.schema.get_schema_branch(name=graphql_context.branch.name)`.
- [ ] T059 [US4] Write the schema-declared scope onto the pool:
      `backend/infrahub/pools/schema_number_pool_upserter.py::SchemaNumberPoolUpserter.upsert_number_pool`
      sets `allocation_scope` from the parameters at creation;
      `backend/infrahub/pools/schema_number_pool_synchronizer.py::SchemaNumberPoolSynchronizer._update_pool_from_schema`
      copies it from the default-branch schema when it differs, as it does the bounds.
- [ ] T060 [US4] Call `ScopeValidator` from
      `backend/infrahub/core/schema/schema_branch.py::SchemaBranch._validate_number_pool_parameters`
      with `self` as the schema branch when `parameters.allocation_scope` is set.
- [ ] T061 [US4] In `backend/infrahub/core/validators/node/attribute.py::NodeAttributeAddChecker`,
      when the added `NumberPool` attribute declares a scope, compare the pool size against the
      largest per-division node count from `NumberPoolDivisions` (entries resolved with
      `DivisionResolver.entries_in_force` against `request.node_schema`'s branch). Needs T048.
- [ ] T062 [US4] Run T053–T056 and
      `backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py`.

**Checkpoint**: every pool-save and schema-load refusal of User Story 5 scenario 1 ships;
schema-created pools carry and honour a declared scope.

---

## Phase 8: US5 — A schema change that breaks a scope is refused (change set D4, Priority: P2)

**Goal**: a schema load that would make a scoped field optional, absent or cardinality many is
refused naming the pool.

**Independent Test**: load schemas that invalidate an entry a pool depends on through the component
checker and through the schema-load API.

- [ ] T063 [P] [US5] Unit test in `backend/tests/unit/core/validators/test_scoped_pool_dependency.py`:
      `ScopedPoolDependencyChecker.check` with a `node_schema` that no longer holds the field reads
      kind and field from `request.schema_path` and does not raise on the lookup itself.
- [ ] T064 [P] [US5] Component tests in
      `backend/tests/component/core/constraint_validators/test_scoped_pool_dependency.py`: a pool
      scoped by `site`; three loads (optional, removed, cardinality many) → three refusals naming the
      pool; a pool scoped by `["site", "pod"]` from `b1` and a default-branch load that never had
      `pod` → accepted; `node_attribute` itself removed → the existing attribute-removal path still
      governs (no double refusal).
- [ ] T065 [P] [US5] Component tests in `backend/tests/component/pools/test_pools_referencing_field.py`
      for `PoolsReferencingField.get`: pools on the kind, on a generic the kind inherits from, by
      scope entry and by `node_attribute`; a pool on an unrelated kind is not returned.
- [ ] T066 [US5] Create `backend/infrahub/pools/referencing.py::PoolsReferencingField` (repository,
      `db` in the constructor, `get(kind, field_name, branch) -> list[CoreNumberPool]`) using
      `NodeManager.query(CoreNumberPool, filters={"node__values": [kind, *generics]})` and a Python
      filter on `allocation_scope` and `node_attribute`.
- [ ] T067 [US5] Create `backend/infrahub/core/validators/pool/__init__.py` and
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
- [ ] T068 [US5] Integration-docker test
      `backend/tests/integration_docker/test_number_pool_scope_schema_load.py` (shard marker as the
      other tests in that folder): the removal refusal through the schema-load API names the pool.

**Checkpoint**: every refusal of User Story 5 ships and names what the user must change.

---

## Phase 9: US6 — Schema and pool changes travel together through branches (Priority: P3)

**Goal**: the branch seam end to end: unknown entries dropped per read, validation on the mutation
branch, the full scope after merge, the scope in force reported by the dedicated queries.

**Independent Test**: every scenario uses two branches.

- [ ] T069 [US6] Functional tests in `backend/tests/functional/pools/test_numberpool_scoped_branch.py`
      (`workflow_awaited_only` for the merge): `pod` declared required on Device in `b1` only;
      `["site", "pod"]` saves on `b1` and is refused on the default branch naming `pod`; the default
      branch allocates per site and `b1` per site and pod; `InfrahubNumberPoolDivisions` on the
      default branch reports `allocation_scope: ["site"]` with one-entry divisions and on `b1`
      `["site", "pod"]` with two-entry divisions; a `division` filter on `pod` is refused on the
      default branch and accepted on `b1`; after `b1` merges every branch allocates per the full
      scope; a node deleted on `b1` but live on the default branch still counts in its division on
      both; the unchanged scope re-sent whole from the default branch is accepted.
- [ ] T070 [US6] Extend `backend/tests/component/core/resource_manager/test_number_pool_branch_liveness.py`
      with the two lifecycle rows the spec adds: the scoped-field move on a branch (record counts in
      both divisions until merge or delete) and schema divergence (the transient double-1 under the
      coarser reading is accepted and documented in the test name by behaviour, not by issue).

**Checkpoint**: the branch cases in the spec's edge list each have a two-branch test.

---

## Phase 10: Change set E — mock removal (serves US1 and US3)

**Goal**: no mock division is returned by any query; the contract is unchanged.

- [ ] T071 [US3] Delete `backend/infrahub/pools/division_mock.py` and
      `backend/tests/unit/pools/test_division_mock.py`; confirm with `grep -rn "division_mock\|mock-"
      backend/infrahub` that no reference remains.
- [ ] T072 [US3] Add to `backend/tests/component/graphql/queries/test_number_pool_surface.py` the
      no-mock test: on the scoped fixture with values in three sites, read the three queries and
      assert that no `value` or `display_label` in any division entry, division row or allocation
      row begins with `mock-`, and that the divisions listed are exactly the sites (FR-019,
      SC-011).
- [ ] T073 [US3] Run T025 (SDL snapshot unchanged), T072 and the regression set.

**Checkpoint**: E merges. SC-011 holds.

---

## Phase 11: US7 — Replace a pool per site with one scoped pool (Priority: P3, deferred)

**Goal**: none in this slice. Gated on P2 attach, which is not built.

- [ ] T074 [US7] When attach lands on this branch, add the consolidation scenario to
      `backend/tests/functional/pools/test_numberpool_scoped_allocation.py`: P_A and P_B each handed
      out 1–10; scope P_A by site, attach the ten site-B nodes → A 10/100, B 10/100, next in B is
      11, P_B deletable. Until then this task is blocked and is not part of the slice's definition of
      done.

---

## Phase 12: US8 — The cost of a scoped pool is measured before it ships (change set F, Priority: P3)

**Goal**: SC-005 and SC-006 figures recorded; the anchor order chosen on numbers.

- [ ] T075 [P] [US8] Query benchmark `backend/tests/query_benchmark/test_number_pool_scoped_allocation.py`:
      a 4094-number pool with a three-entry scope (two relationships, one attribute), five live
      branches, fully occupied; one allocation; record latency and the `EXPLAIN`/`PROFILE` of the
      scoped free query (SC-006).
- [ ] T076 [P] [US8] Timed functional scenario
      `backend/tests/functional/pools/test_numberpool_scoped_throughput.py` marked `measurement`
      (excluded from the default run in `backend/pytest.ini` or the folder's `conftest.py`): one
      scoped pool versus N per-site pools serving the same nodes under concurrent allocation;
      record throughput for both (SC-005).
- [ ] T077 [US8] Run T075 against both anchor orders from T043 at the SC-006 shape and at a hub
      shape (one site holding most nodes); keep the better one, delete the other and its switch.
- [ ] T078 [US8] Write `dev/specs/ifc-3185-scoped-number-pools/measurements.md`: both figures, the
      plans, the anchor order kept, and the occupancy at which a stored division key would be
      needed. State whether SC-005 argues for a per-division lock; take no lock change in this
      slice.

---

## Phase 13: Polish & cross-cutting (change set F)

- [ ] T079 [P] Changelog fragments in `changelog/` (use the `creating-changelog-entries` skill):
      scoped allocation and per-division utilization (feature); `parameters.allocation_scope`
      (feature); the three dedicated number-pool queries (feature); the description notes on the
      generic resource-pool queries (changed description); the pool-save refusals (new refusal); the
      schema-load refusal naming the pool (new refusal); the allocation lists no longer showing a
      deleting branch's values (changed behaviour, from the allocated read moving onto the shared
      fragment).
- [ ] T080 [P] User docs: a "Scope a pool" section in `docs/docs/resource-manager/allocate-number.mdx`
      (web and GraphQL tabs, the refusal list, the branch note) and a "Read a number pool" section
      showing the three dedicated queries; an `allocation_scope` example in
      `docs/docs/schema/number-pool.mdx`; regenerate `docs/docs/snippets/attribute-kind-params.mdx`
      and `docs/docs/reference/schema/attribute.mdx` with `uv run invoke docs.generate`; run
      `uv run invoke docs.lint`.
- [ ] T081 [P] Knowledge: in `dev/knowledge/backend/database-schema.md`, beside the Resource Pool
      Reservations section, describe the division read (entries in force per branch, the per-entry
      union, the shared visibility rule) in a few lines; no spec or ticket references.
- [ ] T082 Final review of the surface with the user: re-judge form A (three root fields) against
      form B (one root object `InfrahubNumberPool` with sub-fields); record the outcome in
      `spec.md` Open points and, if form B is chosen, rename the three root fields in
      `graphql/schema.py` and the SDL snapshot in one change before the slice ships, keeping every
      type.
- [ ] T083 Run `/pre-ci`; confirm `uv run invoke docs.validate` passes with every generated file
      committed-ready and the SDK submodule pointer plan is recorded (SDK PR first, pointer bump
      after).
- [ ] T084 Run `quickstart.md` scenarios 1 to 6 and the regression guard; record the outcome in the
      PR description, not in the docs.

---

## Dependencies & execution order

```text
Phase 1 (setup) ─┬─> Phase 2 (A: schema) ─┬─> Phase 3 (B: surface, US1) ────────────────┬─> Phase 6 (D2, US3) ─> Phase 10 (E) ─┐
                 │                         ├─> Phase 4 (C: seams) ──┬─> Phase 5 (D1, US2) ─┤                                     │
                 │                         │                        └──────────────────────┘                                     ├─> Phase 12 (F, US8) ─> Phase 13
                 │                         ├─> Phase 7 (D3, US4/US5) ─────────────────────────────────────> Phase 9 (US6) ───────┤
                 │                         └─> Phase 8 (D4, US5) ─────────────────────────────────────────────────────────────────┘
                 └────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
Phase 11 (US7): blocked on P2 attach; outside this slice's definition of done.
```

- **Phase 2 blocks everything**: every generated type derives from the attribute and the field.
- **Phase 3 unblocks the frontend and the SDK** and freezes the contract; T025 guards it. It needs
  nothing from Phase 4: the mock partition and today's getter supply its data.
- **Phase 4 is the fan-out point**: once the seams exist, D1 and D2 are different files and can be
  built by two people; D3 and D4 depend only on A and can start as soon as it merges (T061 waits
  for T048).
- **Phase 6 depends on Phase 3** (the resolvers exist), **Phase 4** (the reporter) and **Phase 5**
  (`entries_in_force`, the visibility constant and the division filter shape).
- **Phase 9** needs D1, D2 and D3 to assert allocation, the dedicated queries and the schema-load
  path on two branches.
- **Phase 10** needs D2; it is the last change that touches the three queries.
- **Phase 12** needs D1; T077 decides between the two anchor orders T043 rendered.

## Parallel opportunities

| After | In parallel |
|---|---|
| Phase 1 | T003, T004 |
| Phase 2 merged | Phase 3 (B), Phase 4 (C), Phase 7 (D3), Phase 8 (D4) |
| Within Phase 3 | T011–T015 before T016; T016a, T017 and T023 beside T018–T022 |
| Phase 4 merged | Phase 5 (D1) and Phase 6 (D2) |
| Within Phase 5 | T036, T037, T038, T039 before T040 |
| Within Phase 6 | T046, T047 before T048 |
| Within Phase 7 | T053–T056 before T057 |
| Within Phase 8 | T063, T064, T065 before T066 |
| Phase 13 | T079, T080, T081 |

## Implementation strategy

1. **MVP = Phase 2 + Phase 3**: the schema and the frozen surface with real pool, range and
   allocation data and mock divisions. Frontend and SDK work starts here.
2. **Capability = Phase 4 + Phase 5**: scoped allocation through the ordinary, template and update
   paths.
3. **Operability = Phase 6, 7, 8**: real divisions on the surface, the scope write path and the
   schema-declared scope, every refusal. Three people can take these three concurrently.
4. **Honesty = Phase 10**: the mock is gone and a test says so.
5. **Confidence = Phase 9, 12**: the two-branch suites and the measurements.
6. **Ship = Phase 13**, including the form A versus form B review.

## Summary

| Metric | Value |
|---|---|
| Tasks | 85 |
| Setup / foundational (A) | 10 |
| US1 (B, surface) | 17 (T011–T026, T016a) |
| US2 (C seams + D1) | 16 (T027–T032, T036–T045) |
| US3 (C reporter + D2 + E) | 13 (T033–T035, T046–T052, T071–T073) |
| US4 and US5 (D3) | 10 (T053–T062) |
| US5 (D4) | 6 (T063–T068) |
| US6 | 2 |
| US7 (deferred) | 1 |
| US8 (F) | 4 |
| Polish | 6 |
| Parallel-marked tasks | 30 |
