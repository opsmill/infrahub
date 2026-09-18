# Tasks: Numbers you give the pool

**Input**: Design documents from `specs/ifc-3184-pool-number-attach/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/),
[critiques/critique-20260916.md](./critiques/critique-20260916.md)

**Tests**: required. The spec mandates them (Constitution IV) and two of this slice's items are
confirmed defects whose reproductions gate the release.

**Organization**: grouped by user story. US1 is foundational and **blocks everything** — it merges as
its own change set so SC-022 stays measurable.

## Format: `[ID] [P?] [Story] Description`

- **[P]** — can run in parallel (different files, no dependency on another incomplete task)
- **[Story]** — US1 (foundation), US2 (attach/re-pool), US3 (detach)
- Paths are exact. Code citations are `module::Symbol`, never line numbers.

---

## Phase 1: US1 — The ledger stays honest as data moves (Priority: P1, **foundational**)

**Goal**: re-anchor the reservation record from the shared value vertex to the per-object attribute,
migrate every existing record, take the pool out of `HAS_SOURCE`, and fix the two confirmed defects
the move exposes — with every reported figure unchanged.

**Independent Test**: run the existing number-pool suites plus the new lifecycle and migration
coverage against a database populated before the change. Every figure matches (SC-022), the two
confirmed defects behave, and the migration reports its counts.

**⚠️ This phase merges as its own change set, ahead of Phases 2–4.** Not a release boundary —
everything ships in one minor — but a review-and-merge boundary, because SC-022 can only be measured
where nothing else has moved the numbers.

### 1a. Read the ground truth first

- [X] T001 [US1] Read `dev/knowledge/backend/database-schema.md` (edge activity, priority
      resolution, soft-delete semantics) and `dev/knowledge/backend/query-pattern.md` before touching
      any Cypher. Architectural intent is often the answer — `AGENTS.md`, *Always Do*.
- [X] T002 [US1] Read `core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE` and its
      module docstring in full. Its per-branch-then-max contract is the shape T018 reuses.

### 1b. Tests first — the two confirmed defects

- [X] T003 [P] [US1] Promote `artifacts/test_fr036a_repro.py` into
      `backend/tests/component/core/resource_manager/test_number_pool_branch_liveness.py`. Keep all
      four cases; strip the issue references per `dev/guidelines/backend/testing.md` (*"do not
      describe which bug a test prevents"* — name the behaviour instead). **Must fail** before T018.
- [ ] T004 [US1] Rewrite
      `backend/tests/functional/convert_object_type/test_convert_object_type.py::TestConvertObjectTypeResourcePool::test_convert_number_pool`
      to assert the value the pool **reports** (through a query with a liveness join), not that an
      edge exists. Note it exercises a schema-defined `NumberPool` attribute, which FR-030 excludes
      from the feature but which the migration still rewrites.

      **Amended 2026-09-16 — the original "Must fail before T016" is struck.** It cannot fail, and
      that is a property of the scenario rather than of the rewrite. `handle_pool` unconditionally
      re-allocates a schema-defined `NumberPool` attribute, and in this test's fixture ordering
      (jack=1, paul=2, pierre=3; jack converted) the freed number is also the lowest free — so
      re-allocation hands back the same number and writes a valid record on the new attribute.
      `get_used` then collapses the duplicate row, because `DISTINCT` covers `(value, identifier)`
      and both rows carry the new id. The defect is structurally invisible here.

      No assertion was weakened to make it pass. The biting coverage T016 needs lives in
      `backend/tests/component/core/resource_manager/test_number_pool_object_conversion.py`, which
      exercises the case re-allocation cannot mask — a user-`from_pool` number carried across by
      field mapping — and was verified to fail without the fix
      (`AssertionError: the pool must still account for the number… assert [] == [1]`).
- [ ] T005 [P] [US1] Component test: renaming a pool-tracked attribute leaves the record `-global-`
      and the pool still reporting the number. **Must fail** before T015.

### 1c. Re-anchor the edge

- [ ] T006 [US1] ~~Add the `IS_RESERVED` `branch` range index to `core/graph/index.py::rel_indexes`~~
      — original rationale: it is the **only** property edge type without one, and FR-030b is about to
      put it on a read path that runs for every attribute of every kind. *(Critique E7 / risk R11.)*

      **Reverted 2026-09-16 by the PRD owner: the index does not earn its keep.** The premise about
      the read path holds, but a `branch` range index does not serve it. Every consumer expands
      `IS_RESERVED` from a bound vertex — `(pool { uuid: $pool_id })-[res:IS_RESERVED]->` and
      `OPTIONAL MATCH (pool_source:Node)-[rel_reserved:IS_RESERVED]->(a)` — so the planner uses
      expansion, never a relationship-index seek. And every record is written on `-global-`
      (`NumberPoolSetReserved`'s `rel_prop`), giving the index exactly one distinct key and zero
      selectivity. It cost write amplification on every reservation and bought no read. If records
      ever stop being `-global-`, revisit this **together with** the query shapes — an index alone
      would still not be reachable. Removed while m079 already owns the `GRAPH_VERSION` 78 → 79 bump,
      so it needed no migration of its own.
- [X] T007 [US1] Rewrite `core/query/resource_manager.py::NumberPoolGetUsed` and `::NumberPoolGetFree`
      to traverse `(pool)-[:IS_RESERVED]->(:Attribute)-[:HAS_VALUE]->(:AttributeValueIndexed)` and
      `(:Attribute)<-[:HAS_ATTRIBUTE]-(:Node)`. Drop the `n.uuid = res.identifier` join.
- [X] T008 [US1] Rewrite `::NumberPoolGetReserved` to resolve **forward** through `HAS_VALUE`, so a
      record pointing at an abandoned `Attribute` reports nothing rather than reporting the edge
      (FR-030c). Add the missing `status` predicate.
- [X] T009 [US1] Rewrite `::NumberPoolGetAllocated`: remove the `hs_active` gate entirely (FR-030c),
      reach the node through the record instead of `HAS_SOURCE`, and **add the branch/time/status
      predicate on the reservation edge that it does not have today** (risk R8).
- [X] T010 [US1] Rewrite `::NumberPoolSetReserved` from a bare `CREATE` to match-close-create,
      targeting the `Attribute` vertex and writing `provenance`. See
      [`contracts/reservation-ledger.md`](./contracts/reservation-ledger.md).
- [X] T011 [US1] Thread the `Attribute` vertex id through
      `core/node/resource_manager/number_pool.py::CoreNumberPool.get_resource` → `::reserve` → the
      ledger, and restate the idempotency lookup as "is there a live record from this pool on **this
      attribute**". Without this, T010 has no target to close. *(Critique E2.)*
- [X] T012 [P] [US1] Rewrite the five source-gate tests in
      `backend/tests/component/core/resource_manager/test_number_pool_query.py::TestNumberPoolGetAllocated`
      — they pin behaviour FR-030c deletes.
- [X] T013 [P] [US1] Re-anchor `backend/tests/helpers/agnostic_edges.py::pool_reservation_edges`: the
      `->(:AttributeValue)` target and the identifier filter both go. Update its callers, including
      `component/core/agnostic_retirement/test_on_node_delete.py::…::test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool`,
      which asserts the literal edge tuple.
- [X] T014 [P] [US1] Re-check `backend/tests/db_snapshot.py::DbSnapshotterDeduplicated` — its
      docstring says it does not account for `IS_RESERVED`, which changes meaning once the edge hangs
      off `Attribute`.

### 1d. The two confirmed defects and the rename bug

- [ ] T015 [US1] Port the `-global-` `CASE` from
      `core/migrations/query/node_duplicate.py::NodeDuplicateQuery._render_sub_query_per_rel_type`
      into `core/migrations/query/attribute_rename.py::AttributeRenameQuery` — both the
      `SET …branch = CASE WHEN …` on the new edge and the `WHERE rel.branch IN ["-global-", $branch]`
      close. Makes T005 pass.
- [ ] T016 [US1] Re-target `::PoolChangeReserved` to the **new node's `Attribute`**, matched by the
      pool's `node_attribute`. **It is shared by all three pool shapes** (`(pool:Node)` with both ends
      unlabelled), so branch on shape or split it — the IP shapes keep re-pointing at the same
      `:Node` and only relabel the identifier. Makes T004 pass.
- [ ] T017 [P] [US1] Component test: attribute **removal** closes the record via
      `AttributeRemoveQuery`'s existing `close_unretained_agnostic_fields` call. No code change
      expected — confirm the inheritance.

      **Amended 2026-09-17: the inheritance holds only for a branch-agnostic attribute.**
      `core/query/node_agnostic_retirement.py` gates the sweep on `anchor.branch =
      $global_branch_name`, where `anchor` is the `HAS_ATTRIBUTE` edge. A branch-aware attribute
      carries that edge on its own branch, so the sweep never reaches it and the record survives.
      Keep this task scoped to the agnostic case it already covers; the aware case is T017a.

- [ ] T017a [US1] **Retire the reservation record when the object is deleted, whatever the
      attribute's branch support.** Deleting an object today leaves its `-global-` `IS_RESERVED`
      edge active and open when the tracked attribute is branch-aware: measured on a `TestingTicket`
      whose `ticket_id` inherits `AWARE`, where `HAS_ATTRIBUTE` and `HAS_VALUE` are both closed by
      the delete and the reservation edge is untouched. One orphan accumulates per deleted object,
      for the lifetime of the pool.

      The number is still released, because the reads resolve forward and the delete closes
      `HAS_VALUE` — so this is not a reporting defect today. It matters because the record's
      remaining job is attribution: an orphan says a pool accounts for a number on an object that no
      longer exists, and nothing sweeps it. Test coverage currently hides this —
      `component/core/agnostic_retirement/test_on_node_delete.py::…::test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool`
      uses an agnostic schema, so it passes while the aware case leaks.

      Decide first whether the sweep can be reached at all: the `anchor.branch` condition identifies
      agnostic *fields*, while the reservation edge is `-global-` regardless of the attribute's
      branch support, so this likely needs its own arm rather than a relaxed condition. If it is a
      code change rather than inherited behaviour, records already leaked need a migration behaviour
      to clear them — `m079`'s orphan sweep only covers the legacy shape.

      Cover both branch supports in the test, so the agnostic case cannot stand in for the aware one
      again.
- [X] T018 [US1] Implement cross-branch liveness as a **union** (FR-036a) in the queries from T007,
      reusing the *shape* of `UNRETAINED_AGNOSTIC_FIELD_PREDICATE`: per-branch window
      `(branch @ $at) ∪ (origin @ min(branched_from,$at)) ∪ (-global- @ $at)`, per-branch resolution
      `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1`, `branch.status <> "DELETING"`,
      `count(DISTINCT … node.uuid)`, then an aggregate across branches. A **new** predicate, not a
      call to the existing one — that one resolves whether a *field* is retained, this resolves which
      *values* an attribute holds. Makes T003 pass.
- [ ] T019 [P] [US1] Property-style unit test for one-sidedness (invariant I3): for any branch set,
      the union result is a superset of every single-branch result. *(Critique E10.)*

### 1e. The pool leaves `HAS_SOURCE`

- [X] T020 [US1] Stop writing the pool to `source`: remove `attribute.source = number_pool.id` from
      both branches of `core/node/__init__.py::Node.handle_pool` and from the template allocation path
      in `core/node/create.py`.
- [X] T021 [US1] Add the derivation to
      `core/query/node.py::NodeListGetAttributeQuery._add_source_to_query`: one `OPTIONAL MATCH` for
      the inbound `-global-` `IS_RESERVED` on the already-bound `Attribute`, plus a `CASE` preferring
      the user's edge. **Return the pool vertex, not its uuid** — extraction reads
      `result.get_node("source").labels` and those labels select the concrete GraphQL type. Stays
      inside the `_include_source` gate.
- [X] T022 [P] [US1] Component test: a pooled attribute with no user source resolves `source` to the
      pool **and the correct GraphQL kind**, with no stored source edge. Assert the resolved kind, not
      only the uuid — an implementation returning an id alone passes a uuid assertion and still breaks
      `__kind__`. *(Risk R7.)*
- [X] T023 [P] [US1] Component test: a **user-set, non-pool** source on a pooled attribute changes the
      reported source and changes **nothing** the pool reports. No such test exists today (SC-019).
- [X] T024 [P] [US1] Fix the inaccurate comment in
      `graphql/mutations/profile.py::InfrahubProfileMutation._validate_no_resource_pools_in_data`
      claiming graphene includes unset fields as `None` keys. It does not, and a reviewer will read
      the new resolver against it.
- [ ] T024a [US1] Component test: allocating from a pool **named** rather than identified leaves a
      reservation record. `handle_pool` accepts either — `number_pool_id` is a uuid or a pool name,
      resolved through `registry.manager.query(filters={"name__value": ...})` — and the name path had
      no coverage asserting a record at all.

      It was broken and nothing caught it: `from_pool` kept the name the caller gave, so
      `get_create_data` emitted `pool_prop` carrying a name while `NodeCreateAllQuery` matches the
      pool vertex on `uuid`. Every by-name allocation wrote no record, and therefore no pool
      accounting and, once the pool left `HAS_SOURCE`, no source either. The only test that noticed
      was `component/graphql/resource_manager/test_number_pool_lookup_by_name.py`, and only
      incidentally, because it happened to assert `source_id`.

      Assert the record directly with `pool_reservation_edges`, as
      `migrations/schema/test_node_attribute_add.py` and the `m076` heal tests do, rather than
      inferring it from the source the record produces. Cover both entry points in the same test so
      the uuid path cannot stand in for the name path.

### 1f. Migration `m079`

- [ ] T025 [US1] Create the package
      `core/migrations/graph/m079_reanchor_number_pool_reservations/` (`__init__.py`, `migration.py`,
      `queries.py`) exporting `Migration079`, an `ArbitraryMigration` with `minimum_version = 78`.
      Model on `m078_retire_agnostic_property_edges/`. Registration is filename-driven — **no registry
      list to edit**.
- [ ] T026 [US1] Behaviour 1 — re-anchor every record. Resolve `identifier` to the **active** `Node`
      vertex using the `graph_traversal/_cypher.py::_SOURCE_MATCH` idiom (latest `IS_PART_OF` without
      pre-filtering status, keep only if active, then `ORDER BY branch_level DESC, from DESC LIMIT 1`);
      find the `Attribute` by the pool's `node_attribute`; `CREATE … SET new = properties(old) …
      DELETE old` per `m066::_reassign_has_source`, which preserves `-global-`.
- [ ] T027 [US1] Behaviour 2 — drop orphaned records whose object no longer exists. **Reports a
      pre-count and a post-count.**
- [ ] T028 [US1] Behaviour 4 — delete **every** `(attr)-[:HAS_SOURCE]->(:CoreNumberPool)` edge,
      unconditionally. FR-030b says the pool is never a stored source, so a stored one is legacy
      whatever state that pool's record for the attribute is in; scoping the sweep to a live record
      spares a released reservation, a collapsed-away loser, and an attribute renamed out from under
      its record. Behaviour 4 still runs before behaviour 3 as defence-in-depth against that scoping
      coming back. Pre- and post-count. *(Critique E3 / risk R10.)*
- [ ] T029 [US1] Behaviour 3 — collapse multi-pool records onto one `Attribute`; survivor is the
      **greatest `from`**. Pre- and post-count. Note in the code comment that this is *not* `m066`'s
      rule — `m066` keeps the earliest, and it answers a different question.
- [ ] T030 [US1] One transaction per behaviour, count read back before commit, and **no `return` from
      inside a transaction context** — the documented `m066` partial-commit hazard. *(Critique E4.)*
- [ ] T031 [US1] `validate_migration`: re-run a read query and turn leftovers into `result.errors`,
      following `m077::Migration077.validate_migration`.
- [ ] T032 [US1] Set **both** `result.nbr_migrations_executed` and `console.log(...)` per count.
      Counts reach an operator **only** through the console — `cli/db.py::migrate_database` never
      prints `nbr_migrations_executed`. Emit a structured log line alongside. *(Critique E11.)*
- [ ] T033 [US1] Bump `GRAPH_VERSION` 78 → 79 in `core/graph/__init__.py` and run
      `uv run pytest backend/tests/unit/core/graph/test_graph_version.py`.
- [ ] T034 [P] [US1] Component tests under
      `backend/tests/component/core/migrations/graph/m079_reanchor_number_pool_reservations/`: one per
      behaviour, the duplicate-uuid node case, idempotency, and the console counts (assert the logged
      string, as `m078`'s tests do).
- [ ] T035 [US1] Component tests for the source sweep: two pools with live records on one attribute,
      both carrying legacy pool source edges — after migration the attribute reports the surviving
      pool and has **no** stored source edge; plus the cases with no live record at all (a released
      reservation, and an attribute renamed out from under its record), whose edges must also be gone.
- [ ] T036 [P] [US1] `backend/tests/integration_docker/test_number_pool_migration.py` — the upgrade
      path end to end. **Module-level `pytestmark = pytest.mark.shard_a|shard_b` is mandatory**, with a
      matching entry in the `backend-docker-integration` `shard:` matrix in `.github/workflows/ci.yml`;
      `conftest.py` validates the whole collection `tryfirst`, so a missing marker fails CI rather than
      silently never running. *(Dropped 2026-09-16 by the user: component coverage is sufficient; no
      docker integration test.)*

### 1g. SC-022 evidence

- [ ] T037 [US1] Capture every figure a pool reports — utilization, the branch split, the in-use list
      — on a database populated **before** the change; run the migration; re-capture. Assert identical
      except where FR-036a corrects a known defect. This is the strongest evidence the migration is
      safe, and it is only measurable at this boundary.

### 1h. Docs

- [ ] T038 [P] [US1] Document `IS_RESERVED` in `dev/knowledge/backend/database-schema.md` — its three
      target shapes, its `-global-` scope, its properties including `provenance`, and the forward
      liveness resolution. The edge-type table omits it entirely today. Follow
      `dev/guidelines/documentation.md` (*Writing Style → For Internal Docs* and the *Don't* list).

**Checkpoint**: the ledger is re-anchored, both confirmed defects are fixed, every figure is
unchanged. **Merge this change set before starting Phase 3.**

---

## Phase 2: US2 — Bring existing numbers under a pool (Priority: P1)

**Goal**: a user provides a number together with the pool that should track it — on create or update
— and can move an object between pools in one write.

**Independent Test**: create a pool over a partly-used range, attach the objects holding numbers in
it, and assert what the pool reports in use, in the bucket, and as its next number.

### 2a. Tests first

- [ ] T039 [P] [US2] Create `backend/tests/unit/pools/` (with its `__init__.py`, per
      `dev/knowledge/backend/package-init-files.md`) and write `test_intent.py` — **every cell** of the
      table in [`contracts/from-pool-intent.md`](./contracts/from-pool-intent.md), both re-pool cells,
      the idempotent no-op, and an assertion that **exactly one** input combination produces `REFUSE`
      (assert the count, so a future edit cannot quietly add a second refusal). No database.

### 2b. Payload presence

- [ ] T040 [US2] Carry payload **presence** into the create path: `core/attribute.py::BaseAttribute`
      records whether `value` and `from_pool` were present, not just their values.
      `BaseAttribute.__init__` uses `data.get(...)` today and drops the distinction;
      `BaseAttribute.from_graphql` already uses `"from_pool" in data` and keeps it. Add fields
      alongside the existing ones so nothing reading `attribute.value` / `attribute.from_pool` changes.

### 2c. The resolver

- [ ] T041 [US2] Create `backend/infrahub/pools/intent.py` with `FromPoolIntentResolver` — pure, no
      database, no node access. Intents are an **enum**. Inputs and the full table are in the contract.
- [ ] T042 [US2] Rework `core/node/__init__.py::Node.handle_pool` into an executor driven by the
      resolver. It keeps the I/O — pool lookup by uuid **or** name, the FR-023 attachment check
      (`number_pool.node.value in [kind] + inherit_from and node_attribute.value == attribute.name`),
      the template refusal, the schema-`NumberPool` path. Stop it mutating `attribute.from_pool` and
      `attribute.is_default` on the preview pass, which is meant to be side-effect-free.
- [ ] T043 [US2] Implement the attach path (FR-021, FR-024): a provided `value` alongside
      `from_pool` is **kept**, not discarded, and recorded with `provenance=provided`.
- [ ] T044 [US2] Implement the single refusal — `from_pool` alone on a non-default untracked value —
      naming **both** ways forward: restate the value to attach, or send `value: null` to discard and
      allocate. Follow `dev/guidelines/backend/exceptions.md`.
- [ ] T045 [US2] Implement re-pool (FR-024a): a write naming pool B on an attribute pool A reserves
      ends A's record and begins B's in one operation, allocating or attaching.
- [ ] T046 [US2] On attach onto an existing record from the same pool, update `provenance` to
      `provided` — it describes how the number the attribute *currently* holds got there.
      *(Critique P5.)*

### 2d. Locking

- [ ] T047 [US2] Contribute the lock name of the pool **currently tracking** the attribute in
      `core/node/lock_utils.py::get_lock_names_on_object_mutation`, not only the pool named in the
      payload. Without it two concurrent re-pools of one attribute into different pools each close the
      other's record and both create. The update path already reads the node for uniqueness hashes, so
      this is an extra field on an existing read. *(Risk R6.)*
- [ ] T048 [P] [US2] Component test for concurrent re-pool of one attribute into two different pools:
      one wins, exactly one live record remains (invariant I1).

### 2e. Component coverage

- [ ] T049 [P] [US2] The ledger against a database: attach, and attach with duplicates present.
- [ ] T050 [P] [US2] A plain value change writes **nothing** to the ledger and the number tracked
      follows the attribute (FR-031 deleted, SC-013). **No test exists today.**
- [ ] T051 [P] [US2] Re-pool A→B ends A's record, B reports the number, **and A's out-of-space bucket
      is empty** (SC-018). The empty-bucket assertion is what catches a half-finished implementation.
- [ ] T052 [P] [US2] Idempotent resend: the same `value` + `from_pool` for a number the object already
      owns is a silent no-op.
- [ ] T053 [P] [US2] Extend `backend/tests/functional/pools/test_numberpool_lifecycle.py` and
      `test_numberpool_branch.py` with the attach journey. **Extend — do not add parallel modules**:
      two-branch allocation, branch delete, node delete and allocation over pre-existing nodes are
      already covered (`research.md` D15).

**Checkpoint**: attach, re-pool and the refusal work. The pool tracks numbers it did not hand out.

---

## Phase 3: US3 — Take a pool back off a number (Priority: P2)

**Goal**: detach a number from a pool; the pool stops reporting it and the object keeps it.

**Independent Test**: attach a number, detach it, assert the object's value is unchanged, the in-use
count dropped by one, and the number is offered again.

- [ ] T054 [US3] Implement the release query in `core/query/resource_manager.py` — end the single
      `-global-` record between a pool and an `Attribute`. **No identifier matching.** Time-close
      (`to = $at`), never `status = "deleted"`: a tombstone is terminal per the database-schema doc,
      which is wrong for a record a later re-attach may recreate. This query is new — nothing releases
      a reservation today.
- [ ] T055 [US3] Wire the `DETACH` intent through the executor (FR-025). The number on the object is
      unchanged, and nothing is cleared from `HAS_SOURCE` because the pool was never written there.
- [ ] T056 [P] [US3] Component test: detach leaves the value untouched, drops the in-use count by one,
      and makes the number allocatable again (SC-014).
- [ ] T057 [P] [US3] Component test: with 50 held by two objects under one pool, detaching one ends
      only that record; the other still reports 50 (FR-028a).
- [ ] T058 [P] [US3] Component test: detach on a branch, then delete that branch — no branch reports a
      pool source and the pool reports nothing for it (SC-020).
- [ ] T058a [US3] Revisit
      `backend/tests/component/core/resource_manager/test_number_pool_query.py::TestNumberPoolGetAllocated`.
      Its five source-gate tests were inverted in Phase 1: clearing, reassigning or merging a change to
      an attribute's `source` used to drop the number from what the pool reports, and now leaves it
      reported, because FR-030c makes the record the only thing that answers. They read as "clearing
      the source does not detach", which is the whole of what detaching meant before this phase
      existed.

      Once `DETACH` lands, they are the wrong shape: they still exercise the *only* way a user could
      previously take a number off a pool, but say nothing about the way that replaces it. Either
      extend them so each source manipulation is paired with a real detach on the same attribute —
      proving the two are independent — or move the source-independence assertion to one test and give
      detach its own, rather than leaving five tests describing a gesture that no longer means
      anything.

**Checkpoint**: detach works and is permanent, symmetric with allocation.

---

## Phase 4: Reporting (serves US2; required for SC-015, SC-018)

- [ ] T059 [US2] Create `backend/infrahub/pools/effective_space.py` — the membership/size interface from
      [`contracts/effective-space.md`](./contracts/effective-space.md), plus the interim single-range
      adapter over `start_range`/`end_range` ∩ `[min_value, max_value]` minus intersecting exclusions.
      **Do not reimplement membership** — the adapter lifts arithmetic `get_next` already does inline,
      and it is deleted when P1's calculator lands.
- [ ] T060 [P] [US2] Unit suite `backend/tests/unit/pools/test_reporting.py` — distinct-element
      counting with duplicates, the in-space/out-of-space partition, the branch split, and an **empty**
      effective space (must not divide by zero).
- [ ] T061 [US2] Create `backend/infrahub/pools/reporting.py` with `PoolUtilizationReporter` — pure.
      Takes a record set and an effective space; returns the distinct-element count, the branch split, and the out-of-space
      bucket. Owns invariant I4: count **distinct elements**, never records, or utilization exceeds
      100%. Handle a zero-size space without dividing.
- [ ] T062 [US2] Reduce `pools/number.py::NumberUtilizationGetter` to a fetch-and-delegate seam,
      owning no arithmetic. Preserve today's distinct-union semantics exactly (the three set
      comprehensions in `load_data` partition a distinct union).
- [ ] T063 [US2] Extend the pool query surface in `graphql/queries/resource_manager.py`: `provenance`
      per in-use row, and the out-of-space bucket as a list of rows carrying value, holder **and
      branch** (FR-027a). One row per **(record, branch-resolved value)**.
- [ ] T064 [P] [US2] Component test: an attach outside the ranges succeeds, is bucketed not counted,
      and moves into the utilization fraction when a range is widened — with **no re-attach**
      (SC-015). Cover both paths into the state: attached out of range, and a range removed under a
      tracked value.
- [ ] T065 [P] [US2] Component test: one record straddling the boundary — in space on one branch, out
      of space on another — appears in the fraction **and** the bucket, told apart by the branch on the
      row.
- [ ] T066 [P] [US2] Component test: 50 allocated to A and attached on B with no uniqueness constraint
      gives **two rows** in the in-use list, one `allocated` and one `provided`, while utilization
      counts 50 **once** (SC-001).

---

## Phase 5: Polish & release readiness

- [ ] T067 [US1] Benchmark `backend/tests/query_benchmark/test_number_pool_allocation.py` —
      allocation **and the utilization read** against `develop`, before and after T018, varying live
      branch count. Needs a new axis: `BenchmarkConfig` has only `neo4j_image`, `neo4j_runtime` and
      `load_db_indexes`, and the one branch-aware benchmark creates exactly one extra branch. **No
      numeric gate** (SC-017 withdrawn) — a superlinear curve or a large constant is a release
      decision.
- [ ] T068 [US1] Benchmark the FR-030b source derivation on a metadata read over a kind with **no**
      pool. That is the blast radius — the plan otherwise reasons only about pooled attributes.
      *(Critique E7.)*
- [ ] T069 Regenerate every generated artefact — `uv run invoke backend.generate`,
      `schema.generate-graphqlschema`, `schema.generate-jsonschema`, `docs.generate`. **Never
      hand-edit.** CI's `validate-generated-documentation` fails on stale output.
- [ ] T070 [P] Seven towncrier fragments, one per item in spec.md *Behaviour changes needing changelog
      entries*. Use the `creating-changelog-entries` skill. Item 3 is the deliberate regression: say
      plainly that identifying which numbers to attach is the operator's job, rather than implying a
      tool exists.
- [ ] T071 [P] Update user documentation in `docs/` for the resource-manager pages: providing a number
      with a pool, detaching, the out-of-space bucket, and the upgrade path. The brownfield section
      must be honest that adoption is manual and one object at a time.
- [ ] T072 Name this slice in the **published-contract review** (ADR 0010) alongside P1's and P3's
      `NumberPoolParameters` changes — one review, one SDK type regeneration. **Name FR-030b in words
      within it**: the generated schema will not show it, because the field and type are unchanged and
      only its provenance moves. A reviewer diffing `schema/schema.graphql` sees no trace of a change
      that alters what every pooled attribute reports as its source.
- [ ] T073 Run `/pre-ci` (`.agents/commands/pre-ci.md`) — it includes the whole-repo
      `ruff check . --exclude python_sdk` that `invoke lint` does not, and `docs.validate`.
- [ ] T074 Run `uv run invoke format` and `uv run invoke lint`.

---

## Open items that are not tasks

These need someone outside the development team.

- [x] **OQ1 — RESOLVED 2026-09-16 by the PRD owner: P2 wins.** `source` can be cleared on
      pool-sourced attributes. P1's FR-030a / Decision 2 — *"the `source` of a pool-tracked value is
      the pool … and users cannot clear it"* — is **superseded** by this slice's FR-030b, and P1's
      FR-030a is deleted.

      Remaining action, now mechanical rather than a decision: **amend `POOL-RANGES-PRD.md` before P1
      enters spec-kit** — delete FR-030a from its *"Carried from P2"* section, delete Decision 2 from
      its decisions table, and delete its resolved open question #2 (*"detach clears the pool-owned
      `source`"*), which cites a P2 clause FR-025 no longer contains.

      What "cleared" means under FR-030b, so P1 is not amended into a different misunderstanding: the
      pool is never in `HAS_SOURCE`, so there is no pool-owned source to clear. A user clears **their
      own** source edge, and the slot then falls back to the derived pool — clearing *reveals* the
      pool rather than emptying the field. Covered by SC-019 and T023.
      *(Critique E13, risks R2/R14.)*
- [x] **OQ2 — RESOLVED 2026-09-16: out of scope.** Operators manually name the values they want a
      pool to track. P1 deletes the hand-set-value scan outright per its FR-011, unchanged, and this
      slice adds no enumeration surface. The tasks that carried it are removed; FR-011a and SC-023 are gone
      from the spec; the ergonomic cost on the brownfield path is accepted knowingly and recorded in
      *Out of Scope*. A migration tool may be added later if adoption shows it is needed.

---

## Dependencies

```
Phase 1  US1 — FOUNDATION  ◄── merges as its own change set
    T001,T002 (read)
        ▼
    T003,T004,T005 (failing tests)
        ▼
    T006 (index) → T007,T008,T009 (read queries) → T010 → T011 (vertex threading)
        ▼
    T012,T013,T014 (test/helper updates)  [P]
        ▼
    T015 (rename fix) ‖ T016 (conversion) ‖ T017
        ▼
    T018 (FR-036a — after the re-anchoring, or it is written twice) → T019
        ▼
    T020,T021 (source) → T022,T023,T024  [P]
        ▼
    T025 → T026 → T028 → T029 → T027 → T030,T031,T032,T033
              (T028 BEFORE T029 — ordering hazard)
        ▼
    T034,T035,T036  [P]  →  T037 (SC-022)  →  T038
        ▼
    ══════════ MERGE BOUNDARY ══════════
        ▼
