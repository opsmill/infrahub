# Feature Specification: Schema Load Model Refactor

**Feature Branch**: `infp-234-user-facing-schema-refactor`
**Created**: 2026-03-10
**Status**: Draft
**Input**: Jira INFP-234: Refactor user-facing schema models generated from Infrahub's internal schema

## Overview

Infrahub has two distinct interactions with schema data:

- **Schema loading** (`/api/schema/load`): Users submit schema definitions to configure Infrahub. This is the *write path*.
- **Schema reading** (`/api/schema`): Users retrieve the current schema state from Infrahub. This is the *read path*.

Today, the write and read paths use the same underlying model. This creates two problems: internal-only fields that the system computes and manages (e.g., `inherited`, `used_by`) are exposed as if users can set them, and fields with a bounded set of valid values (e.g., attribute `kind`) accept arbitrary strings instead of showing the valid options. The enum metadata already exists in the source of truth but is not applied during load validation.

This feature introduces a dedicated **Schema Load Model** — a separate, generated definition for what a valid schema submission looks like — used exclusively on the write path. The read path (`/api/schema`) is **out of scope** and remains unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schema Load Rejects Internal-Only Fields (Priority: P1)

A schema author submits a schema via the load endpoint that includes a field the system computes and manages internally (e.g., `inherited` or `used_by`). The load is rejected immediately with a clear error identifying the offending field and stating it cannot be set by users.

**Why this priority**: This is the core correctness problem. These fields being silently accepted causes broken Infrahub state downstream. Immediate rejection with a clear message prevents misconfiguration at the source.

**Independent Test**: Can be tested by submitting a schema containing a known internal-only field to the load endpoint and verifying it is rejected with an informative error.

**Acceptance Scenarios**:

1. **Given** a schema definition that includes `used_by` on a generic, **When** it is submitted to the schema load endpoint, **Then** the load is rejected with an error identifying `used_by` as a field that cannot be set by users
2. **Given** a schema definition that includes `inherited` on an attribute, **When** it is submitted to the schema load endpoint, **Then** the load is rejected with an error identifying `inherited` as a field that cannot be set by users
3. **Given** a schema definition that uses only valid load model fields, **When** submitted, **Then** the load succeeds without errors related to internal-only fields
4. **Given** a schema is read back from the read endpoint after a successful load, **When** the user inspects the response, **Then** it includes system-computed fields such as `inherited` and `used_by` populated by the system

---

### User Story 2 - Enumerable Fields Validate Against All Valid Options (Priority: P2)

A schema author defines an attribute with `kind: InvalidKind`. Currently the load endpoint accepts the submission and the error surfaces later. After this change, the load model validates all enumerable fields — the submission is rejected immediately with the list of valid values shown in the error.

**Why this priority**: This directly reduces technically invalid schemas and unblocks LLM-based schema generation. The valid option lists are already defined in the system's source of truth; this feature ensures they are applied during load validation. It depends on the P1 infrastructure (a dedicated Schema Load Model) being in place.

**Independent Test**: Can be tested by submitting a schema with an invalid value for any enumerable field and confirming it is rejected at the load endpoint with valid options listed in the error message.

**Acceptance Scenarios**:

1. **Given** a schema definition with `kind: InvalidKind` on an attribute, **When** submitted to the load endpoint, **Then** the load is rejected with an error identifying the invalid value and listing the valid alternatives (e.g., `Text`, `Number`, `Boolean`, `Dropdown`, `IPHost`, `IPNetwork`, etc.)
2. **Given** a schema definition with an invalid `cardinality` value on a relationship, **When** submitted, **Then** the load is rejected with the valid cardinality options listed
3. **Given** a schema definition using valid values for all enumerable fields, **When** submitted, **Then** those fields pass validation
4. **Given** a schema author reads the Schema Load Model definition, **When** they inspect any enumerable field, **Then** they see the complete list of valid values for that field

---

### User Story 3 - LLM-Generated Schemas Are Valid by Default (Priority: P3)

A developer provides the Schema Load Model to an LLM and asks it to generate an Infrahub schema from a natural language description. Because the Load Model excludes internal-only fields and enumerates all valid options, the LLM produces a schema that passes load validation without manual correction.

**Why this priority**: This is a secondary benefit that flows directly from completing P1 and P2. It cannot be fully validated until both are in place.

**Independent Test**: Can be tested by providing only the Schema Load Model definition to an LLM, asking it to generate a schema for a simple use case, and submitting the result to the load endpoint without modification.

**Acceptance Scenarios**:

1. **Given** an LLM is provided only the Schema Load Model as context, **When** it generates an attribute with a `kind`, **Then** the generated kind value is a valid option from the enumerated list
2. **Given** an LLM generates a complete node schema using the Schema Load Model, **When** the schema is submitted to the load endpoint, **Then** it passes validation without errors related to internal-only fields or invalid enum values

---

### Out of Scope

- The schema read endpoint (`/api/schema`) is **not changed** by this feature. It continues to return the full schema including system-computed fields such as `inherited` and `used_by`.
- There is no requirement to hide or filter system-computed fields from read responses.

### Edge Cases

