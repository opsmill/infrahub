# Feature Specification: User-Facing Schema Separation

**Feature Branch**: `user-facing-schema-infp-234`

**Created**: 2026-07-01

**Status**: Draft

**Input**: PRD `PRD-user-facing-schema-separation.md` + resolved field mapping `schema-field-classification.md` (repo root). Jira: INFP-234.

## Overview

Infrahub lets users define their own data models by submitting a schema. Today the
document that describes what a user may submit (the "user-facing schema") is a
direct dump of Infrahub's internal schema model. That has two consequences: it
advertises fields the user is not meant to set (so users set them and break their
schema), and it describes constrained fields as free-form text (so users and
automated tools cannot know the allowed values). This feature separates the
user-facing schema from the internal one so that what a user is shown is exactly
what a user may provide, with every constrained field publishing its allowed
values, and anything a user must not set rejected on submission.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Author a valid schema unassisted, first try (Priority: P1)

An automated agent (or a person using one) obtains the description of what a
schema may contain, produces a schema, and submits it. Because the description
lists exactly which fields exist and, for each constrained field, the exact set of
allowed values, the agent can produce a correct schema without trial and error. If
it does get something wrong, the rejection tells it precisely which field is at
fault so it can self-correct.

**Why this priority**: This is the strategic driver — enabling reliable
schema generation (including by LLMs) is the reason the work was prioritised.
Everything else in the feature is in service of, or a by-product of, making the
authoring contract complete and correct.

**Independent Test**: Fetch the published write-schema description, generate a
schema payload from it alone, submit it, and confirm it loads. Separately, submit
a payload containing a field the user is not allowed to set and confirm the
response names that field. Delivers value on its own even if nothing else ships.

**Acceptance Scenarios**:

1. **Given** the published description of a submittable schema, **When** an author
   generates a schema payload using only that description and submits it, **Then**
   the payload loads successfully because every field it used exists and every
   constrained value it chose was within the published allowed set.
2. **Given** a schema payload that includes a field the user is not permitted to
   set (e.g. `inherited`) and an unknown field, **When** it is submitted, **Then**
   it is rejected with a field-level, machine-readable error that names each
   offending field, and nothing is stored.
3. **Given** a schema payload that sets a constrained field to a value outside its
   allowed set (e.g. an attribute `kind` that does not exist), **When** it is
   submitted, **Then** it is rejected with an error identifying the field and the
   invalid value.

---

### User Story 2 - Validate a schema locally, with no server (Priority: P2)

A developer or an automated pipeline checks a schema for correctness before any
server is involved — in CI, on a laptop, or inside an agent loop — using only the
client library. The library gives the same field-and-value verdict the server
would give, so a schema that passes locally is not rejected by the server for
field or allowed-value reasons.

**Why this priority**: Independently shippable and independently valuable: it
shortens the authoring feedback loop and removes a network round-trip, and it is
what makes the P1 flow cheap to iterate on. It depends on the same contract as P1
but delivers value even if the server-side rejection work were deferred.

**Independent Test**: In an environment where only the client library is installed
(no server, no backend), validate a good schema (passes) and a bad one (fails
naming the field), and confirm the local verdict matches the server's for the same
payloads.

**Acceptance Scenarios**:

1. **Given** only the client library is installed and no server is running,
   **When** a well-formed schema is validated locally, **Then** validation passes.
2. **Given** the same environment, **When** a schema containing a non-settable
   field or an out-of-range constrained value is validated locally, **Then**
   validation fails and names the offending field — matching what the server would
   return for that payload.

---

### User Story 3 - Stop being able to set fields that break Infrahub (Priority: P2)

A human author maintaining a schema by hand no longer sees internal, system-managed
fields presented as things they can set. Fields the system derives (such as whether
an attribute was inherited from a generic) are visible when reading a schema back
but are refused on submission, so the author cannot accidentally corrupt their
model by setting them.

**Why this priority**: Directly removes a known source of customer friction and
support load. It shares the same mechanism as P1 (the classification of every
field) but is framed around the human-authoring benefit.

**Independent Test**: Read back an existing schema and confirm derived fields are
present; submit a schema that tries to set one of those derived fields and confirm
it is refused.

**Acceptance Scenarios**:

1. **Given** an existing schema, **When** it is read back, **Then** system-derived
   fields (e.g. `inherited`, `used_by`) are present and clearly not settable.
2. **Given** a submission that sets a system-derived field, **When** it is
   submitted, **Then** it is refused with a field-level error.

---

### Edge Cases

- **Read-modify-write round-trip**: A client reads a schema, edits one field, and
  re-submits the whole document. The read document contains visible-but-not-settable
  fields, so the re-submission is now rejected. This is an accepted behavioural
  change this cycle; the convenience export that would make round-tripping painless
  is explicitly deferred (see Out of Scope). Clients that round-trip must remove
  non-settable fields before submitting, using the published write description to
  know which those are.
