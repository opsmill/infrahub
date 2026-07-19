# Feature Specification: IPAddress attribute kind (bare IP, no netmask)

**Feature Branch**: `ipaddress-attribute-kind-infp-551`

**Created**: 2026-07-19

**Status**: Draft

**Jira**: [INFP-551](https://opsmill.atlassian.net/browse/INFP-551)

**Input**: User description: "Add a new `IPAddress` attribute kind to Infrahub for storing bare IP addresses without a netmask/prefix (cross-stack: backend, frontend, Python SDK)."

## Overview

Infrahub offers two IP-related attribute kinds today — `IPHost` (an address *with* a
prefix, e.g. `192.168.1.1/24`) and `IPNetwork` (a network with a prefix, e.g.
`192.168.1.0/24`). Neither can represent a *bare* IP address. Customers modelling data
such as DNS A/AAAA records, NTP/syslog/SNMP server addresses, monitoring targets,
anycast VIPs, ACL entries, and load-balancer pool members must currently choose between:

- `IPHost`, which silently appends `/32` (IPv4) or `/128` (IPv6) and returns the mask
  inconsistently across the Web UI, GraphQL API, and Python SDK (see infrahub#8896); or
- `Text`, which discards all IP validation.

This feature adds a third kind, `IPAddress`, that stores and returns a plain IP address
with no prefix — validated as a real IPv4/IPv6 address — giving a clean, consistent
representation everywhere the value is entered, stored, queried, or displayed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Model a bare IP address on a schema node (Priority: P1)

A schema author defines an attribute with `kind: IPAddress` on any node (e.g. a
`DnsRecord.address` or `NtpServer.address`). A data author then creates instances,
entering a bare address such as `10.0.0.1` or `2001:db8::1`. The value is validated as a
proper IP address, stored without any mask, and read back identically — in the UI, via
GraphQL, and via the SDK.

**Why this priority**: This is the core capability. Without it nothing else exists; it
directly resolves the customer pain of spurious `/32` and `/128` masks.

**Independent Test**: Define a node with an `IPAddress` attribute, create an instance
with `10.0.0.1`, and confirm the value is stored and returned as exactly `10.0.0.1`
(no `/32`) through the UI, a GraphQL query, and an SDK `client.get(...)`.

**Acceptance Scenarios**:

1. **Given** a node schema with an `IPAddress` attribute, **When** a user creates an
   instance with value `192.0.2.10`, **Then** the stored and returned value is exactly
   `192.0.2.10` with no prefix in any interface.
2. **Given** the same node schema, **When** a user creates an instance with an IPv6
   value `2001:db8::1`, **Then** the value is stored and returned as `2001:db8::1` with
   no `/128`.
3. **Given** an instance whose display label / HFID includes the `IPAddress` attribute,
   **When** the value is looked up by that HFID via GraphQL, **Then** the HFID returned
   by a query is usable directly as lookup input (no mask needs to be added or removed).

### User Story 2 - Reject prefix notation (Priority: P1)

A data author mistakenly enters `10.0.0.1/24` into an `IPAddress` attribute. The system
rejects the value with a clear validation error, because a bare-address attribute must
not carry a prefix.

**Why this priority**: Rejecting prefixes is the defining behavioural difference from
`IPHost` and is essential to the feature's contract. It is part of the P1 MVP.

**Independent Test**: Attempt to set an `IPAddress` attribute to `10.0.0.1/24` and to
`not-an-ip`; both are rejected, while `10.0.0.1` is accepted.

**Acceptance Scenarios**:

1. **Given** an `IPAddress` attribute, **When** a user submits `10.0.0.1/24`, **Then**
   the operation fails with a validation error indicating a bare IP address is required.
2. **Given** an `IPAddress` attribute, **When** a user submits `999.0.0.1` or
   `not-an-ip`, **Then** the operation fails with a validation error.
3. **Given** an `IPAddress` attribute, **When** a user submits a valid `10.0.0.1`,
   **Then** the operation succeeds.

### User Story 3 - Consistent, prefix-free experience across every interface (Priority: P2)

An automation engineer reads and writes `IPAddress` values through the Web UI, GraphQL,
and the Python SDK, and never has to add or strip a mask. The SDK returns a bare-address
object (not an interface with a prefix). Existing `IPHost` and `IPNetwork` behaviour is
unchanged.

**Why this priority**: The value of the feature is a *consistent* clean experience; it
depends on Story 1 existing first, hence P2.

**Independent Test**: On a running instance, round-trip the same `IPAddress` value
through UI, GraphQL, and SDK and confirm identical bare representation; separately
confirm `IPHost`/`IPNetwork` values still round-trip with their prefixes intact.

**Acceptance Scenarios**:

1. **Given** an instance with an `IPAddress` value, **When** it is retrieved via the
   Python SDK, **Then** the returned value is a bare address (no prefix) and matches the
   UI display and the GraphQL response.
2. **Given** existing `IPHost` and `IPNetwork` attributes, **When** they are read and
   written after this feature ships, **Then** their behaviour (including prefixes) is
   unchanged.

### User Story 4 - Filter and query on IPAddress values (Priority: P3)

A user filters a list of nodes by their `IPAddress` attribute, including matching a
specific address and (where supported for IP attributes) address-range/containment
filters, with performance comparable to `IPHost`.

**Why this priority**: Nice-to-have parity with `IPHost` query ergonomics; not required
for the MVP of storing and reading bare addresses.

**Independent Test**: Create several instances with distinct `IPAddress` values and
confirm equality filtering returns the correct instances.

**Acceptance Scenarios**:

1. **Given** multiple instances with different `IPAddress` values, **When** a user
   filters by an exact address, **Then** only matching instances are returned.

### Edge Cases

- **IPv4 vs IPv6**: both families are accepted; behaviour (bare storage, no prefix) is
  identical for each.
- **Prefix notation**: `10.0.0.1/32` and `2001:db8::1/128` are rejected even though the
  prefix is the host prefix — a bare-address attribute never accepts a slash.
- **Leading/trailing whitespace and case**: values are normalised to a canonical
  representation (e.g. compressed IPv6) consistently across interfaces.
- **Kind change on an existing attribute**: changing an existing attribute's kind to or
  from `IPAddress` follows the existing generic attribute-kind-change path; values that
  do not fit the new kind (e.g. an `IPHost` value carrying a real prefix) surface as a
  validation error via the normal schema-migration validators. No bespoke bulk migration
  tool is provided (see Out of Scope).
- **Empty / optional**: an optional `IPAddress` attribute may be null; a required one
  must have a valid bare address.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a new attribute kind `IPAddress`, selectable in a
  node/generic schema alongside the existing `IPHost` and `IPNetwork` kinds.
- **FR-002**: The system MUST accept any valid IPv4 or IPv6 address as an `IPAddress`
  value.
- **FR-003**: The system MUST reject prefix/CIDR notation (any value containing a `/`,
  including host prefixes `/32` and `/128`) for an `IPAddress` value, with a clear
  validation error.
- **FR-004**: The system MUST reject values that are not valid IP addresses.
- **FR-005**: The system MUST store `IPAddress` values without any prefix/netmask and
  MUST NOT append an implicit `/32` or `/128`.
- **FR-006**: The system MUST return `IPAddress` values as bare addresses, identically,
  through the Web UI, the GraphQL API, and the Python SDK.
- **FR-007**: HFIDs and display labels that include an `IPAddress` attribute MUST contain
  the bare address, and an HFID returned by a query MUST be usable directly as lookup
  input without adding or removing a mask.
- **FR-008**: The Web UI MUST let a user enter and edit an `IPAddress` value without any
  prefix-length selector, and MUST display the value without a prefix.
- **FR-009**: The Python SDK MUST expose `IPAddress` (and its optional variant) as a
  typed attribute whose value is a bare address object (no prefix), and MUST serialise it
  to a bare-address string when writing.
- **FR-010**: Existing `IPHost` and `IPNetwork` attribute kinds MUST continue to behave
  exactly as before (values, prefixes, filters, HFIDs) with no regression.
- **FR-011**: The system MUST support equality filtering of nodes by an `IPAddress`
  attribute value.
- **FR-012**: Newly created Infrahub databases and existing databases upgraded to this
  version MUST have the storage/index structures required for `IPAddress` in place (via
  the normal graph-migration/upgrade path) without manual intervention.

### Key Entities *(include if feature involves data)*

- **IPAddress attribute kind**: a schema attribute kind representing a single bare IP
  address (IPv4 or IPv6), with no subnet/prefix context. Distinct from `IPHost` (address
  + prefix) and `IPNetwork` (network + prefix). Used for IP data on arbitrary schema
  nodes; not part of Infrahub's IPAM node/pool/hierarchy features.
- **IPAddress value**: the stored datum — a canonical bare IP address string plus derived
  data needed for validation and querying (IP version and a binary form for
  range/containment queries), never a prefix.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema author can define an `IPAddress` attribute and a data author can
  create an instance with a bare address in under 2 minutes using only the Web UI, with
  no prefix ever shown or required.
- **SC-002**: 100% of round-trips of a given `IPAddress` value return the identical bare
  address across all three interfaces (Web UI, GraphQL, Python SDK).
- **SC-003**: 100% of prefix-notation inputs (e.g. `10.0.0.1/24`, `10.0.0.1/32`,
  `2001:db8::1/128`) to an `IPAddress` attribute are rejected; 100% of valid bare IPv4
  and IPv6 inputs are accepted.
- **SC-004**: Zero regressions in existing `IPHost` and `IPNetwork` behaviour, as
  demonstrated by the existing test suites continuing to pass plus new cross-kind
  round-trip verification.
- **SC-005**: An existing Infrahub instance upgraded to this version can use `IPAddress`
  immediately with no manual database steps.

## Assumptions

- **A-001** (DB storage design — decided): `IPAddress` is stored via a dedicated
  `AttributeIPAddress` graph representation with its own index and query path, mirroring
  the existing `AttributeIPHost` machinery (IP version + binary form for range queries)
  rather than reusing the `IPHost` storage. This is a deliberate design decision, not an
  open question.
- **A-002** (cross-repo delivery — decided): the change spans the main Infrahub repo
  (backend + frontend) and the Python SDK (separate repository, based on the SDK's
  `infrahub-develop` branch). All three are delivered together; the SDK change ships as
  its own pull request, and the Infrahub submodule pointer is only advanced after the SDK
  change is merged upstream.
- **A-003** (target release): the work targets Infrahub 1.11 and is branched from
  `develop`.
- **A-004** (validation source of truth): IP validity and prefix rejection are enforced
  by the backend; the frontend relies on backend validation (matching how `IPHost` works
  today) and is not required to add a bespoke client-side validator.
- **A-005** (IPAM independence): `IPAddress` is purely an attribute kind and has no
  relationship to Infrahub's IPAM built-in nodes, pools, or hierarchy.

## Out of Scope

- Dedicated data-migration tooling to bulk-convert existing `IPHost` `/32` or `/128`
  attributes into `IPAddress`. The generic attribute-kind-change path continues to work
  for a manual per-attribute change, but no bespoke bulk migration tool is built in this
  cycle (open question in the ticket, deferred).
- Any changes to Infrahub's IPAM features or built-in IP nodes.
- New address-range/containment *filter* semantics beyond what `IPHost` already offers
  (equality filtering is in scope; richer IP filters are only a P3 parity nice-to-have).