Phase 2  US2 — attach / re-pool        Phase 4  Reporting
    T039 (failing unit test)               T059 (effective space)
        ▼                                      ▼
    T040 → T041 → T042,T043,T044,T045      T060 (failing unit test) → T061
        ▼                                      ▼
    T046 → T047                            T062 → T063
        ▼                                      ▼
    T048..T053  [P]                        T064,T065,T066  [P]
        ▼
Phase 3  US3 — detach
    T054 → T055 → T056,T057,T058  [P]
        ▼
Phase 5  Polish
    T067,T068 (benchmarks) → T069 → T070,T071  [P] → T072 → T073 → T074
```

**Hard orderings, and why:**

- **T018 after T007–T011.** FR-036a is written against the post-move edge chain. Doing it first means
  writing it twice.
- **T028 before T029.** Defence-in-depth only: T028's predicate no longer reads the records, so
  neither order can leave an edge behind. The order holds the line if the predicate is ever narrowed
  back to a live record, where the collapse would kill a losing pool's record first and its source
  edge would survive and win the read slot forever.
- **T011 before T010 can work.** Match-close-create has no target to close until `get_resource` sees
  the `Attribute` vertex.
- **T059 before T061.** The reporter takes the effective space as an input and never computes it.
- **Phase 1 merges before Phase 2 starts.** SC-022 is only measurable where nothing else has moved the
  numbers.

## Parallel opportunities

- T003 ‖ T005 — independent failing tests.
- T012 ‖ T013 ‖ T014 — different test files.
- T022 ‖ T023 ‖ T024 — different files.
- T034 ‖ T036 — component and integration_docker.
- T048 ‖ T049 ‖ T050 ‖ T051 ‖ T052 — independent component tests.
- T064 ‖ T065 ‖ T066 — independent component tests.
- Phase 2 and Phase 4 are fully independent once Phase 1 has merged; they meet at T063, which is the
  only task needing both the resolver's output and the reporter.

---

## Summary

**74 tasks** across 5 phases. Both open questions are resolved (see above).

| Phase | Tasks | Story |
|---|---|---|
| 1 — Foundation | T001–T038 (38) | US1 |
| 2 — Attach / re-pool | T039–T053 (15) | US2 |
| 3 — Detach | T054–T058 (5) | US3 |
| 4 — Reporting | T059–T066 (8) | US2 |
| 5 — Polish | T067–T074 (8) | — |

There is no setup phase: every module, package and test tree is created by the first task that needs
it.

The foundation is half the work and delivers no user-visible capability. That is the shape of the
problem, not a planning failure: the ledger is anchored somewhere that makes three required
behaviours unbuildable and two existing behaviours wrong.