- **Derived kind field**: The submittable schema derives an object's kind from its
  namespace and name. This derivation must continue to work under the new write
  model (the derived value is not something the user supplies).
- **Schema extensions**: A submission that extends existing objects (rather than
  defining new ones) is subject to the same rejection rules as a submission that
  defines new nodes or generics.
- **Reading historical schemas**: A previously stored schema may contain fields now
  classified as read-only-to-user. Reading it back must still succeed (the read
  view is a superset of the write view).
- **Version skew**: Local (client-side) validation may run against a different
  schema version than the server currently has. The version identifier carried on
  the submission is the compatibility anchor; local validation is advisory and the
  server remains authoritative.
- **Unclassified new field**: A newly added schema field with no explicit
  visibility must not leak to users — it defaults to internal (hidden) until
  someone deliberately classifies it.

## Requirements *(mandatory)*

### Field visibility model

Every field in the schema definitions is assigned one visibility level:

- **write** — the user may set it; accepted on submission; also visible on read.
- **read** — visible when reading a schema back, but refused on submission.
- **internal** — never exposed to users at all.

The levels are nested: `write ⊆ read ⊆ internal`. An unclassified field defaults to
**internal**. The complete, resolved per-field assignment is recorded in
`schema-field-classification.md` and is the authoritative mapping for this feature.
Notable resolved decisions carried into the requirements:

- `state` (on nodes, attributes, relationships) is **write** — it is a legitimate
  load directive (present/absent) that users submit, e.g. to remove an element.
- Node `hierarchy` and relationship `hierarchical` are **read** — both are derived
  from hierarchy/generic inheritance, not authored by the user.
- Relationship `identifier` is **write** — auto-generated when omitted but a user
  may set it to align both directions of a relationship.
- The read-only-to-user set is `inherited` (attributes and relationships),
  `used_by` (generics), and the two derived hierarchy fields above.
- The only never-exposed field is the parent back-reference from an attribute or
  relationship to its owning node (it is implied by nesting, never in a payload).
- Deprecated fields (`default_filter`, `display_labels`, and attribute
  `regex`/`min_length`/`max_length`) remain **write** this cycle.

### Functional Requirements

- **FR-001**: The schema-generation process MUST produce three distinct model sets
  from the single field-definition source: a **write** model (what a submission may
  contain), a **read** model (what a read-back returns), and the existing internal
  model. *Verify:* the generated output contains three model families and
  regeneration produces byte-identical output (idempotent).
- **FR-002**: Every schema field MUST carry a visibility classification of
  `write`, `read`, or `internal`; a field with no explicit classification MUST be
  treated as `internal`. *Verify:* a field left unclassified appears only in the
  internal model; classified fields appear in exactly the models their level
  implies.
- **FR-003**: A submission MUST be rejected if it contains any field that is not
  `write`-level (i.e. `read`, `internal`, or unknown), and the rejection MUST name
  each offending field in a machine-readable form. Nothing from a rejected
  submission is stored. *Verify:* a submission containing `inherited` plus an
  unknown field is rejected and both field names appear in the response.
- **FR-004**: Every field whose allowed values are already known internally (an
  enumeration or otherwise bounded set) MUST publish that allowed-value set in the
  write and read models, across the node, generic, attribute, and relationship
  families. *Verify:* the write model for attribute `kind` and relationship
  `kind`/`cardinality` (and every other enumerated field) publishes its full
  allowed-value set; an automated scan finds no field described as free-form text
  where a bounded set is defined internally.
- **FR-005**: A submission that sets a `write`-level constrained field to a value
  outside its published allowed set MUST be rejected, naming the field and the
  invalid value. *Verify:* a submission with a non-existent attribute `kind` is
  rejected identifying the field and value.
- **FR-006**: The read model MUST include `read`-level fields and MUST exclude
  `internal` fields. *Verify:* a read-back returns `inherited`/`used_by`; it never
  returns the internal parent back-reference or any unclassified field.
- **FR-007**: The write and read models MUST be usable by the client library with
  no server and no backend package present, enabling fully local validation.
  *Verify:* in an environment with only the client library installed, a schema can
  be validated and the correct pass/fail verdict returned.
- **FR-008**: The server MUST validate submissions and produce read-backs using the
  same models the client library uses — not a separate server-side copy — so the
  local and server verdicts cannot diverge for field and allowed-value rules.
  *Verify:* the same payload yields the same field/allowed-value verdict locally and
  on the server; a change to the shared model changes both behaviours.
- **FR-009**: The client library's previous hand-maintained schema models MUST be
  replaced by the generated write/read models, leaving no second, parallel
  definition of the same concepts. *Verify:* the former hand-written model classes
  are gone and the library's callers use the generated models.
