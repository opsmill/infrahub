# Feature Specification: Bare IP addresses on IPHost attributes

**Feature Branch**: `bare-ip-attribute-infp-551`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Implement bare IP addresses on IPHost attributes via a new `IPHostAttributeParameters.allow_prefix` flag, per the PRD at `bare-ip-attribute-prd.md` and the code-confirmed idea brief at `bare-ip-attribute.md`."

**Source of truth**: `bare-ip-attribute-prd.md` (PRD) and `bare-ip-attribute.md` (code-confirmed idea brief), both in the repository root. Ticket: [INFP-551](https://opsmill.atlassian.net/browse/INFP-551).

## Problem Statement

Schema authors modelling infrastructure data frequently need to store an IP address that has no
subnet context — DNS A/AAAA records, NTP/syslog/SNMP server addresses, anycast VIPs, ACL
source/destination entries, monitoring poll targets, load balancer pool members. Infrahub offers no
way to express that. `IPHost` silently attaches a `/32` or `/128` the author never intended, and
`Text` discards IP validation entirely.

Since the fix for the mask-inconsistency bug (issue #8896) normalised `IPHost` values to their
prefixed form at input time, that invented mask now appears consistently on *every* surface — it
removed the one place customers previously saw a clean address. The prefix is data customers neither
want nor need, and today the only way to hide it is per-schema and per-consumer workarounds
(`mgmt_ip { ip }` in GraphQL, `display_label: "mgmt_ip__ip"`,
`human_friendly_id: ["mgmt_ip__ip"]`, `node.mgmt_ip.value.ip` in the SDK) that must be repeated
forever.

## Solution Overview

An `IPHost` attribute can be declared to hold a bare address, via an `allow_prefix: false`
parameter. When it is, Infrahub rejects input carrying a real subnet prefix, accepts a bare address
or a redundant host mask, and stores and returns the address with no mask on every surface — API
responses, human-friendly identifiers, display labels, uniqueness comparisons, the UI, and the SDK.
The schema author declares the intent once; nothing downstream needs to strip anything.

Two properties are deliberate:

1. This reuses the existing `IPHost` kind rather than adding a new attribute kind, so there is no
   new graph storage type, no graph-version bump, and no data migration.
2. The declaration is immutable once an attribute exists: it can be set when an attribute is created
   but not toggled afterwards. That restriction is what makes the feature migration-free, and
   lifting it is tracked as follow-up work rather than being quietly unsupported.

This reverses an earlier in-flight approach that added a separate `IPAddress` attribute kind (PR
#9970, SDK PR #1190). That approach could not deliver the conversion path customers actually need,
and its reverse conversion corrupted data silently. See "Why this reverses the in-flight approach".

## User Scenarios & Testing *(mandatory)*

### Stakeholder Needs

The 16 needs carried from the PRD, each traced to the requirement that satisfies it:

| # | Need | Traces to |
|---|------|-----------|
| 1 | As a schema author, I want to declare that an IP attribute holds a bare address, so that the schema records my intent instead of my consumers guessing it. | FR-001 |
| 2 | As a schema author, I want a bare-address attribute to reject a value carrying a subnet prefix, so that bad data is refused at the boundary rather than discovered later. | FR-003 |
| 3 | As a schema author, I want a redundant host mask on input to be accepted and normalised away, so that data imported from systems that always emit `/32` loads without pre-processing. | FR-004 |
| 4 | As an automation engineer, I want API responses to return the address with no mask, so that I do not write mask-stripping logic in every consumer. | FR-005 |
| 5 | As an automation engineer, I want a human-friendly identifier returned by a query to work as-is when I feed it back into a lookup, so that read-then-write automation does not break. | FR-006 |
| 6 | As an automation engineer, I want the Python SDK to hand me a bare address object, so that the type I receive matches the field's declared meaning. | FR-011 |
| 7 | As an automation engineer, I want generated SDK protocols to type the attribute as a bare address, so that type checking catches misuse before runtime. | FR-011 |
| 8 | As a schema author, I want display labels built from a bare-address attribute to show no mask, so that object lists read the way operators expect. | FR-006 |
| 9 | As a schema author, I want a uniqueness constraint on a bare-address attribute to compare real addresses, so that the same address cannot be stored twice under different notations. | FR-007 |
| 10 | As an operator, I want the edit form for a bare-address attribute to have no prefix-length control, so that the UI does not invite input the field will reject. | FR-010 |
| 11 | As an operator, I want the detail and list views to display the address with no mask, so that what I see matches what the API returns. | FR-005 |
| 12 | As an operator, I want a rejected value to produce an error naming the attribute and explaining that a prefix is not permitted, so that I can fix it without guessing. | FR-003 |
| 13 | As a schema author, I want the declaration to be rejected on attribute kinds where it is meaningless, so that I learn at schema-load time rather than by observing no effect. | FR-002 |
| 14 | As a schema author, I want an attempt to toggle the declaration on an existing attribute to fail with a clear explanation, so that I am not left with data and schema disagreeing. | FR-009 |
| 15 | As a platform maintainer, I want existing `IPHost` attributes to behave exactly as before, so that adopting this feature carries no regression risk for current schemas. | FR-012 |
| 16 | As a platform maintainer, I want no graph migration and no stored-value rewrite in this change, so that upgrades stay boring. | FR-008, SC-005 |

### User Story 1 - Author and populate a bare-address attribute (Priority: P1)

A schema author declares an `IPHost` attribute as holding a bare address, loads data through the API
or SDK, and every read path returns the address with no mask. Input carrying a real subnet prefix is
refused with an error naming the attribute.

**Why this priority**: This is the whole user value. API and SDK consumption is the primary path, so
this journey ships alone and is independently useful without any UI work. It also carries the
guarantees that make the feature migration-free.

**Independent Test**: Fully testable by loading a schema with a bare-address attribute, creating
nodes through the API in each input form, and asserting the stored value, API response, display
label, and human-friendly identifier — no UI and no SDK change required.

**Acceptance Scenarios**:

1. **Given** a schema whose `dns_target` attribute is an `IPHost` declared to hold a bare address, **When** a node is created with `dns_target` set to `10.0.0.1`, **Then** the stored value, the API response, the display label, and the human-friendly identifier are all `10.0.0.1`.
2. **Given** the same schema, **When** a node is created with `dns_target` set to `10.0.0.1/32`, **Then** the stored value and all read surfaces are `10.0.0.1` — indistinguishable from scenario 1.
3. **Given** the same schema, **When** a node is created with `dns_target` set to `10.0.0.1/24`, **Then** the request fails with a validation error naming `dns_target` and explaining that a prefix is not permitted.
4. **Given** the same schema with an IPv6 bare-address attribute, **When** a node is created with `2001:db8::1/128`, **Then** the stored value is `2001:db8::1`; **And When** created with `2001:db8::1/64`, **Then** the request fails.
5. **Given** a bare-address attribute holding `10.0.0.1`, **When** the human-friendly identifier returned by a query is fed back verbatim as lookup input, **Then** the lookup resolves the same node with no caller-side transformation.
6. **Given** a bare-address attribute with a uniqueness constraint, **When** one node is created with `10.0.0.1` and a second with `10.0.0.1/32`, **Then** the second violates the uniqueness constraint.
7. **Given** an existing schema with an undeclared `IPHost` attribute, **When** any of the above operations are performed on it, **Then** behaviour is exactly as it is today, including the prefixed stored form.
8. **Given** a schema declaring the bare-address flag on a `Text` attribute, **When** the schema is loaded, **Then** loading fails with a validation error at schema-load time.
9. **Given** an existing attribute already declared bare-address, **When** a schema update attempts to remove or flip the declaration, **Then** the update fails with an unsupported-change error identifying the declaration.

---

### User Story 2 - Operate on it in the UI (Priority: P2)

An operator edits and views a bare-address attribute without ever meeting a prefix control or a
mask.

**Why this priority**: The UI is the secondary path. This journey ships after P1 and depends on P1's
schema contract being available to the frontend, but it is separately demonstrable and separately
valuable to operators who do not use the API directly.

**Independent Test**: Fully testable by pointing the UI at a node whose schema has a bare-address
attribute and exercising the edit form, detail view, and list view.

**Acceptance Scenarios**:

1. **Given** a node with a bare-address attribute, **When** the operator opens the edit form, **Then** the input offers no prefix-length control.
2. **Given** a node whose bare-address attribute was entered as `10.0.0.1/32`, **When** the operator views the detail view and the list view, **Then** every rendering of the value shows `10.0.0.1` with no mask.
3. **Given** a node with an undeclared `IPHost` attribute, **When** the operator opens the edit form and views the value, **Then** the prefix-length control and the mask are present exactly as today.
4. **Given** the edit form for a bare-address attribute, **When** the operator submits a value carrying a real subnet prefix by any means available to them, **Then** an error naming the attribute is surfaced.

---

### User Story 3 - Consume it through the Python SDK (Priority: P3)

An SDK consumer reads the attribute and receives a bare address object, and generated protocols type
it as a bare address rather than as an interface type.

**Why this priority**: Labelled P3 because it is the narrowest slice, but it **ships with P1**: the
PRD requires it alongside the backend work, because without it the SDK re-attaches the host mask to
a bare stored value and contradicts FR-005 and FR-011. It is cross-repo — the SDK change must land
and be available upstream before the submodule pointer moves.

**Independent Test**: Fully testable by fetching a node with a bare-address attribute through the
SDK and asserting the returned value's type, plus a protocol-generation test asserting the emitted
annotation.

**Acceptance Scenarios**:

1. **Given** a node with a bare-address attribute, **When** it is fetched through the SDK, **Then** the attribute value is a bare address object rather than an interface object carrying `/32`.
2. **Given** a node with an undeclared `IPHost` attribute, **When** it is fetched through the SDK, **Then** the attribute value is still an interface object, unchanged from today.
3. **Given** a schema with a bare-address attribute, **When** SDK protocols are generated, **Then** the attribute carries the bare-address type annotation; **And** an undeclared `IPHost` attribute still carries the interface annotation.
4. **Given** a schema fetched through the schema API, **When** an `IPHost` attribute's parameters are inspected, **Then** the declaration is visible to the SDK generator and the frontend.

---

### Edge Cases

- A redundant host mask (`/32`, `/128`) on input is accepted and normalised away; **any** other
  prefix length, including `/31` and `/0`, is rejected.
- After a write, a value entered bare and a value entered with a host mask are indistinguishable —
  they converge on one stored value and one shared value record. Nothing downstream may depend on
  recovering which form was supplied; the input-time rejection is the only surviving prefix signal.
- Because the two forms converge, two branches setting `10.0.0.1` and `10.0.0.1/32` produce **no**
  merge conflict. This is intended and must be asserted rather than left to chance.
- Changing an attribute's kind away from `IPHost` **silently discards** the declaration, because
  parameter conversion drops fields the target kind does not define — leaving bare values in, for
  example, a `Text` field. For v1 this silence is accepted and documented; surfacing it would
  require new machinery, and conversions away from `IPHost` already lose IP-specific storage
  properties.
- An optional bare-address attribute with no value applies no prefix logic.
- A bare-address attribute's **declared default value** goes through the same rules as a node value: a
  redundant host mask is normalised away in the schema itself, and a non-host prefix is rejected when
  the schema loads rather than when the first node is created. Without this, the schema would advertise
  a default carrying a mask while every node created from it stored a bare address.
- Profile and template nodes inheriting a bare-address attribute must validate and serialise
  identically to the node they derive from.
- Computed attributes and templates that reference a bare-address attribute receive the bare value.
- An attribute declared bare-address on a branch and then merged must carry the declaration **and**
  its validation behaviour to the target branch.
- A prefix-length filter on a bare-address attribute still resolves, returning the derived host
  length (`32`/`128`). Coherent, but arguably surprising on a field declared to have no prefix —
  resolved deliberately in Assumptions.
- A value-equality filter on a bare-address attribute must match bare input, because the stored
  value is bare.
- A bare-address `IPHost` attribute holding `10.0.0.1` must not collide with a `Text` attribute
  holding the string `10.0.0.1` — they remain distinct stored values.
- Latent duplicates are not reachable in v1 because no pre-existing data can carry the declaration,
  but the follow-up conversion work must run the prefix constraint and the uniqueness check
  together, since correcting a `/24` row to a host address can collide with an existing row.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Schema authors MUST be able to declare an `IPHost` attribute as holding a bare
  address. *Verify*: a schema declaring it loads successfully.
- **FR-002**: The declaration MUST be unreachable on any attribute kind other than `IPHost` — it MUST
  have no effect there and MUST NOT be settable through a typed parameters object.
  *Verify*: attaching an `IPHostAttributeParameters` instance to another kind produces a validation
  error; declaring `allow_prefix` as a plain mapping on a text attribute loads with the flag dropped.

  **As-built deviation from user story 13**: declaring the flag as a plain mapping on another kind is
  *silently dropped*, not rejected, so an author learns by observing no effect rather than at
  schema-load time. This is pre-existing behaviour for every attribute parameter — the mapping is
  coerced to the attribute kind's own parameters model, which filters unknown keys before
  `extra="forbid"` can reject them — and changing it would change the contract of every parameter, not
  just this one. The behaviour is pinned by a test so any future change is deliberate. Making the
  forward direction actually reject is out of scope for this feature.
- **FR-003**: System MUST reject a value carrying a non-host subnet prefix on a bare-address
  attribute, with an error naming the attribute. *Verify*: `10.0.0.1/24` and `2001:db8::1/64` are
  both refused; the error text names the attribute.
- **FR-004**: System MUST accept a bare address or a redundant host mask on a bare-address
  attribute, and MUST store the value with no mask. *Verify*: `10.0.0.1` and `10.0.0.1/32` both
  store `10.0.0.1`; `2001:db8::1/128` stores `2001:db8::1`.
  This applies to an attribute's **declared default value** as well as to node values: a default of
  `10.0.0.1/32` MUST be stored in the schema as `10.0.0.1`, so the default the schema advertises is
  the value nodes actually receive. A default carrying a non-host prefix MUST be rejected at
  schema-load time (FR-003). *Verify*: a schema declaring `default_value: "10.0.0.1/32"` on a
  bare-address attribute loads with the default recorded as `10.0.0.1`; one declaring
  `default_value: "10.0.0.1/24"` fails to load.
- **FR-005**: System MUST return the value with no mask on every read surface — API responses
  (GraphQL and REST), the UI, and the SDK. *Verify*: each surface returns `10.0.0.1` for a value
  entered as `10.0.0.1/32`.
- **FR-006**: Human-friendly identifiers and display labels derived from a bare-address attribute
  MUST carry no mask, and an identifier returned by a query MUST be accepted verbatim as lookup
  input. *Verify*: a read-then-lookup round trip succeeds with no caller-side transformation.
- **FR-007**: Uniqueness comparisons on a bare-address attribute MUST compare addresses without
  masks. *Verify*: two nodes created with `10.0.0.1` and `10.0.0.1/32` violate a uniqueness
  constraint on that attribute.
- **FR-008**: System MUST retain the derived prefix length internally rather than clearing it, so
  that address-range and prefix-containment behaviour is unchanged. The derived prefix length MUST
  remain populated (`32`/`128`) and MUST NOT be null. *Verify*: a bare-address attribute's value is
  still returned by a prefix-containment query, and its stored derived prefix length is `32` for
  IPv4.
- **FR-009**: System MUST reject any attempt to add, remove, or toggle the declaration on an
  existing attribute, with an error identifying the declaration. *Verify*: a schema update flipping
  it fails with an unsupported-change error naming the declaration.
- **FR-010**: Users MUST be able to edit a bare-address attribute through a form with no
  prefix-length control. *Verify*: the edit form for such an attribute renders no prefix input.
- **FR-011**: The SDK MUST expose the value as a bare address object, and generated protocols MUST
  type it as one. *Verify*: an SDK fetch returns a bare address object; generated protocol output
  carries the bare-address annotation.
- **FR-012**: Existing `IPHost` attributes MUST be unaffected in validation, storage, and every read
  surface. *Verify*: the existing `IPHost` test suites pass unchanged.
- **FR-013**: The published schema contract MUST expose the declaration so that the SDK and the
  frontend can read it. *Verify*: a schema fetch includes it for an `IPHost` attribute.

### Key Entities

- **`IPHost` attribute kind** *(existing, extended)*: gains one optional declaration. Its graph
  storage type and derived properties are unchanged; only the stored value string differs, and only
  for attributes that opt in.
- **`IPHost` attribute parameters** *(new)*: the kind-specific parameters type that carries the
  declaration, joining the existing per-kind parameter types for text, number, list, and number pool
  attributes. The declaration is confined here rather than living on the generic attribute schema,
  which is what makes it unreachable on other kinds **by construction** rather than merely validated
  away.
- **`IPHost` attribute schema** *(new)*: the per-kind attribute-schema type that carries the typed
  parameters, mirroring the existing per-kind attribute schemas.
- **Attribute value storage** *(existing, unchanged)*: no new graph value type, no new index, no
  graph-version change. Flagged for governance review: the internal schema gains a field, which
  produces a core-schema diff and regenerated artefacts.
- **Not created**: a new attribute kind, a new graph value-node label, a new range index, a
  graph-version bump. This is the deliberate reversal of the earlier approach.

### Constraints & Agreed Design Decisions

These are solution-shape constraints agreed in the PRD, not open design space. They bound scope and
are therefore requirements on any implementation:

- The existing `IPHost` kind is reused. No new attribute kind, no new graph storage type, no
  graph-version bump, no data migration.
- The declaration lives in a new kind-specific `IPHost` attribute parameters type, not on the generic
  attribute schema. This placement is load-bearing: it is what makes FR-002, FR-009, and FR-013 fall
  out of machinery that already exists.
- The declaration is immutable once an attribute exists (FR-009). This is what makes v1
  migration-free.
- The derived prefix length stays populated in storage (FR-008). Clearing it would silently exclude
  flagged rows from containment and range queries rather than raise an error.
- The stored value for a declared attribute is bare. This is required, not incidental: uniqueness
  and human-friendly identifiers can only compare the stored value, so bare storage is the only way
  FR-006 and FR-007 hold.
- Input-time normalisation for **undeclared** `IPHost` attributes stays exactly as it is today.
- Error handling reuses the existing attribute-validation error for a rejected prefix and the
  existing unsupported-schema-change error for an attempted toggle. No new error types.
- No new API endpoints, mutations, arguments, frontend routes, or SDK methods. Existing IPHost input,
  display, table-cell, and filter paths and existing SDK value coercion and protocol generation
  become declaration-aware.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every read surface — API response, UI display, display label, human-friendly
  identifier, and SDK value — returns the address with no mask, with zero consumer-side stripping.
  Today **four of those five** can only be cleaned up by a per-schema or per-consumer workaround
  (API field selection `mgmt_ip { ip }`, `display_label: "mgmt_ip__ip"`,
  `human_friendly_id: ["mgmt_ip__ip"]`, and SDK access `node.mgmt_ip.value.ip`), and the fifth —
  **UI display — has no workaround available at all**. This feature removes all four workarounds and
  fixes the UI.
- **SC-002**: A human-friendly identifier returned by a query is accepted verbatim as lookup input,
  requiring zero caller-side transformations.
- **SC-003**: Storing an address carrying a real subnet prefix in a bare-address attribute fails
  100% of the time, with an error that names the attribute.
- **SC-004**: A schema author needs exactly one declaration to get bare addresses everywhere,
  replacing the four separate workarounds required today (enumerated in SC-001) and fixing the one
  surface that cannot be worked around.
- **SC-005**: Adopting the feature requires zero graph migrations and changes zero stored values on
  existing attributes.
- **SC-006**: Existing schemas using `IPHost` observe no behaviour change whatsoever — the existing
  `IPHost` test suites pass unchanged.

## Testing Strategy

- **What makes a good test here.** Assert what a schema author or consumer observes — what is
  accepted, what is refused, and what comes back on each surface — never how normalisation is wired
  internally. Every test should pair a declared and an undeclared `IPHost` attribute, because the
  primary risk is regressing existing behaviour rather than failing to add new behaviour.
- **Unit tests**: the `IPHost` attribute class (validation and normalisation across bare input,
  redundant host mask, real subnet prefix, IPv4 and IPv6, and the undeclared path); the `IPHost`
  attribute parameters and attribute schema types (default value, rejection on other kinds, and the
  immutability classification the migration-free property depends on); SDK attribute value coercion
  (a bare value stays bare, an undeclared attribute still yields an interface object).
- **Integration / contract tests**: database round trip for a declared attribute; identifier
  round-trip lookup; uniqueness collision between the two input forms; prefix-containment query
  still returning a declared attribute's value; rejection of a schema update attempting a toggle;
  behaviour on profile and template nodes; branch-merge propagation of the declaration.
- **E2E scenario**: an operator creates a node whose bare-address attribute is entered as
  `10.0.0.1/32`, sees `10.0.0.1` in the list view, detail view, and display label with no prefix
  control anywhere in the form, then fetches the same node through the SDK and receives a bare
  address object.
- **Prior art**: `test_iphost_hfid_roundtrip_via_graphql` in
  `backend/tests/component/graphql/queries/test_hfid.py` is the reproduction written for the
  mask-inconsistency bug (issue #8896) and is the model to mirror for FR-006.

## Constitution Alignment

- **I. Schema-Driven Integrity**: supported. Intent becomes schema-expressible instead of implicit,
  and making the declaration immutable means no migration can leave data and schema disagreeing.
- **II. Branch-Safe by Default**: the merge behaviour of an attribute declared on a branch must be
  specified and tested before the feature is considered complete. Covered by an edge case, an
  acceptance scenario, and an integration test.
- **III. Type Safety & Explicit Contracts**: **pushes back**. The serialised form of an `IPHost`
  value becomes conditional on a parameter. Confining the declaration to kind-specific parameters
  keeps the *schema* contract properly typed — the declaration is unreachable on other kinds rather
  than merely validated away — and retaining the derived prefix length keeps the derived properties
  truthful rather than meaningless. FR-011 keeps the SDK from advertising a type it no longer
  returns. The residual deviation is deliberate and MUST be recorded in the plan and the PR.
- **IV. Test Discipline**: three unit suites, integration coverage for the database, identifier,
  uniqueness, and schema-update paths, and an E2E scenario for the user-visible flow.
- **VII. Simplicity & Maintainability**: the reason for this shape. One parameter on an existing kind
  replaces a new attribute kind plus a new graph storage type, index, migration, API type, and
  frontend component set. Extending the established per-kind parameters pattern is what this
  principle's "follow established project patterns" clause asks for, and it is what lets three of
  the requirements above fall out of machinery that already exists. Per Governance, the deviation
  from Principle III MUST be documented in the plan and PR.

## Governance Gates Crossed

- [x] **Database schema or migration change** — no graph migration and no graph-version bump, but the
  internal schema gains a field, producing a core-schema diff and regenerated artefacts. When
  testing `infrahub upgrade` locally, note the known Prefect flow-parameter size limit on
  core-schema diffs.
- [x] **GraphQL schema modification** — the attribute-parameters contract gains a field and the
  serialised value form becomes conditional; the generated schema, API contract, protocols, frontend
  types, and reference documentation all need regenerating. The generated schema models hosted in
  the SDK are covered by a CI-enforced no-diff check spanning the submodule.
- [ ] New dependency — none.
- [ ] CI/CD workflow change — none.
- [ ] Authentication / authorization change — none.

## Assumptions

Carried from the PRD:

- The immediate customer need is satisfied by declaring **new** attributes. Converting existing
  populated `IPHost` attributes is accepted as a manual exercise for v1.
- API and SDK consumption is the primary path; the UI is secondary, which is why P1 ships without P2.
- The existing input-time normalisation of undeclared `IPHost` values stays exactly as it is.
- The SDK change lands and is available upstream before the submodule pointer moves, per the
  repository's submodule rules.
- The earlier `IPAddress`-kind work is withdrawn rather than shipped alongside this. If both shipped,
  schema authors would face two overlapping ways to model the same thing.

Resolutions of the PRD's open questions, decided here so the feature can proceed:

- **Canonical stored form for IPv6 bare addresses**: the canonical form produced by the platform's
  existing IP handling — compressed, lowercase (RFC 5952) — is used, which is exactly today's
  undeclared `IPHost` output minus the mask. IPv4-mapped addresses keep that same canonical
  rendering. Host-bit normalisation does not arise, because only host masks (`/32`, `/128`) are
  accepted, so there are no host bits to mask off. Chosen because it introduces no new normalisation
  logic and keeps declared and undeclared attributes byte-identical apart from the mask.
- **Filter semantics on a bare-address attribute**: the prefix-length filter **remains available and
  functional**, returning the derived host length. Chosen because FR-008 requires the derived prefix
  length to stay populated, hiding the filter would require new per-attribute filter-suppression
  machinery (a Principle VII cost for no user gain), and suppressing it risks silently excluding
  flagged rows from containment queries. The value-equality filter matches bare input. The residual
  surprise is documented as an edge case.
- **Disposition of the in-flight `IPAddress`-kind pull requests**: treated as a coordination matter
  outside this specification. The specification assumes that work is withdrawn (see above). One
  consequence is in scope as a dependency, not a requirement: part of the SDK-side change has
  already merged, so the resulting dead code path must be cleaned up on the SDK side as part of this
  feature's SDK work.

## Dependencies

- **Cross-repo**: the SDK-side changes (value coercion, protocol generator, and cleanup of the
  already-merged dead `IPAddress` path) live in `infrahub-sdk-python`. The commit must be **pushed and
  fetchable** before the `python_sdk` submodule pointer moves in this repository, and must be
  **merged**, with the pointer moved to the merged commit, before this repository's pull request
  merges. The two reviews can therefore run concurrently rather than in series.
- **SDK version floor**: consuming a bare-address attribute requires an SDK at or above the version
  that ships this change. An **older** SDK reading a bare stored value re-attaches the host mask when
  it coerces the value, producing exactly the masked object FR-005 and FR-011 exist to prevent. This
  is unavoidable for that combination and must be documented rather than discovered. The reverse skew
  is safe: a newer SDK against a server that does not publish the declaration falls back to today's
  behaviour.
- **Generated artefacts**: the core schema diff requires regenerating the generated schema
  definitions, protocols, the GraphQL and OpenAPI contracts, frontend generated types, and the
  attribute-kinds reference documentation. CI enforces that these are committed.
- **Prior work**: the mask-inconsistency fix (issue #8896) is the direct cause of the pain this
  feature addresses, and its identifier round-trip reproduction is the model for FR-006's test.

## Out of Scope

- Toggling the declaration on an existing attribute. This is the agreed follow-up and the only
  sanctioned route to a fully-correct conversion; it requires relaxing the immutability
  classification, a stored-value rewrite, a recompute of stored identifiers and display labels, an
  index rebuild, and the prefix and uniqueness checks run together.
- A separate `IPAddress` attribute kind.
- Bulk data-migration tooling for existing masked attributes.
- Any change to `IPNetwork`.
- Any change to Infrahub's IPAM built-in models, which are a separate concern from attribute kinds.
- Surfacing the silent loss of the declaration when an attribute's kind changes away from `IPHost`.

## Why this reverses the in-flight approach

The earlier design added a distinct `IPAddress` attribute kind. Grilling established, against the
code, that the conversion customers actually need — an existing masked attribute becoming a bare one
— is hard-blocked, because the attribute-kind-change validator checks every existing value against
the new kind's rules and every stored `IPHost` value carries a mask. The reverse conversion is
worse: it passes validation and the migration does nothing, leaving an attribute whose value has no
mask and whose storage lacks its prefix length, silently breaking range behaviour. No mechanism
exists to permit or block specific kind transitions, so neither could be addressed without building
new machinery. The full evidence, with file references, is in `bare-ip-attribute.md`.
