# Phase 1 Data Model: Custom prefix mask for from-pool allocation

This feature adds one optional field — the requested prefix length — to the existing from-pool selection value. No new entities; existing shapes are extended.

> **As-built deltas**: the `PoolValue.from_pool.prefixlen?` shape below is accurate. But gating is **`CoreIPAddressPool` only** (prefix pools deferred); the control takes only a `placeholder` (no `addressFamily`), and validation is a fixed **1–128** range, not family-aware. In the wire payload, only the **IP-address relationship** case shipped — the IP-prefix and attribute cases are deferred. `prefixlen` is dropped (not serialized) whenever it is absent/`undefined`, via the shared `buildFromPoolPayload` helper.

## Frontend form value: `PoolValue`

`frontend/app/src/shared/components/form/type.ts`

Current:

```typescript
export type PoolValue = {
  from_pool: { id: string; name: string; kind: string };
};
```

Extended (add optional `prefixlen`):

```typescript
export type PoolValue = {
  from_pool: { id: string; name: string; kind: string; prefixlen?: number };
};
```

- `prefixlen` is `undefined` when the user leaves the control empty (→ pool default).
- `AttributeValueFromPool.value` and `RelationshipValueFromPool.value` carry the same `from_pool` shape; the optional `prefixlen` flows through unchanged.

## Pool metadata available to the control

Extend the IP-pool list query result and the field `pool` metadata so the control can render its placeholder/validation:

| Field | Source | Use |
|---|---|---|
| `kind` | existing `pool.kind` (`CoreIPAddressPool` / `CoreIPPrefixPool`) | gate visibility; pick payload semantics |
| `defaultPrefixLength` | new: pool list query `default_prefix_length__value` | placeholder + helper (`empty = pool default (/24)`) |
| `addressFamily` (v4/v6) | derived from default allocated object kind / namespace when available | validation max (32 vs 128) |

When `defaultPrefixLength` / `addressFamily` are unavailable, the control degrades (neutral placeholder, 0–128 validation).

## Validation rules (client-side, FR-007/FR-008)

| Rule | Condition | Message (indicative) |
|---|---|---|
| Integer | value must be a whole number | "Prefix length must be a whole number" |
| Range (family known) | `0 ≤ n ≤ 32` (v4) or `0 ≤ n ≤ 128` (v6) | "Enter a value between 0 and {max}" |
| Range (family unknown) | `0 ≤ n ≤ 128` | "Enter a value between 0 and 128" |
| Empty allowed | empty ⇒ omit `prefixlen` ⇒ pool default | — |

Invalid value ⇒ inline field error + submit blocked. Server-side allocation failures (pool cannot satisfy a valid length) are surfaced from the mutation response and do not pre-block submit (FR-013).

## State transitions (control lifecycle)

```text
no pool selected            → control hidden
pool selected (IP pool)     → control shown, empty (placeholder = pool default)
user types valid length     → PoolValue.from_pool.prefixlen = n
user types invalid length   → inline error, submit blocked
pool changed                → prefixlen reset to undefined, control re-shown empty
pool cleared / manual entry  → control removed, prefixlen discarded
non-IP pool selected        → control never shown
```

## Wire payload (mutation input)

Emitted by `getCreateMutationFromFormData.ts` / `getUpdateMutationFromFormData.ts`:

- Relationship to IP address (works today): `{ <rel>: { from_pool: { id, prefixlen? } } }`
- Relationship to IP prefix (needs backend support): `{ <rel>: { from_pool: { id, prefixlen? } } }`
- IP attribute (`prefix`/`address`, needs backend support): `{ <attr>: { from_pool: { id, prefixlen? } } }`
- Companion `_from_resource_pool` relationship path (when `fromPoolRelationshipName` is set): include `prefixlen` alongside `id` in that input.

`prefixlen` is omitted entirely when the user did not specify a length.
