# Tasks: IPAddress attribute kind (bare IP, no netmask)

**Feature**: INFP-551 | **Branch**: `ipaddress-attribute-kind-infp-551` | **Base**: `develop`

**Inputs**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/graphql-and-sdk.md](./contracts/graphql-and-sdk.md),
[quickstart.md](./quickstart.md)

Tests are included (constitution Principle IV — Test Discipline). Paths are exact; `[P]` =
parallelizable (distinct files, no incomplete deps). Backend paths are under
`backend/infrahub/` and `backend/tests/`; frontend under `frontend/app/src/`; SDK under the
separate repo `../infrahub-sdk-python/` (base `origin/infrahub-develop`).

---

## Phase 1: Setup

- [x] T001 Confirm feature branch `ipaddress-attribute-kind-infp-551` is checked out off `develop`, and create an SDK working branch `ipaddress-attribute-kind-infp-551` off `origin/infrahub-develop` in `../infrahub-sdk-python`.
- [x] T002 [P] Add a Towncrier changelog fragment `changelog/+ipaddress-attribute-kind.added.md` describing the new `IPAddress` attribute kind (user-facing).

---

## Phase 2: Foundational (blocks all user stories)

The new attribute kind must exist end-to-end in the backend before any story is testable.

### Registry & attribute class

- [x] T003 Add `IPAddress(InfrahubDataType)` (and register in `ATTRIBUTE_TYPES`, `ATTRIBUTE_PYTHON_TYPES` as `IPvAnyAddress`) in `backend/infrahub/types.py`: `graphql=String`, `graphql_query="IPAddressType"`, `graphql_create/update="TextAttributeCreate/Update"`, `graphql_filter=String`, `infrahub="IPAddress"`.
- [x] T004 Add `IPAddress(BaseAttribute)` + `IPAddressOptional(IPAddress)` in `backend/infrahub/core/attribute.py`: `obj` via `ipaddress.ip_address`; properties `ip`, `version`, `ip_binary`; `validate_format` accepts IP and rejects prefix (via `ip_address`); `_normalize_value` returns `str(ipaddress.ip_address(value))`; `get_db_node_type` returns `AttributeDBNodeType.IPADDRESS`; `to_db` writes `version` + `binary_address` (NO `prefixlen`); `get_allowed_property_in_path` returns `["binary_address","ip","value","version"]`.

### Dedicated DB node type

- [x] T005 Add `IPADDRESS_ONLY = auto()` and `IPADDRESS = DEFAULT | INDEX_ONLY | IPADDRESS_ONLY` to `AttributeDBNodeType` in `backend/infrahub/core/constants/__init__.py`.
- [x] T006 Widen the `convert_ip_to_binary_str` type annotation to include `ipaddress.IPv4Address | ipaddress.IPv6Address` in `backend/infrahub/core/utils.py` (runtime already works; annotation only).
- [x] T007 Add `GraphAttributeIPAddressProperties` (value, is_default, binary_address, version) + `GraphAttributeIPAddressNode` (`default_label="AttributeIPAddress"`), and register `GraphAttributeIPAddressNode` in `get_graph_schema()` in `backend/infrahub/core/graph/schema.py`.
- [x] T008 Add RANGE index `attr_ipaddress_bin` on `AttributeIPAddress(binary_address)` to `node_indexes` in `backend/infrahub/core/graph/index.py`.

### Write / read path

- [x] T009 In `backend/infrahub/core/query/node.py`: add `attributes_ipaddress` partition (an `elif AttributeDBNodeType.IPADDRESS in node_type:` branch placed BEFORE the generic `INDEXED` branch), `attrs_ipaddress` params, `ipaddress_prop` dict (value/is_default/binary_address/version), `attrs_ipaddress_query` MERGE on `AttributeValue:AttributeValueIndexed:AttributeIPAddress`, and the conditional append in the final query.
- [x] T010 In `backend/infrahub/core/query/attribute.py`: import `GraphAttributeIPAddressNode` and add `if AttributeDBNodeType.IPADDRESS in node_type: labels.append(GraphAttributeIPAddressNode.get_default_label())` to the value-update label logic.

### GraphQL type

- [x] T011 Add `IPAddressType(BaseAttribute)` (fields `value`, `version`; `Meta.name="IPAddress"`) in `backend/infrahub/graphql/types/attribute.py`, and export it from `backend/infrahub/graphql/types/__init__.py` (import + `__all__`).

### Migration & version bump