- A schema definition that omits an enumerable field entirely — is a missing `kind` valid or required?
- A new internal-only field is added in a future Infrahub version — does it automatically become excluded from the Schema Load Model without a manual code change?
- A field currently accepted by the load endpoint is reclassified as internal-only — are submissions that include it rejected from that point forward?
- The `state` field (used to mark schema elements as `absent` for deletion) has the same system-managed marker as internal-only fields but must remain user-settable in the Load Model — what mechanism ensures it is not incorrectly excluded?

## Requirements *(mandatory)*

### Field Classification Criteria

A field is **internal-only** (excluded from the Schema Load Model) if ALL of the following are true:

1. Its value is computed or populated by the system during schema processing (e.g., inheritance resolution, reference tracking)
2. A user setting it manually would either be a no-op or produce incorrect system behaviour
3. It is never meaningfully authored in a schema definition file by a human

A field is **user-configurable** (included in the Schema Load Model) if a user is expected to set it when authoring a schema — regardless of whether the value can be updated later. Fields that are set on initial load but cannot be changed after (e.g., `human_friendly_id`, `uniqueness_constraints`) are user-configurable and must remain in the Load Model.

### Functional Requirements

- **FR-001**: Before implementation begins, every field across nodes, attributes, relationships, and generics in the schema definition source of truth MUST be individually classified as internal-only or user-configurable using the criteria above, and the complete list MUST be reviewed and approved; no Schema Load Model may be generated until this classification is approved
- **FR-002**: The system MUST establish a formal, machine-readable designation for internal-only fields within the schema definition source of truth, so that the Schema Load Model can be derived automatically rather than maintained as a manual list
- **FR-003**: The Schema Load Model MUST exclude all fields carrying the internal-only designation; only fields users are expected to configure may be present
- **FR-004**: The Schema Load Model MUST enumerate all valid values for every field that has a bounded set of options; this includes at minimum: attribute `kind`, relationship `kind`, relationship `cardinality`, relationship `direction`, relationship `on_delete`, attribute and relationship `branch`, attribute and relationship `allow_override`, and node/attribute/relationship `state`
- **FR-005**: The schema load endpoint MUST immediately reject any submission containing fields not present in the Schema Load Model, returning an error that identifies the offending field(s) by name, with no deprecation or warning period
- **FR-006**: The schema load endpoint MUST reject enumerable field values that are not in the valid options list, returning an error that identifies the invalid value and lists valid alternatives
- **FR-007**: The Schema Load Model MUST be automatically kept in sync with the schema definition source of truth — when new user-configurable fields or valid option values are added to the source of truth, they MUST appear in the generated load model without manual intervention
- **FR-008**: The `state` field (used to mark schema elements as `absent` for deletion) MUST remain present and user-settable in the Schema Load Model, regardless of its system-managed marker
- **FR-009**: The Schema Load Model MUST be available as a machine-readable artifact that external tools and LLMs can consume to understand what constitutes a valid schema submission
- **FR-010**: The schema read endpoint (`/api/schema`) MUST remain unchanged; it MUST continue to return all fields including system-computed fields such as `inherited` and `used_by`

### Key Entities

- **Schema Load Model**: The generated input definition for schema submissions to the load endpoint; contains only user-configurable fields with fully enumerated options for bounded-value fields; derived from the schema definition source of truth but separate from the read model
- **Schema Read Model**: The output definition returned by the read endpoint; unchanged by this feature; includes system-computed fields such as `inherited` and `used_by`
- **Schema Definition Source of Truth**: The internal definition (currently `internal.py`) that describes all schema fields, their types, valid options, and metadata — including whether each field is internal-only
- **Internal-Only Field**: A schema field computed or managed exclusively by the system that must not appear in the Schema Load Model (e.g., `inherited`, `used_by`, `hierarchical`)
- **Enumerable Field**: A schema field that accepts only a bounded set of valid values, where all valid values must be explicitly listed in the Schema Load Model

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of schema load submissions containing internal-only fields (e.g., `inherited`, `used_by`) are rejected with error messages identifying the offending fields by name
- **SC-002**: The Schema Load Model enumerates all valid values for every bounded-value field across nodes, attributes, relationships, and generics; zero valid values are missing
- **SC-003**: Schema submissions using only fields and values present in the Schema Load Model achieve a 100% pass rate for load model compliance validation
- **SC-004**: The schema read endpoint continues to return `inherited`, `used_by`, and all other system-computed fields unchanged; no regression in read behaviour
- **SC-005**: Adding a new user-configurable field or valid option value to the schema definition source of truth automatically produces an updated Schema Load Model with no manual code changes required
- **SC-006**: LLM tools provided with the Schema Load Model produce syntactically valid Infrahub schemas at a measurably higher rate than with the current schema documentation
- **SC-007**: Support cases related to incorrect use of internal schema fields on load decrease by at least 50% within 3 months of release

## Assumptions

- The `hierarchy` field on nodes (described as "Internal value to track the name of the Hierarchy") is user-settable when defining hierarchical schemas and SHOULD remain in the Schema Load Model; this assumption must be confirmed during planning
- The `state` field is user-settable (users set it to `absent` to remove schema elements) and must be explicitly preserved in the Schema Load Model, even though it shares metadata characteristics with internal-only fields
- The enum metadata for all bounded-value fields is already fully defined in the schema definition source of truth; the gap is enforcement during load validation, not the data itself
- Backwards-compatible schema submissions (those not using internal-only fields or invalid enum values) continue to load without modification
