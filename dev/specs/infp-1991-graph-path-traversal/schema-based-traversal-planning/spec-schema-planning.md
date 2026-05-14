# Feature Specification: Schema-Based Path Planning for Graph Traversal Queries

**Feature Branch**: `infp-1991-graph-path-traversal`
**Created**: 2026-05-13
**Status**: Draft
**Input**: User description: "update the InfrahubPathTraversal and InfrahubReachableNodes graphql queries to use a new schema-based planning approach for their cypher queries. the planning should account for what schemas can be used to get from the starting item to the target item/schemas, including relationship directions and identifiers. the schema-based planning should also exclude any paths that include objects for which the user does not have permissions. the schema-based plan should then be used to construct a cypher query that covers all the possible routes from the starting object to the target object or schema. ideally the cypher query can be used to either find a path from one object to another or find a path from one object to all instances of a given schema"

**Related**: This spec refines the path traversal feature originally captured in [`spec.md`](../spec.md). It replaces the underlying traversal strategy used by the `InfrahubPathTraversal` and `InfrahubReachableNodes` GraphQL queries while preserving their externally observable behavior (inputs, outputs, error semantics).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan-Aware Path Discovery Between Two Objects (Priority: P1)

As a user of the graph path traversal feature, when I request paths between two specific objects, I want the system to first determine — from the schema — which sequences of node kinds and relationships could possibly connect the source kind to the destination kind, and then execute a database query that only follows those viable routes. I should receive the same kind of path results as today, but more quickly and without paths that include objects I am not permitted to see.

**Why this priority**: This is the core change. The current traversal blindly walks every outgoing relationship in the graph and prunes afterwards; using a schema-derived plan eliminates dead-end branches before they are explored, which is both faster on large graphs and necessary to enforce permissions correctly. Without this story delivered, the feature has no value.

**Independent Test**: For a source object of kind A and destination of kind B, verify that the engine first produces a non-empty plan listing the kind-sequences that could connect A to B, then executes a query that returns only paths conforming to one of those sequences. Verify that for an unreachable kind pair (no schema path between kinds), the query is short-circuited and returns an empty result without touching the graph.

**Acceptance Scenarios**:

1. **Given** a source object and a destination object whose kinds have at least one schema-level route between them, **When** the user requests `InfrahubPathTraversal`, **Then** the result contains the same set of valid paths as before the change for that branch and point in time.
2. **Given** a source object and a destination object whose kinds have no schema-level route between them within the configured maximum depth, **When** the user requests `InfrahubPathTraversal`, **Then** the engine returns an empty result without executing a graph traversal query.
3. **Given** a source/destination pair where one viable schema route passes through a kind the user does not have read permission on, **When** the user requests paths, **Then** that route is excluded from the plan and any returned paths exclude it.

---

### User Story 2 - Plan-Aware Reachable-Nodes Discovery (Priority: P1)

As a user discovering all reachable instances of one or more target kinds from a source object, I want the same schema-derived plan approach applied: the system determines which kind-sequences can reach each requested target kind, then queries only along those sequences, again excluding kinds the user cannot see.

**Why this priority**: `InfrahubReachableNodes` shares the same traversal substrate as `InfrahubPathTraversal` and is exposed to the same performance and permission concerns. Updating both in lockstep ensures consistent behavior and avoids divergent implementations.

**Independent Test**: For a source object of kind A and target kinds [B, C], verify that the engine produces a plan covering routes A→…→B and A→…→C separately and returns reachable B-instances and C-instances along with their paths. Verify that if no schema routes lead from A to any of the target kinds, the result is empty without database traversal.

**Acceptance Scenarios**:

1. **Given** a source object and one or more target kinds, **When** the user requests `InfrahubReachableNodes`, **Then** results contain only reachable instances of the requested kinds, each annotated with a path that conforms to a schema-derived route.
2. **Given** a source object where none of the target kinds is reachable at the schema level, **When** the user requests `InfrahubReachableNodes`, **Then** the result is empty and no traversal is executed against the data graph.
3. **Given** a target kind reachable only via an intermediate kind the user lacks permission on, **When** the user requests `InfrahubReachableNodes`, **Then** instances of that target kind reachable only through the forbidden intermediate are not returned (or are returned only via permitted alternate routes).

---

### User Story 3 - Single Generated Query Covers Both Modes (Priority: P2)

As a maintainer of the traversal subsystem, I want the schema-based planner to produce a single, parameterized query shape that can be configured to either (a) terminate at a specific destination object, or (b) terminate at any instance of one or more destination kinds. This avoids duplicating Cypher logic between the two GraphQL queries and ensures both modes evolve together.

**Why this priority**: Important for maintainability and correctness, but not user-visible. The feature is functional with two separate query templates; consolidating into one is a quality improvement that significantly reduces future drift.