- [x] T012 Bump `GRAPH_VERSION` from 74 to 75 in `backend/infrahub/core/graph/__init__.py`.
- [x] T013 Add `backend/infrahub/core/migrations/graph/m075_add_attribute_ipaddress_index.py` (`Migration075`, `minimum_version=74`) that, guarded by a Neo4j-only check, builds the `attr_ipaddress_bin` IndexItem and calls `IndexManagerNeo4j.add()`. No data backfill.

**Checkpoint**: backend compiles; `uv run invoke backend.generate` runs clean; schema
attribute-kind enum now includes `IPAddress`.

---

## Phase 3: User Story 1 — Store & read a bare address (P1) 🎯 MVP

**Goal**: Create/read an `IPAddress` value; stored and returned bare (no `/32`·`/128`) via
DB and GraphQL. **Independent test**: create instance `192.0.2.10`, read via GraphQL → exactly
`192.0.2.10`, `version 4`.

- [x] T014 [P] [US1] Add `IPAddress`/`IPAddressOptional` construction + `to_db` (version, binary_address, no prefixlen) + `get_db_node_type` unit/component tests in `backend/tests/component/core/test_attribute.py` (mirror the IPHost cases).
- [x] T015 [P] [US1] Add an `IPAddress` case to `backend/tests/unit/test_types.py` (allowed-path fields; `include_binary_address` true; no prefixlen).
- [x] T016 [US1] Add a component test creating a node with an `IPAddress` attribute and asserting the DB stores value + binary_address + version on an `AttributeIPAddress`-labelled value node (bare, no prefix) in `backend/tests/component/core/` (near the IPHost graph tests).
- [x] T017 [US1] Add a GraphQL query test asserting `address { value version }` returns the bare address and correct version (IPv4 and IPv6) in the appropriate `backend/tests/component/graphql/` query test module.
- [x] T018 [US1] Regenerate `schema/schema.graphql` (`uv run invoke schema.generate-graphqlschema`) and confirm the `IPAddress` attribute type appears; commit the regenerated file.

**Checkpoint**: US1 acceptance scenarios pass — bare address round-trips through DB + GraphQL.

---

## Phase 4: User Story 2 — Reject prefix notation (P1)

**Goal**: Reject any prefix/CIDR input and any invalid IP. **Independent test**: `10.0.0.1/24`,
`10.0.0.1/32`, `2001:db8::1/128`, `not-an-ip` all rejected; `10.0.0.1` accepted.

- [x] T019 [P] [US2] Add `validate_format` tests to `backend/tests/component/core/test_attribute.py`: rejects `10.0.0.1/24`, `10.0.0.1/32`, `2001:db8::1/128`, `999.0.0.1`, `not-an-ip`; accepts `10.0.0.1`, `2001:db8::1` (both IPv4/IPv6).
- [x] T020 [US2] Add a GraphQL mutation test asserting a create/update with a prefixed value fails with a validation error, in the appropriate `backend/tests/component/graphql/` mutation test module.

**Checkpoint**: US1 + US2 = backend MVP complete and validated.

---

## Phase 5: User Story 3 — Consistent UI/GraphQL/SDK experience (P2)

**Goal**: Bare, prefix-free experience in the Web UI and Python SDK; IPHost/IPNetwork
unchanged. **Independent test**: round-trip the same value through UI + SDK; confirm IPHost/
IPNetwork still carry prefixes.

### Frontend

- [x] T021 [P] [US3] Add `IP_ADDRESS: "IPAddress"` to `ATTRIBUTE_KIND` in `frontend/app/src/entities/schema/constants.ts` (and to `ATTRIBUTE_KINDS_FOR_LIST_VIEW` if list-view visibility is desired).
- [x] T022 [US3] Add an `IPAddress` entry to `ATTRIBUTE_ICONS` in `frontend/app/src/entities/schema/ui/field-schema-icon.tsx` (Record is exhaustive → required for compilation).
- [x] T023 [P] [US3] Add `case ATTRIBUTE_KIND.IP_ADDRESS:` to the plain-`InputField` group in `frontend/app/src/shared/components/form/dynamic-form.tsx` (no prefix selector).
- [x] T024 [P] [US3] Add `case ATTRIBUTE_KIND.IP_ADDRESS:` to the `TextDisplay` group in `frontend/app/src/entities/nodes/getObjectItemDisplayValue.tsx`.
- [x] T025 [P] [US3] Add the new kind to the value-span group in `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-attribute-cell.tsx`.
- [x] T026 [P] [US3] Add the new kind to the plain-`Input` filter group in `frontend/app/src/entities/nodes/object/ui/filters/dynamic-filter-input.tsx`.
- [x] T027 [US3] Regenerate frontend types: `cd frontend/app && pnpm codegen` (reads local schema); confirm `IpAddress` appears in generated GraphQL types.
- [x] T028 [P] [US3] Extend `frontend/app/src/entities/nodes/object/utils/get-attributes-visible-in-list-view.test.ts` with an `IPAddress` fixture + expected entry (if added to list-view).

