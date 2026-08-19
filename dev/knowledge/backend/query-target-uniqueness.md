# Query target uniqueness

> Part of: `dev/knowledge/backend/` | Related: [display-labels-and-hfid.md](display-labels-and-hfid.md), [schema-definitions.md](schema-definitions.md)

<!-- Extracted from specs/ifc-2504-graphql-query-report on 2026-08-14 -->

Infrahub decides how much work a proposed change has to redo by asking one question of every artifact
definition and generator definition query: **is this query guaranteed to resolve to a single object?**
The answer is a single boolean, `only_has_unique_targets`, computed by the GraphQL query analyzer.

When the answer is yes, Infrahub can map a changed node back to the exact artifacts or generator
instances that depend on it, and regenerate only those. When the answer is no, a changed node cannot be
attributed to any particular target, so every target of the definition is reprocessed. Users experience
the difference as either a quick, surgical pipeline or a full regeneration of every artifact under the
definition.

## Where it is computed

`GraphQLQueryReport.only_has_unique_targets` in `backend/infrahub/graphql/analyzer.py` is the single
source of truth. It is a pure function of the parsed query document plus the branch's `SchemaBranch`
(needed to read uniqueness constraints); it runs in memory and issues no database queries.

`only_has_unique_targets` is `True` only when **every** root operation in the document pins a single
object. One unfiltered root query anywhere in the document makes the whole report `False`, even if the
other operations are fully pinned.

## The pinning rules

A root operation pins a single object when either condition holds.

### 1. Pinned by identifier

The operation carries an `ids` or `hfid` filter argument that provides a single value.

### 2. Pinned by uniqueness constraint

Every component of at least one of the model's uniqueness constraints is pinned by a single-valued
filter argument. Constraint groups are read via
`model.get_unique_constraint_schema_attribute_paths(...)`, and any group being fully pinned is enough.

- Attribute component: pinned by `<attribute>__<property>`, where the property defaults to `value`.
- Relationship component: pinned by `<relationship>__ids` or `<relationship>__hfid`, and **only for
  cardinality-one relationships**. A cardinality-many relationship can never pin a target.

### What counts as a single value

An argument provides a single value when it is one of:

- A static literal, for example `name__value: "red"`.
- A required, non-list variable, for example `$name: String!` used as `name__value: $name`.
- A single-element list literal whose element is either a static literal or a required variable, for
  example `ids: [$id]` with `$id: ID!`.

A required **list-typed** variable is treated differently depending on where it appears:

| Position | `$ids: [ID!]!` used directly | Why |
|----------|------------------------------|-----|
| Root `ids` / `hfid` filter | Accepted | The target selector is driven once per target member, so at execution time the list carries exactly that member. |
| Relationship component of a uniqueness constraint (`<rel>__ids`) | Rejected | Nothing constrains the list to one element, so it can match several objects. |

An optional variable never pins, whatever its type. `$ids: [ID!]` (optional list of required elements)
is a common near-miss: the elements are non-null but the argument itself may be omitted, so the query
reports `false`.

## What consumes the result

`get_field_level_impacted_subscribers` in `backend/infrahub/proposed_change/tasks.py` combines the
uniqueness verdict with the branch diff and returns an `ImpactScope`:

| Scope | When | Effect |
|-------|------|--------|
| `SPECIFIC` | The query pins unique targets. | Only the subscribers linked to the changed nodes are reprocessed, possibly none. |
| `ALL` | The query does not pin unique targets, but a field the query reads did change. | Every target of the definition is reprocessed. |
| `NONE` | No node of a queried kind had any of its queried fields modified. | Nothing is reprocessed, regardless of the uniqueness verdict. |

Two separate gates therefore apply, and uniqueness is only the second one. Field-level relevance comes
first: `query_report.requested_read` limits "relevant change" to the attributes and relationships the
query actually reads, so a query that reads `name` is untouched by a change to `description`. Only once
a relevant change exists does the uniqueness verdict decide between `SPECIFIC` and `ALL`.

The same helper serves both subscriber kinds: `CoreArtifact` for artifact definitions and
`CoreGeneratorInstance` for generator definitions. A generator query with unpinned targets pays the same
full-reprocessing cost an artifact query does.

## Inspecting a query

The verdict is exposed so users never have to reason about the rules above from source code.

The root GraphQL field `InfrahubGraphQLQueryReport` takes a raw query string and returns
`targets_unique_nodes`. Branch context is resolved from the request like any other query, and the
submitted string is validated against that branch's schema before analysis, so an empty string,
malformed GraphQL, or a reference to an unknown node kind comes back as a GraphQL error rather than a
default `false`.

```graphql
query ($q: String!) {
  InfrahubGraphQLQueryReport(query: $q) {
    targets_unique_nodes
  }
}
```

`infrahubctl graphql query-report <name>` wraps that field for the common case. It resolves the query by
name from the local `.infrahub.yml`, or from the server's `CoreGraphQLQuery` nodes with `--online`, and
prints the verdict. This is the check to run against an artifact definition's query before saving it.

User-facing documentation calls this property a **single-target query**, and
`docs/docs/development-resources/graphql/single-target-queries.mdx` is where the criteria and the command
are documented for users. Keep that page in step when the rules change.

The response type is intentionally a container rather than a bare boolean, so further fields already
computed by the analyzer (`requested_read`, `variables`, `impacted_models`) can be surfaced later
without breaking callers.

## Gotchas

- Adding a second, unfiltered root operation to an otherwise well-pinned query silently flips the verdict
  to `false`. This is the most common cause of an unexpected full regeneration.
- The verdict depends on the branch's schema, because uniqueness constraints live in the schema. The same
  query can report differently on two branches, and changing a model's uniqueness constraints changes how
  its existing queries are scoped.
- `false` is never incorrect behavior, only expensive behavior: Infrahub falls back to reprocessing every
  target, which is safe but slow.
