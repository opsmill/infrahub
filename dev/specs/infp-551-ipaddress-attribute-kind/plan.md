# Implementation Plan: IPAddress attribute kind (bare IP, no netmask)

**Branch**: `ipaddress-attribute-kind-infp-551` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/infp-551-ipaddress-attribute-kind/spec.md`

## Summary

Add a third IP-related attribute kind, `IPAddress`, that stores a **bare** IPv4/IPv6
address with no prefix — validated as a real IP address, rejecting any CIDR/prefix
notation. It sits alongside `IPHost` (address + prefix) and `IPNetwork` (network +
prefix) and is delivered across the full stack: backend (Python), frontend (React/TS),
and the Python SDK (separate repo). Per the decided design, `IPAddress` gets a
**dedicated `AttributeIPAddress` graph representation** (its own DB label, index, and
Cypher write path, storing `value` + `version` + `binary_address` for range/containment
queries), mirroring the existing `AttributeIPHost` machinery rather than reusing it.

## Technical Context

**Language/Version**: Python 3.13/3.14 (backend, SDK); TypeScript 5.9 / React 19.2 (frontend)

**Primary Dependencies**: FastAPI, graphene (GraphQL), Neo4j 2025.10+ (driver 6.x),
Pydantic 2.12, Python stdlib `ipaddress`; frontend Vite/Tailwind; SDK Pydantic + `ipaddress`

**Storage**: Neo4j graph. New `AttributeValue`-family label `AttributeIPAddress` with a
RANGE index on `binary_address`.

**Testing**: pytest (backend unit + component via TestContainers), Vitest (frontend unit),
SDK pytest unit tests, plus a manual/quickstart end-to-end round-trip on a running instance.

**Target Platform**: Linux server (backend), browser (frontend), Python client (SDK)

**Project Type**: Web application (backend + frontend) + companion SDK library

**Performance Goals**: Equality filtering and read/write of `IPAddress` values on par with
`IPHost`; `binary_address` index enables IP range/containment queries.

**Constraints**: No regression to `IPHost`/`IPNetwork`; generated files must be regenerated
not hand-edited; all Cypher parameterized; branch/temporal-safe writes.

**Scale/Scope**: Additive attribute kind. ~3 repos, ~1 graph migration, ~2 dozen files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Schema-Driven Integrity**: PASS. New kind is registered in the schema attribute-kind
  registry; the new DB label and index are introduced via a graph migration; all generated
  files (schema.graphql, openapi.json, protocols.py, frontend codegen, reference docs) are
  regenerated, never hand-edited.
- **II. Branch-Safe by Default**: PASS. The new write path mirrors the existing
  `AttributeIPHost` MERGE, which already carries branch/temporal edges; no new branch logic.
  Attribute-value nodes are branch-agnostic like the existing ones; merge behaviour is
  inherited from the generic attribute machinery and covered by existing tests plus new ones.
- **III. Type Safety & Explicit Contracts**: PASS. New Python classes are fully typed; the
  GraphQL `IPAddressType` is defined before consumers; SDK exposes typed
  `IPAddress`/`IPAddressOptional`. No `any`/`as` in new frontend code.
- **IV. Test Discipline**: PASS. Unit tests (attribute validation, to_db, types), component
  tests (DB round-trip, filtering, graph-constraints/index shape, migration), SDK unit tests,
  and an end-to-end quickstart. Frontend unit test for list-view visibility.
- **V. Query Performance & Efficiency**: PASS. Parameterized Cypher; new RANGE index on
  `binary_address`; returns only needed properties. Mirrors the proven IPHost query shape.
- **VI. Security & Input Boundaries**: PASS. Validation at the API boundary via the attribute
  class `validate_format` (accept IP, reject prefix) and Pydantic `IPvAnyAddress`. No new
  auth surface; no user input interpolated into Cypher.
- **VII. Simplicity & Maintainability**: JUSTIFIED DEVIATION. The *simplest* option (reuse the
  IPHost DB node type) was explicitly rejected by the feature owner in favour of a dedicated
  `AttributeIPAddress` type for clean separation and correct semantics (no phantom prefix in
  storage). See Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/infp-551-ipaddress-attribute-kind/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output — end-to-end validation guide
├── contracts/           # Phase 1 output — GraphQL/SDK contract notes
├── checklists/
│   └── requirements.md  # spec quality checklist (from specify phase)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

Backend (`backend/infrahub/`):

```text
types.py                                  # NEW IPAddress data type + 3 dict entries
core/attribute.py                         # NEW IPAddress + IPAddressOptional classes
core/constants/__init__.py                # NEW AttributeDBNodeType.IPADDRESS_ONLY / IPADDRESS
core/graph/schema.py                      # NEW GraphAttributeIPAddress{Properties,Node} + register
core/graph/index.py                       # NEW attr_ipaddress_bin RANGE index
core/query/node.py                        # NEW attrs_ipaddress partition + Cypher block
core/query/attribute.py                   # NEW AttributeIPAddress label append
core/migrations/graph/mNNN_*.py           # NEW migration: create AttributeIPAddress index
core/migrations/graph/__init__.py         # register new migration
graphql/types/attribute.py                # NEW IPAddressType
graphql/types/__init__.py                 # export IPAddressType
tests/unit/test_types.py                  # IPAddress case
tests/component/core/test_attribute.py    # IPAddress validation / to_db / DB round-trip
tests/component/core/graph/…              # graph-constraints/index shape
tests/component/core/migrations/graph/…   # migration test
```

Frontend (`frontend/app/src/`):

```text
entities/schema/constants.ts                                   # IP_ADDRESS: "IPAddress"
entities/schema/ui/field-schema-icon.tsx                       # IPAddress icon (compile-forced)
shared/components/form/dynamic-form.tsx                        # IP_ADDRESS -> InputField (no prefix)
entities/nodes/getObjectItemDisplayValue.tsx                   # IP_ADDRESS -> TextDisplay
entities/nodes/object/ui/object-table/cells/table-attribute-cell.tsx  # value span
entities/nodes/object/ui/filters/dynamic-filter-input.tsx      # plain Input filter
entities/nodes/object/utils/get-attributes-visible-in-list-view.test.ts  # test fixture
shared/api/graphql/generated/*                                 # regenerated via pnpm codegen
```

SDK (`../infrahub-sdk-python/`, branch base `origin/infrahub-develop`):

```text
infrahub_sdk/protocols_base.py                 # IPAddress + IPAddressOptional classes
infrahub_sdk/protocols_generator/constants.py  # ATTRIBUTE_KIND_MAP += IPAddress
infrahub_sdk/schema/main.py                     # AttributeKind.IPADDRESS
infrahub_sdk/node/attribute.py                  # value_mapper parse + bare-address serialize
infrahub_sdk/node/constants.py                  # IP_TYPES handling for bare addresses
infrahub_sdk/protocols_generator/template.j2    # import IPAddress/IPAddressOptional
infrahub_sdk/protocols.py                        # regenerated
tests/unit/sdk/test_node.py, conftest.py         # SDK tests + fixture
```

**Structure Decision**: Existing web-app (`backend/` + `frontend/app/`) plus the companion
SDK submodule repo. All paths above are additive and mirror the existing `IPHost` wiring;
no new top-level structure is introduced.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dedicated `AttributeIPAddress` DB node type, index, and Cypher path (vs. reusing `AttributeIPHost`) | Feature owner requires clean semantic separation: a bare address must not be stored under a host-with-prefix label, and must never carry a phantom `/32`·`/128` prefixlen in the DB. Keeps range/containment querying while making the storage self-describing. | Reusing the IPHost DB node type would store bare addresses under a label whose contract implies a prefix, blurring the two kinds in the graph, complicating future IPHost-specific migrations/filters, and re-introducing the exact prefix-ambiguity (infrahub#8896) this feature exists to remove. |

## Phase notes

- **Cross-repo sequencing**: the SDK change ships as its own PR against the SDK repo
  (`infrahub-develop` base). For local end-to-end verification the submodule may point at the
  local SDK commit; the committed submodule pointer bump in the Infrahub PR lands only after
  the SDK PR is merged upstream (per AGENTS.md submodule rules).
- **Migration**: introducing a new `AttributeValue` label + index is forward-only and applies
  to newly written data; the migration's job is to ensure the new index exists on upgraded
  DBs. No backfill of existing rows is required (existing IPHost/IPNetwork data is untouched).
  Confirmed in research.md.
```