**Independent Test**: Inspect that the path-finding code path and the reachable-nodes code path call into the same plan-to-query construction routine, differing only in the terminal predicate (specific destination id vs. destination kind set).

**Acceptance Scenarios**:

1. **Given** the planner output for any source/target pair, **When** the destination is configured as a specific object id, **Then** the generated query returns only paths whose final node has that id.
2. **Given** the same planner output, **When** the destination is configured as one or more target kinds, **Then** the generated query returns all paths whose final node is an instance of any of those kinds.
3. **Given** unit-level tests that fix the planner output, **When** the query is generated in each mode, **Then** the only difference between the two generated queries is the terminal predicate.

---

### User Story 4 - Plan Inspection for Debugging (Priority: P3)

As a developer debugging unexpected traversal results, I want the planner output (the set of viable kind-sequences with their relationship identifiers and directions, and any sequences pruned for permission reasons) to be observable via structured logs or a developer-facing diagnostic field, so I can verify that the plan matches my mental model of the schema.

**Why this priority**: Operational quality-of-life. Useful for troubleshooting and future development, but not required for the feature to deliver value.

**Independent Test**: With a debug flag or log level enabled, execute a traversal query and verify the plan is emitted in a structured, readable form that lists each viable kind-sequence, the relationship identifier and direction for each hop, and which sequences (if any) were pruned by permission filtering.

**Acceptance Scenarios**:

1. **Given** a traversal request executed with diagnostics enabled, **When** the request completes, **Then** logs include the full set of viable kind-sequences considered.
2. **Given** the same request, **When** the planner pruned routes for permission reasons, **Then** the diagnostic output identifies which routes were pruned and on which kind the user lacked permission.

---

### Edge Cases

- **Same kind at source and destination, no schema route**: If the source object and destination object share a kind but the schema offers no self-referential route within the configured depth, the planner returns no routes and the query is short-circuited to an empty result.
- **Cyclic schema routes**: If the schema permits cycles (kind A → kind B → kind A), the planner must enumerate viable sequences without infinite recursion. It does so by capping route enumeration at the configured maximum traversal depth, allowing each kind to appear multiple times along a sequence as long as total length stays within the cap.
- **User has permission on source and destination kinds but not on every intermediate kind on every route**: The planner must keep routes whose intermediate kinds are all permitted and drop routes that include any forbidden intermediate. If the result is no viable routes, the query is short-circuited.
- **Generic / parent kinds in routes**: When a schema relationship is defined against a generic, the planner enumerates the generic and treats any concrete kind that inherits from it as a valid stand-in for that hop, subject to per-kind permission filtering.
- **Asymmetric relationship directionality**: The planner records the direction of each relationship as defined in the schema and emits direction-aware Cypher; reversing endpoints in the schema must result in a different (or empty) plan.
- **Permission-set changes mid-flight**: Permission filtering is computed at plan time using the requester's effective permissions at request time; subsequent permission changes do not affect an in-flight query.
- **Existing input filters interact with the planner**: User-supplied `kind_filter`, `excluded_kinds`, `excluded_namespaces`, and `relationship_filter` are applied *to the plan* (removing routes that violate them) before query generation, not just to results post-hoc.
- **Branch and time context**: The planner reads the schema for the requested branch at the requested point in time, so structurally different schemas across branches produce different plans.
- **Excluded namespaces still defaulted**: The current default-excluded namespaces (Core, Internal, Builtin, Lineage, Profile, Template unless explicitly included) continue to apply to the planner the same way they apply today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST, on receiving a traversal request, derive from the active branch's schema the complete set of node-kind sequences (up to the configured maximum depth) that can connect the source object's kind to either the destination object's kind or any of the requested destination kinds.
- **FR-002**: Each route in the plan MUST record, for every hop, the relationship identifier and the relationship direction (outbound from the previous kind or inbound to it) as defined in the schema.
- **FR-003**: The planner MUST exclude any route containing a node kind on which the requesting user does not have read permission, evaluated against the requester's effective permissions for the requested branch.
- **FR-004**: When the planner produces zero viable routes (whether because no schema route exists, all routes were pruned for permissions, or all routes were pruned by user-supplied filters), the system MUST return an empty result without executing a traversal against the data graph.
- **FR-005**: The system MUST translate the planner output into a single Cypher query whose path expressions correspond exactly to the viable routes; no path outside the plan may be returned.
- **FR-006**: The generated query MUST support two terminal modes: (a) terminate at a specific destination node id, and (b) terminate at any node whose kind is in a configured set of destination kinds.
- **FR-007**: The `InfrahubPathTraversal` GraphQL query MUST use the planner in mode (a) and continue to accept the same inputs and return the same output shape as defined in `path.py`.
- **FR-008**: The `InfrahubReachableNodes` GraphQL query MUST use the planner in mode (b) and continue to accept the same inputs and return the same output shape as defined in `reachable.py`.
- **FR-009**: User-supplied filters (`kind_filter`, `excluded_kinds`, `excluded_namespaces`, `relationship_filter`) MUST be applied to the plan prior to query generation, eliminating routes that conflict with them.
- **FR-010**: The configured maximum traversal depth (default 5, max 20) MUST bound both the planner's route enumeration and the generated query's path lengths.
- **FR-011**: The configured maximum result count (paths or reachable nodes, as appropriate) MUST be enforced by the generated query.
- **FR-012**: The planner MUST treat generic schemas in the schema as expansions to their concrete inheriting kinds for the purposes of enumerating viable routes, subject to per-kind permission filtering.
- **FR-013**: The planner and generated query MUST respect branch and point-in-time context — the same source/destination on different branches with different schemas MUST produce plans appropriate to each branch's schema.
- **FR-014**: The system MUST emit, at a developer-facing diagnostic log level, a structured representation of the planner output for each request, including viable routes, routes pruned by permission, and routes pruned by user filters.
- **FR-015**: The system MUST preserve current error semantics: missing source/destination object returns the same error message, identical source and destination returns the same error message, exceeding the maximum depth or paths is bounded the same way.
- **FR-016**: Planner output for identical (schema-branch, source-kind, target-kind-set, depth, filter) tuples MUST be deterministic so that two adjacent requests produce the same plan, supporting cacheability.

