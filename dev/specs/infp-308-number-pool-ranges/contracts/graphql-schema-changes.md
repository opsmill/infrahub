# Contract: GraphQL / Schema Surface Changes (P1)

This is the externally-visible contract for the P1 slice. It is subject to the published-schema-contract review (one review covering `ranges`, nullable scalars, and — coordinated but out of scope here — the P3 `allocation_scope` parameter). Generated files are regenerated from the schema, not hand-edited: `schema/schema.graphql`, `schema/openapi.json`, `backend/infrahub/core/protocols.py`, frontend generated types.

## New kind: `CoreNumberPoolRange`

Exposed like any core node. Fields:

- `start: Int!` — inclusive lower bound.
- `end: Int!` — inclusive upper bound.
- `allocation_weight: Int` — optional (inherited from `CoreWeightedPoolResource`); absent counts as zero.
- `pool: CoreNumberPool!` — owning pool (cardinality one, mandatory).

Standard node metadata (id, display_label, lineage source, etc.) applies. Branch-agnostic: identical on every branch.

## Modified kind: `CoreNumberPool`

### New relationship

- `ranges: [CoreNumberPoolRange]` — the pool's ranges (cardinality many). Peer relationship to `CoreNumberPoolRange.pool`.

### Changed scalar contract (breaking on read)

- `start_range: Int` — **was non-null, now nullable.** Returns the range start only when the pool holds exactly one range; null when the pool holds zero or more than one range.
- `end_range: Int` — same nullability change.

### Write semantics for `start_range` / `end_range`

| Input | Effect |
|-------|--------|
| `start_range` + `end_range`, pool has ≤1 range | Creates or replaces the pool's single range. |
| `start_range` + `end_range` **and** an explicit `ranges` set | Refused — conflicting spellings. |
| neither, `ranges` provided | Multi-range pool authored directly. |

Mutation `InfrahubNumberPoolMutation` (`backend/infrahub/graphql/mutations/resource_manager.py`):
- Per-range guard `start <= end` (was a single `start_range > end_range` check).
- Intra-pool overlap refused; cross-pool overlap allowed.

## Schema-created pools: `NumberPoolParameters`

`backend/infrahub/core/schema/attribute_parameters.py` (under ADR 0010; SDK type regeneration + one review):

- `start_range: int | None` — default changes `1` → `None`.
- `end_range: int | None` — default changes `sys.maxsize` → `None`.
- `ranges: list[{start:int, end:int, weight:int | None}] | None` — new, optional; schema-declared multi-range pools.
- Validator: refuse both the single shorthand and an explicit `ranges` list.

## Error contract

- Allocation on an exhausted or zero-range pool → the existing pool-exhausted validation error ("pool ... is exhausted"), surfaced from `Node.handle_pool`. No divide-by-zero surfaces to the client.
- Schema change leaving held values outside every range → refused by `AttributeNumberPoolChecker`, identifying offending objects (FR-039).

## Out of contract for P1 (do not add here)

- Provenance field on the held-number record / any provide-attach-detach `from_pool` semantics (P2).
- `allocation_scope` on the pool or in `NumberPoolParameters` (P3) — though its parameter-contract change is reviewed together with the FR-041 default change.
