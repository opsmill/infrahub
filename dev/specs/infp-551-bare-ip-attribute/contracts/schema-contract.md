# Contract: Schema surface

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

One new optional field on the `IPHost` variant of attribute parameters. No new endpoints, mutations,
arguments, or GraphQL types.

## Author-facing schema contract

A schema author declares a bare-address attribute like this:

```yaml
nodes:
  - name: DnsRecord
    namespace: Testing
    attributes:
      - name: dns_target
        kind: IPHost
        parameters:
          allow_prefix: false
```

Omitting `parameters`, or omitting `allow_prefix`, yields today's behaviour:

```yaml
      - name: mgmt_ip
        kind: IPHost          # allow_prefix defaults to true — unchanged behaviour
```

### Field definition

| Property | Value |
|----------|-------|
| Path | `attributes[].parameters.allow_prefix` |
| Type | `boolean` |
| Default | `true` |
| Valid kinds | `IPHost` **only** |
| Mutability | Immutable once the attribute exists |
| Visibility | `WRITE` (inherited from the `parameters` field) |

### Kind-scoping cases

| Input | Result |
|-------|--------|
| `allow_prefix` on a `Text`, `TextArea`, `List`, `Number`, or `NumberPool` attribute | **Accepted and silently dropped** — the attribute keeps its own kind's parameters, without the flag |
| `allow_prefix` on any other kind (base `AttributeParameters`) | **Accepted and silently dropped**, same mechanism |
| An `IPHostAttributeParameters` instance attached to a non-`IPHost` kind | Schema load fails — `"IPHostAttributeParameters can't be used as parameters for {kind}"` |
| A schema update adding, removing, or flipping `allow_prefix` on an existing attribute | Update fails — unsupported-change error naming `parameters.allow_prefix` |

The silent drop is **pre-existing behaviour shared by every attribute parameter**, not something this
feature introduces: a `parameters` mapping is coerced to the parameters model of the attribute's own
kind, and that coercion filters out keys the target model does not declare *before* Pydantic's
`extra="forbid"` can see them. `regex` on a `Number` attribute behaves identically. So the flag is
unreachable on other kinds — it has no effect there — but a schema declaring it there still loads.

Only the reverse direction genuinely rejects: an `IPHostAttributeParameters` **instance** (as opposed
to a plain mapping) attached to a kind whose registered parameters class is something else.

## Value contract

### Accepted and rejected input

For an attribute with `allow_prefix: false`:

| Input | Result | Stored `value` |
|-------|--------|----------------|
| `10.0.0.1` | accepted | `10.0.0.1` |
| `10.0.0.1/32` | accepted, mask normalised away | `10.0.0.1` |
| `2001:db8::1` | accepted | `2001:db8::1` |
| `2001:db8::1/128` | accepted, mask normalised away | `2001:db8::1` |
| `10.0.0.1/24` | **rejected** — error names the attribute | — |
| `10.0.0.1/31` | **rejected** | — |
| `10.0.0.1/0` | **rejected** | — |
| `2001:db8::1/64` | **rejected** | — |
| `not-an-ip` | **rejected** — existing `is not a valid IPHost` error | — |
| `null` (optional attribute) | accepted, no prefix logic applied | `null` |

For an attribute with `allow_prefix: true` (or absent), every row above behaves exactly as it does
today, including `10.0.0.1` → stored `10.0.0.1/32` and `10.0.0.1/24` → stored `10.0.0.1/24`.

### Declared default values

An attribute's `default_value` goes through the same rules, but the outcome is visible in the **schema**
rather than only in node data. For an attribute with `allow_prefix: false`:

| Declared `default_value` | Result | Recorded in the schema as |
|--------------------------|--------|---------------------------|
| `10.0.0.1` | accepted | `10.0.0.1` |
| `10.0.0.1/32` | accepted, mask normalised away | `10.0.0.1` |
| `2001:db8::1/128` | accepted, mask normalised away | `2001:db8::1` |
| `10.0.0.1/24` | **schema load fails** — `default value ...` error naming the attribute | — |
| `2001:db8::1/64` | **schema load fails** | — |