- **FR-010**: Reading back a schema that was stored before this change — including
  one that contains fields now classified `read` — MUST continue to succeed.
  *Verify:* a stored schema containing a now-`read` field is read back without
  error.
- **FR-011**: The change MUST ship with a changelog entry and an upgrade note that
  document the stricter submission behaviour (previously-accepted non-settable
  fields are now rejected) and tell clients how to produce a submittable payload
  (strip non-settable fields using the published write description). *Verify:* a
  changelog fragment exists for this change and the upgrade note names the affected
  endpoint and the client-side mitigation.
- **FR-012**: The generated write and read models MUST be committed, version-
  controlled artifacts shipped inside the published client library package (not
  build-time-only), so a consumer installing only the library obtains them.
  *Verify:* the client library's own checks confirm the generated models are present
  and non-stale, and a consumer install exposes them without any generation step.

### Key Entities

- **Field visibility classification** *(new)*: metadata attached to every schema
  field declaring its level (`write`/`read`/`internal`). It is the single control
  that decides what users may set, see, or never see. Governance-relevant.
- **Write model** *(new, external)*: the exact shape of a valid submission; the
  authoring contract. Hosted so the client library can use it without a server.
- **Read model** *(new, external)*: the shape returned when reading a schema back;
  a superset of the write model that adds visible-but-not-settable fields.
- **Internal model** *(existing)*: the full model used inside the server;
  unchanged in shape, now the source from which the two external models are derived.
- **Schema families** *(existing)*: node, generic, attribute, and relationship
  definitions — each gains per-field classifications and each produces its own
  write/read projection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The write model exposes zero fields the user is not allowed to set —
  every field it contains is settable.
- **SC-002**: Zero constrained fields are described as free-form where a bounded
  set of allowed values is already defined internally (100% of known allowed-value
  sets are published).
- **SC-003**: 100% of submissions containing a non-settable or unknown field are
  rejected with a field-level error that names the field; zero are silently
  accepted or partially stored.
- **SC-004**: An author working only from the published write description produces
  a valid, loadable schema across a representative benchmark set at or above a
  target first-attempt success rate. *(Target rate to be set with product; see Open
  Questions.)*
- **SC-005**: A schema can be validated with only the client library present (no
  server), and the local verdict matches the server's for every field and
  allowed-value rule across a shared test set.
- **SC-006**: Every schema previously loadable remains loadable, and every stored
  schema remains readable — no regression in existing authoring or read-back flows
  beyond the intended rejection of non-settable fields on submission.

## Assumptions

- The visibility levels are strictly nested (`write ⊆ read ⊆ internal`); there is
  no field a user must submit but must not be able to read back.
- The dominant way users author schemas is by writing submittable (write-shaped)
  documents directly; reading a full schema and re-submitting it unchanged is a
  minority path (see the round-trip edge case and Out of Scope).
- The internally defined allowed-value sets are authoritative and complete at the
  time the models are generated.
- The client library is already a runtime dependency of the server, so the server
  can use the library-hosted models, and the generation process can target the
  library.
- The resolved field classification in `schema-field-classification.md` is correct
  for this cycle; the remaining ambiguous fields have been decided (see the field
  visibility model above).

## Out of Scope

- A convenience export that returns a write-shaped schema (excluding
  read-only-to-user fields and omitting defaulted values) to make read-modify-write
  round-trips painless. Deferred — it needs value-provenance tracking.
- Making specific attribute kinds (computed attributes, number pools) read-only by
  default — a defaults-and-conditional-validation problem tracked separately.
- Updating the separate schema-visualizer consumer to the new models — assessed
  after these models land.

## Dependencies & Governance

- **API / public interface change** — the submission endpoint becomes stricter
  (breaking for payloads that carry non-settable fields) and the read-back shape
  changes. Requires the "ask first" governance discussion before implementation.
  Must ship with a changelog fragment and an upgrade note (FR-011).
- **Generated files + client-library changes** — regeneration produces new/changed
  generated models in both the backend and the client library; both must be
  regenerated and committed together, and CI must validate them on both sides. The
  client-library models are committed, shipped artifacts (FR-012).
- **Server/client release compatibility** — server and client library now ship the
  same generated contract; they must be released compatibly. The `version` field on
  a submission is the compatibility anchor; client-side local validation is advisory
  and the server remains authoritative on skew.
- **`id`-driven mutations** — because object `id` is user-settable (to rename/delete
  an existing object), implementation MUST confirm existing authorization and branch
  scoping prevent an `id` in a payload from targeting an object the caller may not
  modify; this MUST be covered by a test.
- **No database, dependency, or authentication changes** (the authorization check
  above reuses existing controls; it introduces no new auth model).

## Open Questions

- [NEEDS CLARIFICATION: SC-004 target first-attempt success rate and the benchmark
  task set used to measure it — needs product input.]
