# Feature Specification: GraphQL Query Report Introspection

**Feature Branch**: `ifc-2504-graphql-query-report`
**Jira**: IFC-2504
**Created**: 2026-04-25
**Status**: Draft
**Input**: Add InfrahubGraphQLQueryReport introspection query that reports how Infrahub will interpret a given GraphQL query, specifically whether it targets unique nodes for artifact regeneration purposes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate Query Before Defining Artifact (Priority: P1)

A platform engineer is writing a new artifact definition. They have a GraphQL query and want to know, before saving the definition, whether Infrahub will be able to perform targeted artifact regeneration or will fall back to regenerating all artifacts whenever any relevant node changes. They submit their query to the report endpoint and get an immediate answer.

**Why this priority**: This is the core use case driving the feature. Without this, users discover the behavior only at runtime through unexpected full regenerations, which wastes compute and causes delays.

**Independent Test**: Can be fully tested by submitting a known query to the `InfrahubGraphQLQueryReport` query and verifying the `targets_unique_nodes` field returns the correct value. Delivers immediate value as a diagnostic tool even before any UI integration.

**Acceptance Scenarios**:

1. **Given** a valid GraphQL query that filters by unique node identifiers, **When** the user submits the query to `InfrahubGraphQLQueryReport`, **Then** the response returns `targets_unique_nodes: true`
2. **Given** a valid GraphQL query that returns all nodes of a type without unique filters, **When** the user submits the query to `InfrahubGraphQLQueryReport`, **Then** the response returns `targets_unique_nodes: false`
3. **Given** a valid GraphQL query string, **When** the user submits it, **Then** branch context is automatically resolved from the request without requiring a branch argument

---

### User Story 2 - Debug Unexpected Full Regenerations (Priority: P2)

A platform engineer notices that artifact regenerations are running for all nodes rather than only changed nodes. They want to determine whether their existing query is the cause. They submit the query to the introspection endpoint and confirm whether the query is structured correctly for targeted regeneration.

**Why this priority**: Debugging silent misconfiguration is the second most common need. Users currently have no signal that their query is causing full regenerations until they observe the behavior in production.

**Independent Test**: Can be tested independently by submitting a query that lacks uniqueness constraints and confirming `targets_unique_nodes: false`, allowing the user to identify the root cause.

**Acceptance Scenarios**:

1. **Given** an existing artifact definition query, **When** the user submits it to `InfrahubGraphQLQueryReport`, **Then** the response clearly indicates whether it supports targeted regeneration
2. **Given** a query that uses a `ids` argument as a required filter, **When** submitted, **Then** `targets_unique_nodes` returns `true`
3. **Given** a query that uses a field matching a model's uniqueness constraints as a required argument, **When** submitted, **Then** `targets_unique_nodes` returns `true`

---

### Edge Cases

- **Empty or invalid query string**: The system MUST return an error. An empty string or syntactically malformed GraphQL is not analyzable and must not silently return a default value. Component test required.
- **Query referencing non-existent node types**: The system MUST return an error. A query that references types absent from the current schema cannot be meaningfully analyzed. Component test required.
- **Branch context resolution**: Follows standard Infrahub behavior — no special handling needed for this query.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a `InfrahubGraphQLQueryReport` query in the root GraphQL schema that accepts a required `query` string argument
- **FR-002**: The `InfrahubGraphQLQueryReport` query MUST return a `targets_unique_nodes` boolean field indicating whether the submitted query is structured to uniquely identify its target nodes
- **FR-003**: The `targets_unique_nodes` field MUST return `true` if and only if the query uses an `ids` argument or a field matching the model's uniqueness constraints, in both cases as a required argument
- **FR-004**: Branch context MUST be resolved automatically from the request context, consistent with how all other Infrahub GraphQL queries resolve branch
- **FR-005**: The system MUST return an error when the submitted query string is empty, syntactically invalid, or references node types that do not exist in the current schema; behavior for each MUST be validated by component tests
- **FR-006**: The `targets_unique_nodes` field MUST be documented and required (non-nullable) in the response type
- **FR-007**: The response type MUST be designed to allow future extension with additional report fields without breaking existing callers

### Key Entities

- **GraphQL Query Report**: A structured analysis result for a submitted query string, initially containing only the `targets_unique_nodes` indicator but extensible with further analysis fields (e.g., which node kinds the query reads, declared variables, model references)
- **Query Uniqueness**: The property of a GraphQL query where every operation resolves to nodes that can be uniquely identified, enabling Infrahub to limit artifact regeneration to only changed nodes rather than all nodes matching the definition

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can determine whether their query supports targeted artifact regeneration without reading Infrahub source code or documentation about internal analyzer behavior
- **SC-002**: The introspection query returns a result in under 500 milliseconds for any valid query input under normal load
- **SC-003**: The `targets_unique_nodes` result is accurate — zero false positives (reporting `true` when full regeneration would occur) and zero false negatives (reporting `false` when targeted regeneration is possible) across the defined uniqueness conditions
- **SC-004**: The feature is accessible to any user who can already execute GraphQL queries against their Infrahub instance, requiring no additional permissions or configuration

## Assumptions

- The uniqueness analysis logic already exists in the `InfrahubGraphQLQueryAnalyzer` component; this feature exposes it via a query endpoint rather than implementing new analysis logic
- Branch resolution behavior follows the same pattern already established for existing GraphQL queries — no changes to branch resolution logic are needed
- No authentication or authorization changes are required; access follows existing GraphQL query permissions
- The initial response type contains only `targets_unique_nodes`; future fields from the existing analyzer output can be added in subsequent iterations without this spec
