# Contracts: GraphQL & SDK for IPAddress

Phase 1 output. The external-facing contracts introduced by this feature. Implementation
detail lives in `data-model.md` / `tasks.md`; this file is the interface surface.

## GraphQL

### Attribute query type `IPAddress`

For a schema node with an attribute `address` of `kind: IPAddress`, GraphQL exposes:

```graphql
type IPAddress implements AttributeInterface {
  value: String        # bare address, e.g. "192.0.2.10" / "2001:db8::1"
  version: Int         # 4 or 6
  # standard AttributeInterface metadata: is_default, is_from_profile,
  # updated_at, is_protected, is_visible, source, owner, ...
}
```

- No `prefixlen`, `netmask`, `hostmask`, `with_netmask`, `with_hostmask` fields (those are
  IPHost-only). This is the contract difference that makes the kind "bare".

### Create / update inputs

Reuses the existing text attribute inputs (as IPHost does):

```graphql
input TextAttributeCreate { value: String, ... }
input TextAttributeUpdate { value: String, ... }
```

- Submitting a value containing `/` (e.g. `"10.0.0.1/24"`, `"10.0.0.1/32"`) MUST fail
  validation with an error identifying the value as not a valid `IPAddress`.

### Filters

Auto-generated for the attribute `address`:

```graphql
address__value: String
address__values: [String]
address__isnull: Boolean
# plus standard metadata filters (source/owner ids, protected flags)
```

- Equality/`values` filtering MUST return exactly the instances whose bare address matches.

### HFID / display label

- When `address` participates in a node's `human_friendly_id` or display label, the value
  used is the bare address. An HFID returned by a query MUST be usable directly as lookup
  input (no mask to add/strip) — the round-trip failure of IPHost (infrahub#8896) MUST NOT
  occur for IPAddress.

## Python SDK

### Typed attribute classes

```python
class IPAddress(Attribute):
    value: ipaddress.IPv4Address | ipaddress.IPv6Address

class IPAddressOptional(Attribute):
    value: ipaddress.IPv4Address | ipaddress.IPv6Address | None
```

### Behaviour

- `client.get(...)` on a node with an `IPAddress` attribute returns `attr.value` as a bare
  `IPv4Address`/`IPv6Address` object (no prefix). `str(attr.value)` == the GraphQL `value`
  == the UI display.
- Writing accepts a bare address (string or address object) and serialises to a bare-address
  string; a value with a prefix is rejected by the backend.
- `AttributeKind.IPADDRESS == "IPAddress"`; `ATTRIBUTE_KIND_MAP["IPAddress"] == "IPAddress"`.

### Generated protocols

- `infrahub_sdk/protocols.py` (generated) imports `IPAddress`/`IPAddressOptional`; a schema
  attribute of `kind: IPAddress` is typed as `IPAddress` (or `IPAddressOptional` when
  optional) in generated protocol stubs.

## Backward-compatibility contract

- `IPHost` and `IPNetwork` GraphQL types, inputs, filters, HFID behaviour, and SDK value
  types are unchanged. No existing query, mutation, or SDK call changes shape.
