# Phase 0 Research: Custom prefix mask for from-pool allocation

> **As-built outcome of these decisions**: R1's audit held up (the `size`-vs-`prefixlen` gap is real). At implementation time we **deferred** the prefix-relationship and attribute backend fixes rather than doing them — scope narrowed to the IP-address relationship path, which needed no backend change. R4 (family-aware validation) was **not** implemented; a fixed 1–128 range is used. R6's plan to render "beside `PoolSelect` in three host fields" became "**inside `PoolSelect`**" (one render, all three hosts inherit it). One thing added beyond this research: the FR-014 conflict guard in `CoreIPAddressPool.get_resource`.

## R1. Does the inline `from_pool` allocation honor a caller-supplied prefix length?

**Mechanism** (`backend/infrahub/core/relationship/model.py:572-604`): when a relationship has `from_pool` and no peer id, the code deep-copies `from_pool`, deletes `id`, and unpacks the remainder as kwargs into `pool.get_resource(db=..., branch=..., at=..., user_id=..., **data_from_pool)`. So any extra key present on the inline `from_pool` input is forwarded directly to the pool's `get_resource`.

**GraphQL inline input types** (`backend/infrahub/graphql/types/attribute.py:14-55`):

- `RelatedNodeInput.from_pool` → `GenericPoolInput` (`id`, `identifier`, `data`) — **no length field**.
- `RelatedIPAddressNodeInput.from_pool` → `IPAddressPoolInput` (adds **`prefixlen: Int`**).
- `RelatedIPPrefixNodeInput.from_pool` → `IPPrefixPoolInput` (adds **`size: Int`**, `member_type`, `prefix_type`).

**Pool `get_resource` signatures**:

- `ip_address_pool.py:get_resource(..., prefixlen: int | None = None, ...)` → `prefixlen = prefixlen or data.get("prefixlen") or self.default_prefix_length.value`.
- `ip_prefix_pool.py:get_resource(..., prefixlen: int | None = None, member_type=..., prefix_type=..., ...)` → resolves `prefixlen` the same way. **It has no `size` parameter.**

### Decision (per entry point)

| Entry point | Status today | Action |
|---|---|---|
| **IP address via relationship** (e.g. *Primary IP Address*) | `IPAddressPoolInput.prefixlen` → `get_resource(prefixlen=…)`. **Works end-to-end.** | Frontend-only: send `prefixlen`. |
| **IP prefix via relationship** | Input exposes `size`, but `get_resource` accepts `prefixlen`, not `size`. Passing `size` would raise `TypeError` (it is never sent today, so it is latent/dead). **Broken for length.** | Backend fix: accept `prefixlen` on `IPPrefixPoolInput` (add field; `size` mapping is out of scope) so it threads to `get_resource`. |
| **IP prefix / IP address via attribute** (IPAM-native *Prefix \*/Address* creation forms) | The attribute `from_pool` processing path extracts only the pool `id`; it does not forward extra allocation kwargs the way relationships do. **Does not honor length.** | Backend fix: thread a caller `prefixlen` from the attribute `from_pool` into the IP pool `get_resource`, and expose `prefixlen` on the attribute's inline pool input. |

**Rationale**: The relationship IP-address path proves the UX cheaply with zero backend change — ideal first slice for preview-driven validation. The prefix and attribute paths need small, well-scoped backend changes. **GraphQL input-type changes require maintainer sign-off per the constitution ("Ask First: GraphQL schema modifications").**

**Alternatives considered**: (a) Route everything through the dedicated `IPPrefixPoolGetResource`/`IPAddressPoolGetResource` mutations (which already accept `prefix_length`) — rejected: the object forms allocate inline during node create/update, not via the standalone resource mutations; reworking that is a much larger change. (b) Reuse the existing `size` field for prefix — rejected: `size` is not wired into `get_resource` and its intended semantics are unclear; adding an explicit `prefixlen` is clearer and lower-risk.

**Open verification (first implementation task, T001)**: confirm the exact attribute-side `from_pool` processing path for IP `prefix`/`address` attributes and the precise minimal edit, and confirm `IPPrefixPoolInput` has no consumer of `size` before adding `prefixlen`.

## R2. Field naming sent by the frontend

**Decision**: the frontend sends **`prefixlen`** (matching the backend inline input `IPAddressPoolInput.prefixlen` and the `get_resource` kwarg), not `prefix_length`. The spec's user-facing label remains "Prefix length"; `prefixlen` is the wire/payload key only.

**Rationale**: aligns with the path that already works (address relationship) and with `get_resource`'s kwarg, minimising surface area. The dedicated resource mutations use `prefix_length`, but those are not on the inline path this feature uses.

## R3. Communicating the pool's default prefix length (placeholder/helper)

**Finding**: the pool list query (`entities/nodes/relationships/api/generate-relationship-list.query.ts`) requests only `id`, `hfid`, `display_label`, `__typename`. The pool's `default_prefix_length` and address family are **not** currently fetched at picker time.

**Decision**: extend the pool list query (for IP-pool kinds) to also request `default_prefix_length` (and the default object kind/namespace if needed to infer v4/v6). Use it for the placeholder and helper text. If unavailable, degrade gracefully to a neutral placeholder and `empty = pool default` (per spec FR-005).

**Rationale**: small additive query change, keeps the backend authoritative for the default (no client-side guessing of the default value).

## R4. Address family for validation range (v4 0–32 vs v6 0–128)

**Decision**: derive the family from the pool's default allocated object kind / namespace when available; otherwise validate the widest range (0–128) and let the backend reject impossible values (spec FR-007, edge case). Do not hardcode v4.

## R5. Input primitive to reuse

**Candidates**: `Input` (`shared/components/ui/input.tsx`); `Row` layout container; `Autocomplete` already demonstrates a `suffix`-adornment pattern. **Decision**: reuse `Input` (`type="number"`) inside a `Row` with a leading `/` adornment span; do not build a new primitive (constitution: Reuse Before Reinvent, YAGNI). If a `/`-adorned numeric input is needed in 2+ places later, extract then.

## R6. Where the control is rendered

**Correction (verified in code):** the IP pool picker is `PoolSelect` (`shared/components/inputs/pool-select.tsx`, trigger `select-open-pool-option-button`), gated to IP pools via its `filterQuery`. `PoolSelector` (`shared/components/form/pool-selector.tsx`, `pools: NumberPool[]`, trigger `number-pool-button`) is the **number-pool** selector and is unrelated to this feature. `PoolSelect` is rendered by three host fields: `input.field.tsx` (the IP `prefix`/`address` attribute), `regular-relationship.field.tsx`, and `relationship-hierarchical.field.tsx` — each computing `selectedPoolId` and laying out a `Row` of input + `PoolSelect`.

**Decision**: implement the revealed control as a shared `PoolPrefixLengthInput` and render it beside `PoolSelect` (under the "allocated by pool" state) in each of those three host fields, gated on `poolKind ∈ {CoreIPAddressPool, CoreIPPrefixPool}` and on a pool being selected. This satisfies FR-011 (every IP entry point) and Single State Owner (value lives in the `useForm` field via the existing `onChange`/`PoolValue`). `PoolSelector`/`number.field.tsx` are intentionally untouched (FR-003 excludes number pools).

**Kind constants** (already defined): `IP_ADDRESS_POOL = "CoreIPAddressPool"`, `IP_PREFIX_POOL = "CoreIPPrefixPool"` (`entities/resource-manager/constants.ts`); generics `BuiltinIPAddress`/`BuiltinIPPrefix` (`entities/ipam/constants.ts`).