### Key Entities

- **Route**: A schema-derived sequence of node kinds and the relationship hops between them, including each hop's relationship identifier and direction. The atomic unit produced by the planner.
- **Plan**: The complete set of routes from a source kind to one or more target kinds (or to a destination kind) under the active branch's schema, after permission and user-filter pruning. A plan may be empty.
- **Hop**: A single edge in a route, described by (start kind, relationship identifier, direction, end kind).
- **Permission Decision**: For a given requester and kind, a yes/no answer to "may this user read instances of this kind on this branch." Used by the planner to prune routes.
- **Terminal Predicate**: The condition that closes a path in the generated query — either "node id equals X" or "node kind is in {…}". Determines which traversal mode is run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For source/destination pairs whose kinds have no schema-level route between them, the traversal queries return an empty result in under 100 ms without executing a graph traversal.
- **SC-002**: For source/destination pairs that share a route, query latency at p95 is at least as fast as the existing implementation on the same graph and schema, and on graphs of 100,000 nodes is reduced by a meaningful margin (target ≥ 30%) compared to the existing implementation.
- **SC-003**: Zero paths returned by either GraphQL query include nodes whose kind the requester lacks read permission on, verified by automated test against representative permission configurations.
- **SC-004**: Existing automated tests covering `InfrahubPathTraversal` and `InfrahubReachableNodes` continue to pass without modification to assertions on input/output shape or error messages.
- **SC-005**: A developer with no prior context can, from diagnostic logs alone, reconstruct which routes the planner considered and which were pruned for which reason, validated by a peer review exercise on two sample requests.
- **SC-006**: Both GraphQL queries share a single plan-to-query construction routine, verified by the test referenced in User Story 3 — there is no Cypher query template duplicated between the two query handlers.

## Assumptions

- The existing schema branch infrastructure (`graphql_context.db.schema.get(...)`) is sufficient to enumerate kinds, their relationships, relationship identifiers, directions, and inheritance from generics. No new schema introspection capability is required.
- The existing permission system can answer "does requester R have read permission on kind K at branch B at time T" efficiently enough to call once per kind appearing in the candidate routes. If it cannot, the planner caches answers per request.
- The existing `kind_filter`, `excluded_kinds`, `excluded_namespaces`, and `relationship_filter` inputs on the path-traversal GraphQL types remain semantically meaningful and continue to be supported as plan-level filters.
- The current default-excluded namespaces (Core, Internal, Builtin, Lineage, Profile, Template) continue to apply unless explicitly overridden via the existing input.
- The output GraphQL types (`PathHopType`, `PathNodeType`, `PathRelationshipType`, `PathResultType`, `PathTraversalResultType`, `ReachableNodeType`, `ReachableNodesResultType`) do not change as part of this work; only the internal Cypher generation strategy changes.
- "All possible routes" is bounded by the maximum traversal depth; enumerating unbounded routes in a schema with cycles is explicitly out of scope.
- The planner is a backend-only concern; no UI changes are required for this work item beyond reflecting any new error or empty-result conditions surfaced through the existing GraphQL response shape.
- Diagnostic logs are sufficient for plan inspection in this iteration; a user-visible "show me the plan" GraphQL field is out of scope.
