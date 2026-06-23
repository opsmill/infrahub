# Research: Search Anywhere Display Label Enrichment

## R1: How does display_label work for Schema/Internal nodes?

**Decision**: Use `node.get_display_label(db)` which is async and returns a string.

**Rationale**: The method already handles all fallback cases:
- If the node has a configured display_label template: renders it (e.g., "InfraDevice")
- If no display_label is configured: returns `repr(self)` which includes the kind and UUID
- If display_label resolves to whitespace: falls back to `repr(self)`

This means we always get a usable string, even for nodes without explicit display_label configuration.

**Alternatives considered**: Computing a label manually from the kind string — rejected because `get_display_label` already handles all cases consistently.

## R2: Does the GraphQL schema need regeneration?

**Decision**: Yes. The `Node` ObjectType in `search.py` is defined in Python using Graphene. After adding the `display_label` field, run `uv run invoke backend.generate` to regenerate `schema/schema.graphql`.

**Rationale**: The schema file at `schema/schema.graphql` is auto-generated from the Python Graphene definitions via `uv run infrahub dev export-graphql-schema`. The frontend uses `gql.tada` for type-safe GraphQL queries, so the generated schema must be up to date.

**Alternatives considered**: None — this is the standard workflow.

## R3: Frontend component testing approach

**Decision**: The `search-nodes.tsx` component has no existing test file. A new test file should be created for the Schema/Internal node rendering path.

**Rationale**: Backend tests already exist in `test_search.py` with patterns for GraphQL query testing (async pytest, `prepare_graphql_params`, `graphql()` helper). Frontend tests use Vitest with component rendering. The new frontend behavior (simplified rendering for unknown schema kinds) is testable without full integration.

**Alternatives considered**: Testing only via E2E — rejected because the rendering logic branching is unit-testable.

## R4: Frontend navigation for Schema/Internal nodes

**Decision**: Link to `/schema?kind={node.kind}` using the existing `QSP.KIND` query parameter.

**Rationale**: The schema page's `SchemaSelector` component already reads `kind` from query params via `useQueryState(QSP.KIND, ...)` and auto-scrolls to the selected entry. No schema page changes needed.

**Alternatives considered**: Custom schema detail route — rejected because the schema page already supports deep-linking via query parameter.

## R5: getObjectDetailsUrl behavior for unknown kinds

**Decision**: Do NOT use `getObjectDetailsUrl` for Schema/Internal nodes. It falls back to `/objects/{kind}/{id}` for unknown schemas, which would be a broken link.

**Rationale**: The function tries `getSchema(objectKind)` and when it returns null, constructs `/objects/{kind}/{id}` — a route that won't resolve for Schema/Internal kinds. Instead, the frontend should detect unknown schema kinds and construct `/schema?kind={kind}` directly.

**Alternatives considered**: Extending `getObjectDetailsUrl` with a Schema/Internal case — rejected because it would couple the utility to schema-page routing concerns, and the check should happen at the component level.
