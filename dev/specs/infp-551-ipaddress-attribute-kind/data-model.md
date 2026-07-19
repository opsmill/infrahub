# Data Model: IPAddress attribute kind

Phase 1 output. Describes the new entity, its stored form, validation, and relationships.

## Entity: `IPAddress` attribute kind

A schema attribute kind representing a single **bare** IP address (IPv4 or IPv6), with no
subnet/prefix. Selected in a node/generic schema as `kind: IPAddress`, alongside `IPHost`
and `IPNetwork`.

### Logical value

| Aspect | IPAddress (new) | IPHost (existing) | IPNetwork (existing) |
|---|---|---|---|
| Python mapping | `ipaddress.ip_address` | `ipaddress.ip_interface` | `ipaddress.ip_network` |
| Stored string | bare, e.g. `192.168.1.1`, `2001:db8::1` | `192.168.1.1/24` | `192.168.1.0/24` |
| Prefix stored? | **No** | Yes (`prefixlen`) | Yes (`prefixlen`) |
| API-boundary python type | `IPvAnyAddress` | `IPvAnyAddress` | `str` |

### Stored graph representation

New `AttributeValue`-family node, label chain
`AttributeValue:AttributeValueIndexed:AttributeIPAddress`.

`GraphAttributeIPAddressProperties`:

| Property | Type | Notes |
|---|---|---|
| `value` | str | canonical bare address (compressed IPv6) |
| `is_default` | bool | default-value flag |
| `binary_address` | str | zero-padded binary of the address (max_prefixlen bits) for range/containment queries |
| `version` | int | 4 or 6 |

Deliberately **omits** `prefixlen` (present on IPHost/IPNetwork) — a bare address has none.

Index: `attr_ipaddress_bin` — RANGE index on `AttributeIPAddress(binary_address)`.

`AttributeDBNodeType` flag: `IPADDRESS_ONLY = auto()`;
`IPADDRESS = DEFAULT | INDEX_ONLY | IPADDRESS_ONLY`.

### Validation rules

- **V1 (FR-002)**: value MUST parse as `ipaddress.ip_address(value)` — any valid IPv4/IPv6.
- **V2 (FR-003)**: value MUST NOT contain a prefix; `ip_address` rejects any `/` including
  `/32`·`/128`, raising a `ValidationError` `"<value> is not a valid IPAddress"`.
- **V3 (FR-004)**: malformed values are rejected by the same parse.
- **V4**: optional attributes may be null (`IPAddressOptional`); required ones must have a
  valid bare value.
- **V5 (normalisation)**: stored value is `str(ipaddress.ip_address(value))` — canonical,
  identical across UI/GraphQL/SDK.

### Derived / exposed properties (attribute class)

`get_allowed_property_in_path()` → `["binary_address", "ip", "value", "version"]`.
GraphQL `IPAddressType` exposes `value` and `version` (bare-address-relevant only).

### Relationships

None beyond the standard attribute-value graph edges (`HAS_ATTRIBUTE`, `HAS_VALUE`,
`IS_PROTECTED`, optional `HAS_SOURCE`/`HAS_OWNER`). No relationship to IPAM nodes, pools,
or hierarchy.

## SDK representation

| Class | value type |
|---|---|
| `IPAddress(Attribute)` | `ipaddress.IPv4Address \| ipaddress.IPv6Address` |
| `IPAddressOptional(Attribute)` | `... \| None` |

- Parse: `value_mapper["IPAddress"] = ipaddress.ip_address`.
- Serialize: bare address → `str(value)` (no `.with_prefixlen`).
- `ATTRIBUTE_KIND_MAP["IPAddress"] = "IPAddress"`; `AttributeKind.IPADDRESS = "IPAddress"`.

## Frontend representation

- `ATTRIBUTE_KIND.IP_ADDRESS = "IPAddress"` (derives the `AttributeKind` TS union
  automatically).
- Editing: plain text `InputField` (no prefix-length selector) — identical UX to IPHost's
  current text input.
- Display: `TextDisplay` / plain value span in tables; plain `Input` in filters.
- Icon: `ATTRIBUTE_ICONS.IPAddress` (Record is exhaustive → compile-forced entry).
- GraphQL `IpAddress` type appears in generated types after backend codegen; frontend can
  share the text-render path.

## State transitions

None. An `IPAddress` value has no lifecycle beyond create/update/delete via the standard
attribute machinery. Kind changes to/from `IPAddress` go through the existing generic
attribute-kind-change migration/validator (out of scope to extend).
