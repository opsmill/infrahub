# Research: IPAddress attribute kind

Phase 0 output. All open technical questions resolved against the current `develop` code.

## R1 — Validation semantics (accept IP, reject prefix)

- **Decision**: Validate with `ipaddress.ip_address(value)` in the attribute class
  `validate_format`. Store the canonical string via `_normalize_value` returning
  `str(ipaddress.ip_address(value))`.
- **Rationale**: `ipaddress.ip_address("10.0.0.1/24")` raises `ValueError` — prefix
  notation is rejected for free, satisfying FR-003. `ip_address` also rejects malformed
  addresses (FR-004). Canonical `str()` gives compressed IPv6 (e.g. `2001:db8::1`),
  matching the "consistent representation" requirement.
- **Alternatives considered**: manual `/` check then `ip_interface` — unnecessary;
  `ip_address` already rejects the slash. Pydantic `IPvAnyAddress` is used for the
  API-boundary python type map, complementing (not replacing) the attribute validator.

## R2 — Binary form for indexing

- **Decision**: Reuse `convert_ip_to_binary_str` (backend `core/utils.py`) to compute
  `binary_address` from the bare address object. Widen its type annotation to also accept
  `IPv4Address | IPv6Address`.
- **Rationale**: The function's non-network branch uses only `int(obj)` and
  `obj.max_prefixlen`, both supported by `IPv4Address`/`IPv6Address` (32/128). It works
  as-is at runtime; only the annotation needs widening for mypy cleanliness.
- **Note**: Unlike IPHost (which stores `prefixlen`), the `AttributeIPAddress` value node
  stores **no** `prefixlen` — a bare address has no prefix. Properties stored: `value`,
  `is_default`, `binary_address`, `version`.

## R3 — Dedicated DB node type wiring

- **Decision**: Add `AttributeDBNodeType.IPADDRESS_ONLY = auto()` and
  `IPADDRESS = DEFAULT | INDEX_ONLY | IPADDRESS_ONLY` to the `Flag` in
  `core/constants/__init__.py`. Add `GraphAttributeIPAddressProperties` +
  `GraphAttributeIPAddressNode` (label `AttributeIPAddress`) in `core/graph/schema.py`
  and register in `get_graph_schema()`. Add a RANGE index `attr_ipaddress_bin` on
  `AttributeIPAddress.binary_address` in `core/graph/index.py`.
- **Flag-safety check**: because `IPADDRESS` carries a distinct `IPADDRESS_ONLY` bit, the
  existing `AttributeDBNodeType.IPHOST in node_type` / `IPNETWORK in node_type` membership
  checks do **not** match an IPADDRESS attribute. The write-path partitioning must add an
  `IPADDRESS` branch **before** the generic `INDEXED` branch (since `INDEXED` bits are a
  subset of `IPADDRESS`).
- **Rationale**: mirrors the proven `AttributeIPHost` machinery; keeps bare addresses in a
  self-describing label without a phantom prefix. This is the feature owner's decided
  design (see plan Complexity Tracking).

## R4 — Write-path Cypher

- **Decision**: In `core/query/node.py`, add an `attributes_ipaddress` partition list, an
  `attrs_ipaddress` params entry, an `ipaddress_prop` dict (value, is_default,
  binary_address, version — **no** prefixlen), an `attrs_ipaddress_query` block that
  `MERGE`s on `AttributeValue:AttributeValueIndexed:AttributeIPAddress`, and a conditional
  append in the final query. In `core/query/attribute.py`, add a
  `if AttributeDBNodeType.IPADDRESS in node_type:` branch appending
  `GraphAttributeIPAddressNode.get_default_label()` on value updates.
- **Rationale**: exact structural parallel to the existing IPHost/IPNetwork blocks.
  Parameterized (`$attrs_ipaddress`), satisfying the injection-prevention gate.

## R5 — Graph migration + index application

- **Findings**:
  - `GRAPH_VERSION = 74` in `core/graph/__init__.py`; highest migration is `m074`.
    Migrations are **auto-discovered** by scanning the directory (no registry list to
    edit); a migration runs when `current_graph_version <= migration.minimum_version`.
  - Indexes in `core/graph/index.py` are applied on **every server startup** via
    `add_indexes()` using `CREATE ... IF NOT EXISTS` (idempotent), and by the
    `infrahub db index` CLI. So adding the `node_indexes` entry covers fresh **and**
    upgraded installs.
  - **No data migration** was written when IPHost/IPNetwork were introduced — the
    dedicated labels + `binary_address` only ever applied to newly-written data. No
    backfill/relabel of existing `AttributeValue` nodes exists.
