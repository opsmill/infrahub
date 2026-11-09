# Contract: inline `from_pool` allocation accepts `prefixlen`

Scope: the inline `from_pool` input used during normal node create/update mutations (not the dedicated `*PoolGetResource` mutations).

> **As-built status**: Only the **address pool (relationship)** contract below shipped — it required no change. The **prefix pool** and **attribute** sections are **DEFERRED** (the prefix-pool input uses `size`, not `prefixlen`; no GraphQL change was made). One behavior was **added** beyond this contract: `CoreIPAddressPool.get_resource` now rejects an explicit `prefixlen` that conflicts with an existing reservation (FR-014) — an absent or matching length stays idempotent.

## Address pool (relationship) — EXISTS TODAY, no change

`IPAddressPoolInput` already exposes `prefixlen`; `relationship/model.py` forwards it to `IPAddressPool.get_resource(prefixlen=…)`.

```graphql
mutation {
  InfraDeviceCreate(data: {
    name: { value: "edge-1" }
    primary_address: { from_pool: { id: "<pool-id>", prefixlen: 32 } }
  }) { ok object { id } }
}
```

Expected: the allocated address uses `/32`. Omitting `prefixlen` uses the pool default. (Behaviour to be covered by a new backend test.)

## Prefix pool (relationship) — REQUIRES BACKEND CHANGE (Ask First)

Add `prefixlen: Int` to `IPPrefixPoolInput` so it threads to `IPPrefixPool.get_resource(prefixlen=…)`. (`size` is left untouched / out of scope.)

```graphql
mutation {
  IpamIPPrefixCreate(data: {
    # ... allocate a child prefix from a prefix pool relationship ...
    from_pool: { id: "<prefix-pool-id>", prefixlen: 28 }
  }) { ok object { id } }
}
```

Expected after change: allocates a `/28`. Omitting `prefixlen` uses pool default.

## IP attribute (`prefix` / `address`) — REQUIRES BACKEND CHANGE (Ask First)

The IPAM-native creation forms allocate the `prefix`/`address` attribute from a pool. The attribute-side `from_pool` processing must forward a caller `prefixlen` into the IP pool `get_resource`, and the attribute's inline pool input must expose `prefixlen`.

```graphql
mutation {
  IpamIPPrefixCreate(data: {
    prefix: { from_pool: { id: "<prefix-pool-id>", prefixlen: 28 } }
  }) { ok object { id } }
}
```

Expected after change: allocates a `/28`. Exact field/resolver path to be confirmed in task T001.

## Invariants

- `prefixlen` omitted ⇒ pool default (no behaviour change vs today).
- A `prefixlen` valid for the family but unsatisfiable by the pool ⇒ allocation error returned by the mutation (surfaced inline by the UI); no silent fallback to default.
- Authn/authz, branch/temporal handling unchanged — allocation already runs inside the existing mutation transaction.