Normalising rather than rejecting a `/32` default keeps the schema self-consistent: the default the
schema advertises is the value a node created without an explicit value actually receives. Rejection of
a non-host prefix happens at schema-load time, not at first node creation, because
`SchemaBranch.validate_default_values()` routes defaults through the same format validator.

For an unflagged attribute every row above behaves as today, including `10.0.0.1` recorded verbatim.

### IPv6 canonical form

The stored value is `str(ip_interface(value).ip)` — the `ipaddress` module's canonical RFC 5952
rendering: compressed, lowercase, longest zero-run collapsed. This is byte-identical to today's
undeclared output minus the mask. IPv4-mapped addresses keep the same canonical rendering.

## GraphQL contract

`IPHostType` (`backend/infrahub/graphql/types/attribute.py:115-128`) is **unchanged** — no fields
added, removed, or retyped:

```graphql
type IPHost implements AttributeInterface {
  value: String
  ip: String
  hostmask: String
  netmask: String
  prefixlen: Int
  version: Int
  with_hostmask: String
  with_netmask: String
  # ... AttributeInterface members
}
```

What changes is the **content** of `value` for flagged attributes, because it resolves from the stored
value. Every derived field keeps returning its derived answer:

```graphql
# For dns_target declared allow_prefix: false, entered as "10.0.0.1/32"
{
  TestingDnsRecord {
    edges {
      node {
        dns_target {
          value      # "10.0.0.1"      <- bare
          ip         # "10.0.0.1"
          prefixlen  # 32              <- derived, still truthful
          netmask    # "255.255.255.255"
          version    # 4
        }
        display_label      # "10.0.0.1"  <- no mask
        hfid               # ["10.0.0.1"] <- no mask, usable verbatim as lookup input
      }
    }
  }
}
```

The schema-parameters contract gains the field, so a schema query exposes it:

```graphql
{
  # via the schema API
  attributes { name kind parameters }   # parameters includes allow_prefix for IPHost
}
```

## Filter contract

**Unchanged.** All existing `IPHost` filters remain available on flagged attributes:

| Filter | Behaviour on a flagged attribute |
|--------|----------------------------------|
| `__value` | Matches the stored bare form. `dns_target__value: "10.0.0.1"` matches; `"10.0.0.1/32"` does not. |
| `__prefixlen` | Still resolves, returning the derived host length (`32`/`128`). Coherent but arguably surprising — accepted, documented. |
| `__binary_address` | Unchanged |
| `__isnull` | Unchanged |
| IPAM prefix-containment queries | Unchanged — flagged values are still returned, because `prefixlen` stays populated |

## Uniqueness contract

Uniqueness compares only the stored `value`
(`backend/infrahub/core/validators/uniqueness/query/validation.py:22`). On a flagged attribute with
`unique: true` or a uniqueness constraint:

```text
node A: dns_target = "10.0.0.1"     -> stored "10.0.0.1"
node B: dns_target = "10.0.0.1/32"  -> stored "10.0.0.1"  -> VIOLATION
```

On an unflagged attribute the same two inputs both store `10.0.0.1/32` and also collide — unchanged
from today.

## Error contract

No new error types. Both failure modes reuse existing machinery:

| Failure | Error | Shape |
|---------|-------|-------|
| Value carries a non-host prefix on a flagged attribute | `ValidationError` | Keyed by attribute name, so the attribute is named in the message |
| Schema update flips `allow_prefix` | Unsupported-schema-change error | Names `parameters.allow_prefix` as the offending path |

## Backward-compatibility guarantees

1. Every existing schema parses unchanged — `allow_prefix` defaults to `true`.
2. Every existing stored value is untouched. Zero rows rewritten.
3. `IPHostType`'s GraphQL shape is unchanged, so no client breaks on the type.
4. No graph label, property, or index changes; `GRAPH_VERSION` unchanged.
5. The existing `IPHost` test suites must pass with no modification (FR-012, SC-006).
