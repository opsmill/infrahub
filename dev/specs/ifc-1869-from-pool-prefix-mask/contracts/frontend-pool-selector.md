# Contract: shared prefix-length control across both from-pool surfaces

> **As-built deltas** (the contract below reflects the original design): the component shipped with props `value / placeholder / invalid / onChange` (no `poolKind` / `defaultPrefixLength` / `addressFamily`). It renders **inside `PoolSelect`**, gated to `CoreIPAddressPool` **only** (prefix pools deferred) — so the three host fields render `PoolSelect` unchanged. The default is passed as `placeholder`; validation is a fixed **1–128** range (not address-family-aware). The list query fetches `default_prefix_length` for address pools only. Mutation emission drops an absent/`undefined` `prefixlen` via a shared `buildFromPoolPayload` helper.

## Component: `PoolPrefixLengthInput` (new, `shared/components/form/pool-prefix-length-input.tsx`)

The IP pool picker is `PoolSelect` (`inputs/pool-select.tsx`), rendered by three host fields: `input.field.tsx` (the IP `prefix`/`address` attribute), `regular-relationship.field.tsx`, and `relationship-hierarchical.field.tsx`. `PoolSelector` (`form/pool-selector.tsx`) is the number-pool selector and is out of scope. The control is a single shared component rendered beside `PoolSelect` (under the "allocated by pool" state) in each of the three host fields. It reveals the prefix-length input once a pool is selected and the pool is an IP pool. The value lives in the existing form field via `onChange(PoolValue)` — no new state owner.

Props:

| Prop | Type | Meaning |
|---|---|---|
| `value` | `FormFieldValue` | current field value; pool selection + current `prefixlen` read from here |
| `onChange` | `(PoolValue \| null) => void` | emits `from_pool` with/without `prefixlen` |
| `poolKind` | `string` | gate: render only for `CoreIPAddressPool` / `CoreIPPrefixPool` |
| `defaultPrefixLength` | `number \| undefined` | placeholder/helper hint |
| `addressFamily` | `"v4" \| "v6" \| undefined` | validation max (32/128); undefined ⇒ 0–128 |

Behaviour contract:

1. Control hidden unless a pool is selected AND `poolKind` ∈ {IP address pool, IP prefix pool}.
2. Leading `/` adornment; numeric entry; labelled "Prefix length · optional".
3. Empty ⇒ `onChange` emits `from_pool` without `prefixlen`.
4. Valid integer in range ⇒ `onChange` emits `from_pool.prefixlen = n`.
5. Invalid ⇒ inline error via the form's field-error mechanism; submit blocked.
6. Changing the pool resets `prefixlen`; clearing the pool removes the control.
7. `data-testid="pool-prefix-length-input"` for E2E.

## Pool list query (`generate-relationship-list.query.ts`)

For IP-pool kinds, additionally request `default_prefix_length { value }` so `defaultPrefixLength` can be passed down. Additive; no change for non-IP pools.

## Mutation builders

`getCreateMutationFromFormData.ts` / `getUpdateMutationFromFormData.ts`: when emitting a `from_pool` input (direct or via `fromPoolRelationshipName`), include `prefixlen` iff present on `PoolValue.from_pool`.
