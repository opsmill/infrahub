# Research: Number Pools — Several Weighted Ranges per Pool (P1)

All code citations are `module::symbol` (never line numbers). Grounded against `develop` as of 2026-09-08.

## D1 — New core kind for a range

**Decision**: Add a new core kind `CoreNumberPoolRange` with attributes `start` (Number, required), `end` (Number, required), inheriting `CoreWeightedPoolResource` (which contributes `allocation_weight`, Number, optional). It belongs to exactly one pool via a mandatory relationship. Declared in `backend/infrahub/core/schema/definitions/core/resource_pool.py`, registered in `.../core/__init__.py`, protocol added to `backend/infrahub/core/protocols.py`.

**Rationale**: The PRD calls for several weighted ranges per pool; a first-class kind lets each range carry its own weight and be edited independently. `CoreWeightedPoolResource` already models `allocation_weight` and is the generic the IP pools sort by (`ip_prefix_pool.py`, `ip_address_pool.py` sort `resources` by `allocation_weight.value or 0`), so reuse satisfies the constitution's "serve two callers before extraction" rule (IP pools + ranges).

**Alternatives considered**: A JSON list attribute of `{start,end,weight}` on `CoreNumberPool` — rejected: not independently addressable, no per-range metadata/lineage, and it would not reuse the weighted-resource sorting the IP pools already use.

## D2 — Branch behaviour of the range kind (open point resolved)

**Decision**: `CoreNumberPoolRange` is `branch=AGNOSTIC`, matching `CoreNumberPool` (which is `AGNOSTIC` in `resource_pool.py`). The inherited generic `CoreWeightedPoolResource` is currently `branch=AWARE`. The concrete node's `branch` setting governs the node's rows; the generic contributes only the `allocation_weight` attribute definition.

**Rationale**: PRD principle 3 — the ledger and pool structure are branch-agnostic; a range must be identical on every branch, like the pool it belongs to. `allocation_weight` as an agnostic attribute is consistent with the pool's other agnostic attributes.

**Verification task (implementation)**: Confirm that an `AGNOSTIC` node inheriting an `AWARE` generic passes schema validation and that `allocation_weight` materialises as agnostic. If schema validation forbids the mix, the minimal fix is to make `CoreWeightedPoolResource` branch-neutral for inheritance rather than to store ranges branch-aware. This is the one genuinely novel schema combination in the slice (first core kind to inherit the generic) and must be proven with a schema-load/component test before the rest is built.

## D3 — Pool → ranges relationship

**Decision**: Add a `ranges` relationship on `CoreNumberPool` (cardinality many, to `CoreNumberPoolRange`) and a mandatory `pool` back-relationship (cardinality one) on `CoreNumberPoolRange`. There is **no** existing schema relationship on `CoreNumberPool` today (the node↔value link is the runtime `IS_RESERVED`/`HAS_SOURCE` edges, not schema), so this is a new relationship, not a modification.

**Rationale**: Ranges are owned data of a pool; a schema relationship gives cascade, GraphQL exposure, and lineage for free. The mandatory `pool` side enforces "belongs to exactly one pool" (FR-001).

## D4 — `start_range` / `end_range` become optional shorthand

