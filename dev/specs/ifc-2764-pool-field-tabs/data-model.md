# Data model — the availability harness

Not an application data model: this feature adds no entities. What follows is the **fixture**
model — the schema shapes and seed data the harness needs so every availability rule can be
reached by hand (FR-023) rather than only asserted in a unit test.

The rules being covered are in `scratchpad/edge-case-matrix.md` and span three gating layers:
whether a pool is offered at all, whether each override is offered, and which requested types the
server accepts.

## Already present in `models/examples/ipam_kind_override.yml`

| Shape | Unlocks |
|---|---|
| `InfraLoopbackAddress` inheriting `BuiltinIPAddress` (2nd concrete type) | type override offered; override wins over the pool default |
| `InfraTransitPrefix` inheriting `BuiltinIPPrefix` (2nd concrete type) | same, prefix side |
| `InfraKindOverrideDemo` with `ip_address` / `ip_prefix` at the **bare generics**, cardinality one | the whole generic-peer path |

Plus, from the existing `models/base` schema and needing nothing new:

| Shape | Unlocks |
|---|---|
| `InfraDevice.primary_address` → concrete `IpamIPAddress`, cardinality one | pool offered, **no** type override (type is pinned) |
| `InfraInterfaceL3.ip_addresses` → cardinality **many** | **no** pool at all |
| `InfraDevice.site` / `.platform` → non-IP peer | **no** pool at all |

## To add — 4 schema shapes

The seven "missing" shapes reduce to four once the base schema is credited above.

| # | Shape | Unlocks | Notes |
|---|---|---|---|
| S1 | A generic inheriting `BuiltinIPAddress` used by **exactly one** concrete type, and a node with a cardinality-one relationship to it | pool offered, **type override withheld** — nothing to override | The `> 1` half of the override's visibility rule; today only the `≥ 2` half is reachable |
| S2 | A node with an `address` **attribute** (not a relationship) | the attribute pool path, **create-only**; and the FR-017 attribute-side check | Attribute pools require the attribute to be named exactly `address` or `prefix` |
| S3 | A node with a **Number** attribute backed by a Number pool | pool offered, **neither** override applies | The only non-IP pool kind |
| S4 | An **object template** over a pool-backed relationship | template-inherited pool value: shown for provenance, **not submitted** | Also the documented IFC-3135 limitation |

S2 is the one that matters most: it is the prerequisite for deciding D3 in
[research.md](./research.md), because it is what makes the suspected
`getFieldDefaultValue` defect reachable.

## To add — seed data

In `models/examples/ipam_kind_override_data.py`:

| # | Data | Why |
|---|---|---|
| D1 | A `CoreNumberPool` bound to S3's attribute | S3 is inert without it — the Number gate is `pool.options` being non-empty |
| D2 | A second `CoreIPAddressPool` defaulting to **`InfraLoopbackAddress`** | Today both pools default to an `Ipam*` type, so "default" and "override" are only distinguishable in one direction. With this, allocating `IpamIPAddress` from an `Infra`-defaulting pool is also an observable override. |
| D3 | An object created from S4's template | Makes the template-inherited case reachable without the reader building a template by hand |
| D4 | A roomier address-pool resource | Already applied: the pool's resource is a `/25` rather than a `/29`, since hand-testing exhausted 8 addresses quickly |

## Invariants the harness must preserve

- **Pool defaults point at `Ipam*` types** (except D2, deliberately inverted). This is what makes
  an override observable at a glance: an `Infra*` result can only have come from an override.
- **`models/base/ipam.yml` stays untouched.** It defines exactly one concrete type per generic —
  the original reason the feature could not be exercised — and changing it would ship demo-only
  types into the default dev schema.
- **One load command each.** Shapes go into the existing YAML and data into the existing script,
  so `quickstart.md` keeps a single `infrahubctl schema load` and a single `infrahubctl run`.
