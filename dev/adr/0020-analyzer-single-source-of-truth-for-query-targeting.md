# 20. Analyzer is the single source of truth for query targeting

**Status:** Accepted
**Date:** 2026-08-14
**Author:** @opsmill-team

## Context

Whether a proposed change regenerates one artifact or every artifact under a definition hinges on a
single verdict: is the definition's GraphQL query guaranteed to resolve to one object? That verdict is
computed by `GraphQLQueryReport.only_has_unique_targets` in the GraphQL query analyzer, and consumed by
the proposed change pipeline to choose between a specific and a full regeneration scope.

The rules behind the verdict are not obvious from a query alone. They depend on the branch's uniqueness
constraints, on whether a filter argument is a literal, a required variable, or a list, and on every root
operation in the document rather than just the first. Users had no way to reach the verdict: they
discovered it at runtime, as an unexpectedly slow pipeline, and could only explain it by reading backend
source.

Exposing the verdict meant choosing where the rules live. The tempting shape is to state the rules in
user documentation and let a lighter-weight check - in the CLI, in the frontend, or in a separate
validation helper - reproduce them for users. That check would be cheap, would work offline, and would
not require a server round trip.

## Decision

The analyzer holds the rules, and every consumer reads them from it. Nothing reimplements or restates
the targeting logic as executable rules.

- The proposed change pipeline calls `only_has_unique_targets` as it already did.
- The root GraphQL field `InfrahubGraphQLQueryReport` exposes the same property as
  `targets_unique_nodes`, resolving branch and schema from the request so the answer is computed against
  the branch the query will actually run on.
- `infrahubctl graphql query-report` calls that GraphQL field. It resolves a query by name and prints the
  verdict; it does not analyze the query locally.

Documentation describes the rules for comprehension and points at the command for the answer. It is not
a specification a second implementation is written against.

## Consequences

### Positive

- A user's answer and the pipeline's decision cannot disagree, because they are the same computation on
  the same branch schema.
- Broadening the rules stays a single change. The rules were extended after the introspection query
  shipped - `hfid`, cardinality-one relationships, and composite uniqueness constraints were added - and
  the exposed verdict followed automatically with no second implementation to update.
- The verdict is reachable before a definition is saved, which is when it is actionable.

### Negative

- Checking a query requires a reachable Infrahub instance and a branch. There is no offline linting of a
  `.gql` file, and none can be added without reintroducing the divergence this decision avoids.
- Every consumer pays a round trip for a computation that is pure and in-memory on the server.

### Neutral

- The verdict is branch-dependent by construction. The same query can report differently on two branches,
  because uniqueness constraints live in the schema.
- Documentation of the rules is explanatory and can drift from the analyzer without anything failing.
  Behavior does not drift; only the prose can, so it needs review whenever the rules change.

## Alternatives Considered

### Reimplement the targeting rules in the CLI or SDK

Would give offline checks with no server dependency. Rejected: the rules read the branch's uniqueness
constraints, so an offline implementation would need the schema anyway, and any drift between the two
implementations produces the worst possible failure - a tool that confidently reports `true` while the
pipeline regenerates everything.

### Document the rules and ship no tooling

Cheapest option, and where the feature started. Rejected because the rules are subtle enough that reading
them is not the same as applying them correctly to a specific query, and the failure mode is silent: a
user gets no signal that a query is expensive until they observe the pipeline.

### Return the verdict as a bare `Boolean` field

Simpler schema for the one question being asked. Rejected in favor of an object type, so the other
properties the analyzer already computes (`requested_read`, `variables`, `impacted_models`) can be
surfaced later without a breaking change.

## Implementation Notes

- Rules and consumers: [`dev/knowledge/backend/query-target-uniqueness.md`](../knowledge/backend/query-target-uniqueness.md).
- Spec: [`dev/specs/archive/ifc-2504-graphql-query-report/research.md`](../specs/archive/ifc-2504-graphql-query-report/research.md) (RES-001).