**Decision**: In `resource_pool.py`, change `start_range` and `end_range` from `required` to `optional=True`. On **write**, when supplied they create-or-replace a single range (the pool's only range). On **read**, they return a value only when the pool holds exactly one range, else null. Keep the fields (do **not** remove them).

**Rationale**: FR-005a / FR-042 — preserve the simple single-span authoring path and backward compatibility while the ranges relationship carries the general case. Nullable-on-read is the contract change flagged for the published-schema review.

**Alternatives considered**: Removing the scalars (as the source PRD's early text suggested) — rejected: breaks every existing pool definition and the GraphQL contract for no gain; the shorthand is genuinely useful for the common one-range pool.

## D5 — Single effective-space calculator

**Decision**: Introduce one pure function/class computing the pool's **effective space** = (union of ranges) ∩ `[min_value, max_value]` − intersecting excluded values. Home it in `backend/infrahub/pools/number.py` (already the pool-arithmetic module that owns `total_pool_size` and the `utilization` properties). It must expose: total size, per-range effective bounds (for gap/order), fullness, and be safe when the result is empty (no division). Replace the three disagreeing computations:
- the effective-range maths in `backend/infrahub/core/node/resource_manager/number_pool.py::CoreNumberPool.get_next` (`effective_start`/`effective_end`),
- the `skip_excluded` closure in the same method,
- `total_pool_size` in `backend/infrahub/pools/number.py`.

**Rationale**: FR-006/FR-007/FR-008 and SC-003/SC-004 require one consistent answer across size, utilization, allocation order, and fullness, and eliminate the `ZeroDivisionError` in the `utilization` properties (`pools/number.py` divides by `total_pool_size`) when exclusions fall entirely outside the span. Centralising the arithmetic is the constitution's Simplicity principle applied to three copies that already drift.

**Alternatives considered**: Fix each of the three sites in place — rejected: leaves three implementations to keep in sync, the exact defect being removed.

## D6 — Read queries take a range set

**Decision**: Change `NumberPoolGetFree`, `NumberPoolGetUsed`, `NumberPoolGetAllocated`, `NumberPoolGetReserved` in `backend/infrahub/core/query/resource_manager.py` to accept a **set of ranges** instead of a single `$start_range`/`$end_range`. Gap detection stays in Cypher (the `NumberPoolGetFree` gap-finding `UNWIND range(...)` block is generalised to iterate the ordered union of ranges). Parameters become a list of `{start,end,weight}`; the "no reservations" base case returns the lowest value of the lowest range.

**Rationale**: The queries currently filter `av.value >= $start_range AND <= $end_range`; multiple ranges require an `OR` over intervals (or an `ANY` over a parameter list) and the gap walk must resume at the next range's start after a range is exhausted (SC-001 fall-through). Keeping gap detection in the database preserves the current performance shape.

**Alternatives considered**: Pull all used values into Python and compute the next free number there — rejected: unbounded memory on large pools, violates Query Performance principle.

## D7 — FR-011: update, do not delete, the taken-value scan (P1/P2 decoupling)

**Decision**: Keep `NumberPoolGetTaken` (`resource_manager.py`) and the `get_next` hook `if attribute.unique: excluded_values |= await self.get_taken(...)` (`number_pool.py`), and **update** the query to range-set semantics so it keeps skipping hand-set values on a unique attribute. Do **not** delete it in P1. The deletion (the deliberate #10180 revert, commit `40167728e`, closes #10179) moves to P2 where attachment replaces it.

**Rationale**: The maintainer's direction during specification: updating rather than deleting the scan makes P1 self-consistent and independently releasable, removing the P1↔P2 shipping coupling the source PRD assumed. Deleting it in P1 would reintroduce #10179 (allocation stalling on a hand-set value the uniqueness constraint rejects) until P2 lands.

## D8 — Schema-created pools declare ranges; parameter defaults become "unset"

**Decision**: In `backend/infrahub/core/schema/attribute_parameters.py::NumberPoolParameters`, change `start_range` default from `1` and `end_range` default from `sys.maxsize` to `None`, add a validator that refuses supplying both the single shorthand and an explicit ranges list, and extend the parameters to carry an optional list of ranges (`{start,end,weight}`) for schema-declared multi-range pools. Update `get_pool_size()` to defer to the effective-space calculator.

**Rationale**: FR-041 — with `1`/`sys.maxsize` defaults, "both spellings set" is undetectable. FR-039 requires schema-created pools to support the range set. Note the coupling flagged in the spec: this is one `NumberPoolParameters` contract change under ADR 0010; P3's `allocation_scope` parameter (out of scope here) rides the same change and its review.

## D9 — Validator against the attribute domain over a range set

**Decision**: Update `backend/infrahub/core/validators/attribute/number_pool.py::AttributeNumberPoolChecker` and its `AttributeNumberPoolUpdateValidatorQuery` so a schema change is refused when an object's held value falls outside **every** declared range (was: outside the single `[start_range, end_range]`), identifying the offending objects.

**Rationale**: FR-039 — schema-created pool ranges are validated against the attribute's domain; the semantics are the existing checker generalised from one span to a range set.

## D10 — Data migration

**Decision**: Add a graph data migration `m0NN_number_pool_single_range` (next free number after `m077`), modelled on `backend/infrahub/core/migrations/graph/m066_consolidate_duplicate_number_pools.py` (`ArbitraryMigration`): for every existing `CoreNumberPool`, create one `CoreNumberPoolRange` covering its current `[start_range, end_range]` with `allocation_weight` absent (counts as zero), linked via the new `ranges` relationship. Existing `IS_RESERVED`/`HAS_SOURCE` edges are untouched. Register in `backend/infrahub/core/migrations/graph/__init__.py` with `Migration0NN` and `minimum_version`.

**Rationale**: FR-005/FR-042 and SC-005 — every existing pool keeps allocating with no operator action, now as a single-range pool. `m066` is the established pattern for pool-data migrations (it already manipulates `IS_RESERVED`/`HAS_SOURCE`).

## D11 — Zero-ranges and empty effective space

**Decision**: A pool with zero ranges is legal. The effective-space calculator returns size 0; `utilization` reports 0 of 0 as 0% (guarded, no division by zero); allocation raises `PoolExhaustedError` (`backend/infrahub/exceptions.py`, caught in `node/__init__.py::Node.handle_pool`) rather than dividing by zero. A range that clamps to empty against the attribute domain counts as exhausted for fullness.

**Rationale**: PRD "Open questions → Zero ranges" default; FR-007; SC-006.

## D12 — Mutation-side range guard

**Decision**: The GraphQL mutation guard `start_range.value > end_range.value` (`backend/infrahub/graphql/mutations/resource_manager.py::InfrahubNumberPoolMutation`) generalises to validate each range (`start <= end`) and refuse intra-pool overlaps (FR-004). Cross-pool overlap is allowed (no pool-side arbitration).

**Rationale**: FR-004 — intra-pool non-overlap only; a value collision between two pools is refused only by a uniqueness constraint.

## Testing strategy (Constitution IV)

- **Component** (`backend/tests/component/core/resource_manager/test_number_pool.py`, `test_number_pool_query.py`): fall-through across gaps and weights (SC-001), range removal retaining held numbers (SC-002/FR-002a), effective-space size/utilization incl. min/max and intersecting exclusions (SC-003), the former divide-by-zero case (SC-004), zero-ranges full (SC-006), shorthand round-trip (SC-007), FR-011 taken-value skip still working over the range set.
- **Component** (`.../constraint_validators/test_attribute_numberpool_constraints.py`): FR-039 validator over a range set.
- **Migration** (`.../migrations/graph/test_0NN_number_pool_single_range.py`, modelled on `test_066_...`): every existing pool → one covering range, still allocatable (SC-005).
- **Functional** (`backend/tests/functional/pools/`): branch-agnostic range edits take effect on every branch.
- Reuse fixtures in `backend/tests/helpers/number_pool.py`.

## Documentation & generated files

- Regenerate protocols (`uv run invoke backend.generate`), GraphQL schema (`schema.generate-graphqlschema`), OpenAPI (`schema.generate-jsonschema`), reference docs (`docs.generate`); CI's `validate-generated-documentation` fails on drift.
- Changelog fragments (P1 portion): utilization sensitivity to `min_value`/`max_value` and intersecting exclusions; `start_range`/`end_range` reading null on multi-range pools. (The #10180-revert changelog belongs to P2 under D7.)
- Update `dev/knowledge/backend/` for the ranges model and effective-space calculator.