### SDK (`../infrahub-sdk-python/`, base `infrahub-develop`)

- [x] T029 [P] [US3] Add `IPAddress(Attribute)` (`value: IPv4Address | IPv6Address`) + `IPAddressOptional` in `infrahub_sdk/protocols_base.py`.
- [x] T030 [P] [US3] Add `"IPAddress": "IPAddress"` to `ATTRIBUTE_KIND_MAP` in `infrahub_sdk/protocols_generator/constants.py`.
- [x] T031 [P] [US3] Add `IPADDRESS = "IPAddress"` to `AttributeKind` enum in `infrahub_sdk/schema/main.py`.
- [x] T032 [US3] Add `"IPAddress": ipaddress.ip_address` to `value_mapper` and adjust serialization so bare `IPv4Address`/`IPv6Address` serialise via `str()` (not `.with_prefixlen`) in `infrahub_sdk/node/attribute.py` (and extend `IP_TYPES` handling in `infrahub_sdk/node/constants.py` as needed).
- [x] T033 [US3] Add `IPAddress,` / `IPAddressOptional,` to the `protocols_base` import block in `infrahub_sdk/protocols_generator/template.j2`, then regenerate `infrahub_sdk/protocols.py`.
- [x] T034 [P] [US3] Add an `ipaddress`-kind schema fixture + create-input and deserialization tests (bare address, no prefix) in `../infrahub-sdk-python/tests/unit/sdk/test_node.py` and `conftest.py`.

**Checkpoint**: UI shows/edits bare addresses with no prefix selector; SDK returns bare
address objects; IPHost/IPNetwork unchanged.

---

## Phase 6: User Story 4 — Filtering (P3)

**Goal**: Equality filtering by `IPAddress` value. **Independent test**: filter
`address__value == "192.0.2.10"` returns only matching instances.

- [x] T035 [US4] Add a GraphQL filter test asserting `address__value`/`address__values` return the correct instances in the appropriate `backend/tests/component/graphql/` module.

---

## Phase 7: Polish & Cross-Cutting

- [x] T036 [P] Add user-facing documentation for the `IPAddress` attribute kind in `docs/` (schema attribute-kinds reference / relevant topic), noting the difference from IPHost/IPNetwork.
- [x] T037 [P] Update backend knowledge docs if the attribute/graph-storage docs enumerate kinds (`dev/knowledge/backend/`), reflecting the new `AttributeIPAddress` node type.
- [x] T038 Regenerate all generated files and verify committed: `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`; `git diff --exit-code` clean.
- [x] T039 Run `uv run invoke format lint` (ruff+mypy), `cd frontend/app && pnpm biome:fix && pnpm test`, then `/pre-ci`.
- [x] T040 End-to-end verification per [quickstart.md](./quickstart.md): run a local Infrahub instance on this branch with the SDK submodule pointed at the local SDK branch; execute Scenarios 1–6 (bare store/read, prefix rejection, UI, HFID round-trip, SDK round-trip + IPHost/IPNetwork no-regression, filtering).
- [x] T041 Open the SDK PR against the SDK repo (`infrahub-develop`); once merged upstream, bump the `python_sdk` submodule pointer in the Infrahub PR.

---

## Dependencies & order

- **Phase 2 (Foundational)** blocks all user stories. Within Phase 2: T003–T004 (registry/class)
  → T005–T008 (DB type/index) → T009–T010 (queries) → T011 (GraphQL) → T012–T013 (migration).
- **US1 (Phase 3)** depends only on Phase 2 → MVP.
- **US2 (Phase 4)** depends on Phase 2 (T004 validate_format); independent of US1.
- **US3 (Phase 5)**: frontend depends on Phase 2 + T018/T027 codegen; SDK is independent of
  frontend and can proceed in parallel once Phase 2 is stable.
- **US4 (Phase 6)** depends on Phase 2 (filters auto-derive from the registry).
- **Polish (Phase 7)**: T038–T041 after all stories; T041 gated on the SDK PR merge.

## Parallel opportunities

- Backend tests T014/T015 [P]; frontend switch edits T021/T023/T024/T025/T026/T028 [P] (distinct
  files); SDK edits T029/T030/T031/T034 [P]. The whole SDK track (Phase 5 SDK) runs in parallel
  with the frontend track.

## MVP scope

**US1 + US2** (Phases 2–4): the backend delivers bare-address store/read with prefix rejection —
a demonstrable, independently valuable slice. US3 (UI+SDK) and US4 (filtering) layer on top.
