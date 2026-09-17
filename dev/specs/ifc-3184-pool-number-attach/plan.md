# Implementation Plan: Numbers you give the pool

**Branch**: `pool-number-attach-ifc-3184` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Epic**: [IFC-3184](https://opsmill.atlassian.net/browse/IFC-3184)

**Input**: Feature specification from `specs/ifc-3184-pool-number-attach/spec.md`, derived from
`POOL-ASSIGNMENT-PRD.md`. Research and decisions in [research.md](./research.md).

---

## Summary

A number pool learns to track numbers it did not hand out. A user provides a number together with
the pool that should account for it — on create or on update — and the pool records it, counts it in
utilization, and never offers it again. A pool can be taken back off a number without changing the
number. The pool refuses nothing: a value outside its ranges is tracked and reported in a bucket of
its own rather than folded into the utilization fraction.

Underneath, the pool's ledger moves. The `IS_RESERVED` record is re-anchored from the shared,
de-duplicated `AttributeValue` vertex to the per-object `Attribute` vertex, and the pool stops
writing itself into that attribute's `HAS_SOURCE`; `source` derives the pool from the record instead.
Those two moves are what make the rest correct — a value change becomes a no-op for the ledger,
detach becomes expressible, and the record inherits branch-agnostic retirement's sweep. They also
withdraw an invariant that currently holds by accident (one pool per attribute), which is restored
by construction, and they expose two confirmed data-integrity defects that must be fixed in the same
release: object conversion re-points the record at the abandoned attribute, and cross-branch liveness
is resolved winner-takes-all rather than as a union.

The work lands as three sequenced change sets in one minor release, alongside P1 (several ranges).

---

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.131, graphene (pinned), Pydantic 2.12, Neo4j driver 6.2

**Storage**: Neo4j 2026.05 — temporal, branch-aware property graph. See
`dev/knowledge/backend/database-schema.md`.

**Testing**: pytest 9.0. Tiers used here: `tests/unit/` (the two pure modules),
`tests/component/` (queries, ledger, migration behaviours — testcontainers),
`tests/functional/` (lifecycle/branch suites), `tests/integration_docker/` (one upgrade-path test),
`tests/query_benchmark/` (the FR-036a allocation benchmark).

**Target Platform**: Linux server (containerised backend)

**Project Type**: Backend-only change to an existing web service. **No frontend work** — the backend
must expose everything the deferred views need so they require no further backend change.

**Performance Goals**: no numeric target (SC-017 withdrawn). Net expectation is an improvement:
P1 deletes the per-allocation in-memory taken-set, the re-anchoring removes the liveness traversal's
fan-out over a globally shared value vertex and the uuid join with it, and FR-031's deletion removes
pool-lock contention on plain number edits. The one regression risk is FR-036a's per-branch
resolution inside `get_resource`'s pool-wide lock; it carries a mandatory benchmark and no gate.

**Constraints**:
- Records stay branch-agnostic (`-global-`), so attach and detach take effect on every branch at once.
- Liveness must be one-sided: the pool may report a number taken that is free on some branch, never
  free when taken on any.
- Utilization counts distinct elements of the effective space, never records.
- The migration must preserve every figure a pool reports (SC-022), and reports a count for each of
  its three destructive behaviours.

**Scale/Scope**: ~6 Cypher queries rewritten, 1 new release query, 1 graph migration over every
existing reservation, 2 new pure modules, 2 new GraphQL output fields, 1 new refusal, 0 new core
kinds, 0 new dependencies.

---

## Constitution Check

*Gate evaluated before Phase 0 and re-evaluated after Phase 1 design. Constitution v1.0.0.*

| Principle | Verdict | Notes |
|---|---|---|
| **I. Schema-Driven Integrity** | ⚠️ **Gated — passes with conditions** | No new core kind, but a data migration over every reservation, carrying the first deliberate deletion of reservation data. Conditions: `GRAPH_VERSION` 78→79; `minimum_version = 78`; `validate_migration` implements a post-condition; three counts reported to the console; generated files regenerated not edited (`uv run invoke backend.generate`, `schema.generate-graphqlschema`, `schema.generate-jsonschema`, `docs.generate`). |
| **II. Branch-Safe by Default** | ⚠️ **Gated — this is the principle under test** | The slice's whole correctness argument is branch behaviour. FR-036a is a confirmed violation *in existing code* that this slice must fix: a ledger branch-agnostic in storage must still be branch-*honest* in what it reports. Every lifecycle row is specified and tested. Merge behaviour for the new state is specified (the record is `-global-`, so it does not merge; the value it resolves to does). |
| **III. Type Safety & Explicit Contracts** | ✅ **Passes** | `from_pool` changes meaning without changing shape and `source` changes provenance without changing shape, so the decision table *is* the contract — hence `FromPoolIntentResolver` is extracted and unit-tested. Query results come back as frozen dataclasses via `get_data()`, never raw records. New intents are an enum, not strings. |
| **IV. Test Discipline** | ✅ **Passes** | Two pure modules with unit suites; component tests per lifecycle row; functional extension; one `integration_docker` upgrade test; a benchmark. E2E travels with the deferred frontend — **noted as a deliberate deviation**, see Complexity Tracking. |
| **V. Query Performance & Efficiency** | ⚠️ **Gated — passes with a benchmark** | Net improvement expected; one real regression risk (FR-036a inside the pool lock). All queries stay parameterised. The reporting split must not reintroduce an N+1 over records — `PoolUtilizationReporter` is pure and consumes one already-fetched record set. |
| **VI. Security & Input Boundaries** | ✅ **Passes** | No new authn/authz surface. No new user input reaches Cypher unparameterised. The one new error message names two remedies and exposes no internals. |
| **VII. Simplicity & Maintainability** | ✅ **Passes** | Net reduction: one storage for the pool's claim instead of two hand-synchronised across incompatible scopes; one arithmetic for utilization instead of set comprehensions in a fetcher; FR-031's record-move, self-healing clause and second lock key all deleted. The two new modules each serve an existing caller and exist to make an untestable decision table testable. |

**No principle is violated.** Three are gated on conditions carried as tasks.

---

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3184-pool-number-attach/
├── spec.md                      # Feature specification
├── plan.md                      # This file
├── research.md                  # Phase 0 — decisions D1..D15 and PRD corrections
├── data-model.md                # Phase 1 — the record, its states, the migration
├── quickstart.md                # Phase 1 — how to validate the feature works
├── contracts/
│   ├── graphql-pool-query.md    # The two new output fields + source provenance
│   ├── from-pool-intent.md      # The decision table, as a contract
│   ├── effective-space.md       # The seam this slice consumes from P1
│   └── reservation-ledger.md    # PoolRecordLedger's internal contract
├── artifacts/
│   └── test_fr036a_repro.py     # Rescued exploratory repro (see research.md §0 item 8)
├── checklists/
│   └── requirements.md
├── alignment-check.md           # Phase 5
└── tasks.md                     # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── query/
│   │   ├── resource_manager.py              # 6 queries rewritten + 1 new release query
│   │   ├── agnostic_retention.py            # shape reused for cross-branch liveness (read-only)
│   │   └── node.py                          # NodeListGetAttributeQuery._add_source_to_query
│   ├── node/
│   │   ├── __init__.py                      # Node.handle_pool — becomes an executor
│   │   ├── lock_utils.py                    # lock the currently-tracking pool too
│   │   └── resource_manager/number_pool.py  # CoreNumberPool: get_used/get_free/reserve/release
│   ├── attribute.py                         # payload-presence flags on BaseAttribute
│   ├── constants/database.py                # (no change — IS_RESERVED already enumerated)
│   ├── convert_object_type/object_conversion.py   # caller of the re-targeted query
│   └── migrations/
│       ├── graph/m079_reanchor_number_pool_reservations/   # NEW package
│       │   ├── __init__.py                  # exports Migration079
│       │   ├── migration.py
│       │   └── queries.py
│       └── query/attribute_rename.py        # port node_duplicate's -global- CASE
├── core/graph/__init__.py                   # GRAPH_VERSION 78 -> 79
├── pools/
│   ├── number.py                            # NumberUtilizationGetter reduced to a seam
│   ├── intent.py                            # NEW — FromPoolIntentResolver (pure)
│   ├── reporting.py                         # NEW — PoolUtilizationReporter (pure)
│   └── effective_space.py                   # NEW — the P1 seam + single-range adapter
└── graphql/
    ├── queries/resource_manager.py          # provenance + out-of-space bucket
    └── mutations/profile.py                 # fix the inaccurate unset-vs-null comment

backend/tests/
├── unit/pools/                              # test_intent.py, test_reporting.py  (NEW)
├── component/core/resource_manager/         # test_number_pool_query.py (rewritten), test_number_pool.py
├── component/core/migrations/graph/m079_.../  # NEW — the four behaviours
├── component/core/agnostic_retirement/test_on_node_delete.py   # pool test updated for the new anchor
├── functional/pools/                        # lifecycle + branch suites extended
├── functional/convert_object_type/          # test_convert_number_pool rewritten
├── integration_docker/test_number_pool_migration.py            # NEW (shard marker mandatory)
├── helpers/agnostic_edges.py                # pool_reservation_edges re-anchored
└── query_benchmark/test_number_pool_allocation.py              # NEW

dev/knowledge/backend/database-schema.md     # document IS_RESERVED (currently absent)
changelog/                                   # 7 towncrier fragments
```

**Structure Decision**: this is an existing backend service; the feature slots into the established
layout. Pure logic goes in `backend/infrahub/pools/` alongside `number.py`, because that package
already owns pool arithmetic and both new modules are consumed from `core/` and `graphql/`. Cypher
stays in `core/query/resource_manager.py` — the repo keeps all pool Cypher in one module and this
slice does not change that. No new top-level package.

---

## Phase 1 — Design

### 1. The three change sets

The order is forced by the dependency graph in `research.md` §3, not chosen for convenience.

#### Change set A — Foundation (merges alone, ahead of the feature work)

Everything that must be true before a user-facing capability can be built, plus the two confirmed
defects the move exposes.

| # | Item | Requirement |
|---|---|---|
| A1 | Re-anchor `IS_RESERVED` to the `Attribute` vertex; rewrite six queries | D1, D2 |
| A2 | Migration `m079` — re-anchor, drop orphans, collapse multi-pool, delete legacy pool `HAS_SOURCE`; three counts | D13, FR-024b, FR-030b |
| A3 | Pool leaves `HAS_SOURCE`; `source` derives from the record | FR-030b, FR-030c, D5 |
| A4 | Port the `-global-` `CASE` into `AttributeRenameQuery` | D14 |
| A5 | Re-target `PoolChangeReserved` for object conversion; branch on pool shape | D8 |
| A6 | Cross-branch liveness as a union | FR-036a, D9 |
| A7 | Document `IS_RESERVED` in `dev/knowledge/backend/database-schema.md` | R7 |
| A8 | Add the `IS_RESERVED` `branch` range index — the only property edge type without one, now on a generic hot read path | E7 |
| A9 | Thread the `Attribute` vertex id through `get_resource` → `reserve` → the ledger; restate idempotency per-attribute | E2 |

**Why it merges alone**: SC-022 asks that every figure a pool reports be identical before and after
the re-anchoring. That is only measurable at a boundary where nothing else has moved the numbers —
before P1's ranges and before this slice's bucket. It is the strongest available evidence the
migration is safe, and it evaporates if the change sets land together. This is a *review and merge*
boundary, not a release boundary: everything ships in the same minor.

A6 is sequenced last inside A because it is written against the post-move edge chain. Writing it
first means writing it twice.

#### Change set B — Attach, detach, re-pool

| # | Item | Requirement |
|---|---|---|
| B1 | Payload-presence flags on `BaseAttribute` (create path) | D3 |
| B2 | `FromPoolIntentResolver` (pure) + unit suite | D4, FR-021/022/024/024a |
| B3 | `Node.handle_pool` becomes an executor driven by the resolver | FR-021, FR-024 |
| B4 | `PoolRecordLedger`: create with `provenance`, match-close-create, new release query | FR-025, FR-026, FR-024b |
| B5 | Lock the currently-tracking pool as well as the named one | D6 |
| B6 | The one new refusal, with both remedies named | FR-024 |

#### Change set C — Reporting

| # | Item | Requirement |
|---|---|---|
| C1 | `PoolUtilizationReporter` (pure) + unit suite | FR-027, FR-028a, D10 |
| C2 | `effective_space` seam + single-range adapter | D11, FR-002a |
| C3 | `NumberUtilizationGetter` reduced to fetch-and-delegate | D10 |
| C4 | GraphQL: `provenance` per in-use row; out-of-space bucket rows carrying value, holder, branch | FR-027a |

### 2. The intent decision table

The whole input contract, as pure logic. Inputs: whether `value` was present in the payload and its
value; whether `from_pool` was present and its value; and the attribute's current tracking state.
Full table with every cell in [`contracts/from-pool-intent.md`](./contracts/from-pool-intent.md).

Shape:

| `value` | `from_pool` | currently tracked by | intent |
|---|---|---|---|
| present, non-null | present, pool P | nothing | **attach** (`provenance=provided`) |
| present, non-null | present, pool P | P, same value | **no_op** |
| present, non-null | present, pool P | P, different value | **attach** (record already on the attribute; nothing to write) |
| present, non-null | present, pool B | A | **re_pool_attach** |
| present, non-null | absent | anything | write the value; ledger untouched |
| present, **null** | present, pool P | anything | **discard_and_allocate** |
| absent | present, pool P | nothing, value is a schema default | **allocate** |
| absent | present, pool P | nothing, value is non-default | **refuse** ← the only refusal |
| absent | present, pool P | P | **no_op** |
| absent | present, pool B | A | **re_pool_allocate** |
| absent/any | present, **null** | P | **detach** |
| absent/any | present, **null** | nothing | **no_op** |

Two properties this table must have, and the unit suite must assert:
- **Exactly one refusal.** The out-of-range refusal earlier drafts carried is deleted (FR-029), and
  the two `source` refusals go with FR-030a.
- **Idempotence.** Re-sending the same `value` + `from_pool` for a number the object already owns is
  a silent no-op, because clients resend every field.

### 3. The ledger

`PoolRecordLedger` owns every write to `IS_RESERVED` for number pools.

- **create**: match-close-create. Closes any live record on the target `Attribute` *before* creating
  its own, which is what makes FR-024b hold by construction rather than by accident. Writes
  `provenance ∈ {allocated, provided}`.
- **release**: ends the single `-global-` record between a pool and an `Attribute`. No identifier
  matching — the anchor is already per-object. This is new; nothing in the codebase has ever closed
  an `IS_RESERVED` edge except `PoolChangeReserved`.
- **no move**: FR-031 is deleted. A value change writes nothing.

`provenance` absent means `allocated`, so the property needs no backfill — it rides the migration.

**Closing semantics**: `to = $at` (time-close), not `status = "deleted"`. Consistent with every
existing global-edge closure in the tree (retirement, `PoolChangeReserved`), and required because a
`status="deleted"` edge is terminal per `dev/knowledge/backend/database-schema.md`, which is wrong
for a record that may be recreated by a later re-attach.

### 4. Cross-branch liveness (FR-036a)

A new predicate built on the shape of
`core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE` — reusing its mechanics, not
calling it, because the existing one answers "is this *field* retained" (node existence +
`HAS_ATTRIBUTE`) while this one answers "which *values* does this attribute hold on any branch"
(node existence + `HAS_ATTRIBUTE` + `HAS_VALUE`, per branch).

Mechanics carried over verbatim: the per-branch window
`(branch @ $at) ∪ (origin @ min(branched_from, $at)) ∪ (-global- @ $at)`; per-branch resolution by
`ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1`; `branch.status <> "DELETING"`;
`count(DISTINCT … node.uuid)` as the duplicate-UUID guard; and an aggregate across branches for the
disjunction.

The error stays one-sided by construction: taking the union can only ever *add* numbers to the taken
set.

### 5. Source derivation (FR-030b)

`NodeListGetAttributeQuery._add_source_to_query` gains an `OPTIONAL MATCH` for the inbound `-global-`
`IS_RESERVED` edge on the already-bound `Attribute` vertex, plus a `CASE` preferring the user's
`HAS_SOURCE` when one resolves active.

Two constraints that decide whether this works:

1. It must return the **pool vertex**, not its uuid. Extraction builds
   `AttributeNodePropertyFromDB(uuid=…, labels=…)` from `result.get_node("source").labels`, and those
   labels are what `graphql/types/interface.py::InfrahubInterface.resolve_type` uses to select the
   concrete GraphQL type. Returning only an id breaks `__kind__` resolution. This is the single most
   likely way to get FR-030b subtly wrong.
2. It stays inside the `_include_source` gate, so reads that ask for no metadata pay nothing.

The existing subquery already matches undirected and unlabelled, and `CoreNumberPool` is already
declared a `LineageSource`, so no contract shape changes — only what populates the slot.

### 6. Interface contracts

| Contract | Kind | Consumer |
|---|---|---|
| [`contracts/graphql-pool-query.md`](./contracts/graphql-pool-query.md) | **Published** (ADR 0010) | SDK, frontend, users |
| [`contracts/from-pool-intent.md`](./contracts/from-pool-intent.md) | Published behaviour, unpublished shape | GraphQL mutation callers |
| [`contracts/effective-space.md`](./contracts/effective-space.md) | Internal, **consumed from P1** | this slice |
| [`contracts/reservation-ledger.md`](./contracts/reservation-ledger.md) | Internal | `Node.handle_pool`, conversion |

### 7. Data model

The record, its three shapes, its lifecycle and the migration's four behaviours are in
[`data-model.md`](./data-model.md).

---

## Testing Strategy

Driven by the coverage audit in `research.md` D15 — which **inverts** the PRD's stated gap.

| Tier | What |
|---|---|
| **Unit** (`tests/unit/pools/`) | `FromPoolIntentResolver`: every cell of the table, both re-pool cells, the single refusal, the idempotent no-op. `PoolUtilizationReporter`: distinct counting with duplicates, in/out-of-space partition, the branch split, an empty effective space. Neither touches a database. |
| **Component** | The ledger (attach, detach, release with duplicates present); a value change writing nothing to the ledger; re-pool A→B leaving A's bucket empty; a **user-set non-pool source** changing nothing the pool reports; the rename and remove sweeps leaving the record `-global-`; the migration's four behaviours with their counts; one test per uncovered lifecycle row. |
| **Component (rewrites)** | The five `TestNumberPoolGetAllocated` source-gate tests are pinned to behaviour FR-030c deletes — rewritten, not kept. `agnostic_retirement/test_on_node_delete.py::…::test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool` asserts the literal edge tuple and calls `pool_reservation_edges`; it breaks on the re-anchoring and is updated in change set A. |
| **Functional** | Extend `functional/pools/test_numberpool_lifecycle.py` and `test_numberpool_branch.py`. Rewrite `test_convert_number_pool` to assert the value the pool **reports**, not that an edge exists. |
| **FR-036a regression** | Promote `artifacts/test_fr036a_repro.py`. Both polarities: non-unique (reproduces today) and unique (starts failing when P1 lands FR-011). Keep the passing case as a regression — a branch-level value change must not free the default branch's value. |
| **Integration (Docker)** | One upgrade-path test. **Module-level `pytestmark = pytest.mark.shard_a|shard_b` is mandatory** with a matching `shard:` entry in `.github/workflows/ci.yml`; `conftest.py` validates the whole collection `tryfirst`, so a missing marker fails CI. |
| **Benchmark** | Allocation **and the utilization read** vs `develop`, before and after A6, varying live branch count. The same per-branch resolution lands in `NumberPoolGetUsed`, which backs utilization — a user-facing query with no lock but a wider fan-out. Requires extending `BenchmarkConfig` or adding a `parametrize` axis plus a generator that creates N branches — nothing does that today. Separately, benchmark the FR-030b source derivation on a metadata read over a kind with **no** pool. No gate; a superlinear curve is a release decision. |
| **E2E** | Deferred with the frontend. See Complexity Tracking. |

**Do not duplicate**: two-branch allocation, branch delete, node delete and allocation over
pre-existing nodes are already covered (research.md D15). Extend those modules.

---

## Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **P1's effective-space calculator does not exist.** `POOL-RANGES-PRD.md` is still an Idea Brief with an open `[NEEDS CLARIFICATION]` on zero-range pools, and there is no `specs/` directory for it. | High | D11: consume through a pinned seam with a single-range adapter. This slice ships behind the interface; the adapter is deleted when P1 lands. Does **not** block change set A. |
| R2 | ~~**P1's FR-030a directly contradicts this slice's FR-030b.**~~ **RESOLVED 2026-09-16 by the PRD owner: P2 wins** — `source` can be cleared on pool-sourced attributes, P1's FR-030a and Decision 2 are superseded. | ~~High~~ Closed | Remaining action is mechanical: amend `POOL-RANGES-PRD.md` (delete FR-030a, Decision 2, and its resolved open question #2) before P1 enters spec-kit. No design impact on this slice — FR-030b/FR-030c were already written this way. |
| R3 | FR-036a's per-branch resolution runs inside `get_resource`'s pool-wide lock, so allocation gains a live-branch-count dependency it does not have today. | Medium | Mandatory benchmark (D12). No numeric gate — SC-017 withdrawn for want of evidence. A superlinear curve or a large constant is a release decision. |
| R4 | The migration deletes reservation data for the first time, and two of its four behaviours are destructive beyond the orphan drop. | Medium | Three reported counts; `validate_migration` post-condition following `m077`; component coverage per behaviour; one Docker upgrade test. Avoid `m066`'s documented partial-commit hazard. |
| R5 | **Published contract (ADR 0010).** Two new output fields are a contract change; FR-030b is one the generated schema will **not** show, because the field and type are unchanged and only its provenance moves. | Medium | Name this slice explicitly in the contract review alongside P1 and P3's attribute-parameter changes, and name FR-030b within it. Regenerate, never hand-edit. |
| R6 | Concurrent re-pool of one attribute into two different pools races: the close touches pool A while the mutation holds only pool B's lock. | Medium | D6: contribute the currently-tracking pool's lock name. Uses a field on a read the update path already performs. |
| R7 | `_add_source_to_query` returning an id rather than the pool vertex silently breaks `__kind__` resolution. | Medium | Called out in design §5; assert the resolved GraphQL kind in a component test, not just the uuid. |
| R8 | `NumberPoolGetAllocated` today applies **no** status or branch predicate to the reservation edge. Harmless while nothing closes one; wrong the moment detach and re-pool do. | Medium | The rewrite adds the predicate. Listed explicitly so it is not lost in "rewrite the query". |
| R9 | The PRD's testing guidance points at the wrong configuration (research.md §0 item 6) and names a merge suite that merges nothing (item 7). Following it literally would produce tests for a gap that is already covered and miss the real one. | Low | Superseded by the audit in D15. |
| R10 | **Migration behaviour ordering** — collapsing multi-pool records before deleting legacy source edges leaves a losing pool's `HAS_SOURCE` winning the read slot forever. | High | Evaluate behaviour 4's predicate against records live at migration start, or run it first. Component test named in `data-model.md` §6. Found by critique (E3). |
| R11 | **`IS_RESERVED` is the only property edge type with no index**, and FR-030b puts it on a read path that runs for every attribute of every kind. | High | A8: add the `branch` range index. Benchmark the source derivation on a kind with **no** pool — that is the blast radius, not the pooled case. Found by critique (E7). |
| R12 | **The migration is irreversible** and nothing said so. | Medium | Stated in spec and `data-model.md`; each destructive behaviour reports a pre-count as well as a post-count. Recourse is a database restore. Found by critique (P7). |
| R13 | ~~The upgrade note is unactionable without the brownfield worklist~~ **CLOSED 2026-09-16 — out of scope by decision.** Operators name the values they want tracked; P1 deletes the scan outright per its unchanged FR-011. | Accepted | The ergonomic cost on the brownfield path is accepted knowingly and recorded in the spec's *Out of Scope*. A migration tool may follow if adoption shows it is needed. Reverses critique X1/P2. |
| R14 | ~~**Stakeholder-owned, unresolved**~~ **CLOSED 2026-09-16.** The PRD owner confirmed P2 supersedes P1 on `source` ownership. | Closed | See R2. Critique E13 is answered. |

---

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **No E2E test in this slice** (Constitution IV requires E2E for user-facing features) | The user-facing surface is a GraphQL contract; the views that consume it (range management, the attach action, the pool detail view) are explicitly out of scope and deferred with the frontend. The E2E scenario **is** specified in spec.md and travels with that work. | Writing a Playwright test against a UI that does not exist is not possible. Writing an API-level "E2E" duplicates the functional suite at higher cost. |
| **Two new pure modules** (Constitution VII: helpers serve ≥2 callers before extraction) | Both replace logic that exists today but is only reachable through a database. `from_pool` changes meaning without changing shape, so the decision table *is* the contract (III) and must be unit-testable; the utilization arithmetic is an invariant (FR-028a) that currently emerges from three lines of set comprehension inside a fetcher. | Leaving them inline keeps a seven-branch decision table and a 100%-bounded arithmetic testable only against Neo4j. That is how the current silent value-discard survived. |
| **A migration that deletes data** (Constitution I: migrations preserve integrity) | The orphan drop removes records whose object no longer exists — dead rows the standing comment in `core/query/resource_manager.py` has flagged for years. The multi-pool collapse and legacy `HAS_SOURCE` deletion are required to make FR-024b and FR-030b hold for pre-upgrade data. | Leaving them: orphans keep leaking; multiple live records make the pool report numbers another pool handed out; legacy source edges win the read slot forever, so the derivation never fires for existing data. |

---

## Progress

- [x] Phase 0 — research complete (`research.md`, decisions D1–D15)
- [x] Phase 1 — design complete (`data-model.md`, `contracts/`, `quickstart.md`)
- [x] Constitution Check — pre-design
- [x] Constitution Check — post-design (no new violations; three gated conditions carried as tasks)
- [x] Phase 3 — dual-lens critique ([critiques/critique-20260916.md](./critiques/critique-20260916.md));
      6 must-address findings applied (E2, E3, E7, P7, P2/X1, P5); E13 escalated as an open
      stakeholder question
- [ ] Phase 2 — `tasks.md` (`/speckit-tasks`)