- **Decision**: Bump `GRAPH_VERSION` to `75`. Add `m075_add_attribute_ipaddress_index.py`
  (`Migration075`, `minimum_version = 74`) that builds the `attr_ipaddress_bin` IndexItem
  and calls `IndexManagerNeo4j.add()` — the explicit, belt-and-suspenders path for
  `infrahub db migrate` / `infrahub upgrade` flows that may run before a server boot,
  guarded by a Neo4j-only check. **No data backfill** is required (existing IPHost data is
  untouched; new IPAddress data is written with the new label from day one).
- **Rationale**: matches historical precedent (`m036`/`m037` index migrations) and the
  Schema-Driven-Integrity gate (upgrade path is deterministic, no manual steps → SC-005).

## R6 — GraphQL type

- **Decision**: Add `IPAddressType(BaseAttribute)` in `graphql/types/attribute.py` with
  fields `value`, `version` (and `ip` optionally, equal to value); `Meta.name = "IPAddress"`.
  Export from `graphql/types/__init__.py`. Wire the new `IPAddress` datatype in `types.py`
  with `graphql_query = "IPAddressType"`, `graphql_create/update = TextAttributeCreate/Update`
  (reuse, as IPHost does), `graphql_filter = graphene.String`.
- **Collision check**: No existing graphene ObjectType is named `"IPAddress"` (existing
  attribute types are `"IPHost"`/`"IPNetwork"`; the node kind is `BuiltinIPAddress`). The
  Python symbol `IPAddressType` exists only as an unrelated alias in `core/ipam/constants.py`
  (different module) — no conflict inside `graphql/types/attribute.py`.
- **Rationale**: registration in `ATTRIBUTE_TYPES` auto-enables GraphQL query type,
  create/update inputs, and `address__value`/`address__values` filters via the schema
  manager. Bare-address type intentionally omits prefix/netmask/hostmask fields.

## R7 — Filtering

- **Finding**: Equality filters (`__value`, `__values`, `__isnull`) are generated from the
  attribute's `InfrahubDataType.get_graphql_filters()` driven by `ATTRIBUTE_TYPES`, **not**
  by the DB label or `AttributeDBNodeType`. `get_allowed_property_in_path()` separately
  governs dotted paths usable in `default_filter`/`order_by`/`display_label`.
- **Decision**: Registering the `IPAddress` datatype yields equality filtering (FR-011)
  automatically. `get_allowed_property_in_path()` on the new attribute class returns
  `["binary_address", "ip", "value", "version"]` (the bare-address-relevant subset).

## R8 — SDK bare-address serialization

- **Finding**: SDK `node/attribute.py` parses via a `value_mapper` (`IPHost →
  ip_interface`, `IPNetwork → ip_network`) and serialises IP objects with
  `.with_prefixlen`. Bare `IPv4Address`/`IPv6Address` objects are **not** in the SDK's
  `IP_TYPES` and have no `.with_prefixlen`.
- **Decision**: Add `"IPAddress": ipaddress.ip_address` to `value_mapper`; adjust
  serialization so a bare address object serialises via `str()` (canonical) rather than
  `.with_prefixlen`. Add `IPAddress`/`IPAddressOptional` protocol classes
  (`value: IPv4Address | IPv6Address [| None]`), the `ATTRIBUTE_KIND_MAP` entry, the
  `AttributeKind.IPADDRESS` enum member, and the `template.j2` import so generated
  `protocols.py` imports them.
- **Rationale**: mirrors IPHost SDK handling while honouring "no prefix". SDK PR targets
  the SDK repo's `infrahub-develop` branch.

## R9 — Cross-repo delivery sequencing

- **Finding** (AGENTS.md submodule rules): Infrahub `develop` tracks SDK branch
  `infrahub-develop` (not the SDK's own `develop`). A submodule pointer to an unpushed
  commit breaks other checkouts.
- **Decision**: (1) implement + PR the SDK change against `infrahub-develop`; (2) for local
  e2e verification point the submodule at the local SDK commit; (3) land the committed
  submodule-pointer bump in the Infrahub PR only after the SDK PR merges upstream.

## Out-of-scope confirmation

- No bulk data-migration tool to convert existing IPHost `/32`·`/128` values to IPAddress.
  The generic attribute-kind-change migration/validator path already exists and is
  unaffected; a manual per-attribute kind change will surface value-fit errors normally.
