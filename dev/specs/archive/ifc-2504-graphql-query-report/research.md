# Research: GraphQL Query Report Introspection

**Feature**: IFC-2504 | **Date**: 2026-04-25

## Summary

No unknowns required external research. All questions are resolved by reading existing code.

---

## RES-001: Existing Analyzer API

**Decision**: Use `InfrahubGraphQLQueryAnalyzer.query_report.only_has_unique_targets` directly.

**Rationale**: This property already exists at `backend/infrahub/graphql/analyzer.py:370`. It returns `True` if and only if every operation in the query resolves to uniquely identified nodes (via `ids` argument or uniqueness constraint field, both as required arguments). No new logic required.

**Alternatives considered**: Reimplementing uniqueness detection in the resolver — rejected; would duplicate logic and diverge from the authoritative source of truth used by artifact regeneration.

---

## RES-002: Pattern for New Root Query Fields

**Decision**: Follow the `InfrahubStatus` pattern in `backend/infrahub/graphql/queries/status.py`.

**Rationale**: `InfrahubStatus` is the canonical example of a custom root-level GraphQL query field that:
- Defines a graphene `ObjectType` with `required=True` fields
- Uses a standalone async resolver function
- Exports a `Field(...)` instance bound to the resolver
- Is imported in `__init__.py` and assigned as a class attribute in `InfrahubBaseQuery` in `schema.py`

**Alternatives considered**: Using a `graphene.Mutation`-style class resolver — rejected; queries do not mutate state and `status.py` provides the right pattern.

---

## RES-003: Schema Branch Access in Resolver

**Decision**: Access schema branch via `registry.schema.get_schema_branch(name=graphql_context.branch.name)`.

**Rationale**: `GraphqlContext` does not expose `schema_branch` directly. The same pattern is used in `backend/infrahub/graphql/mutations/graphql_query.py:44` which calls `db.schema.get_schema_branch(name=branch.name)`. Using `registry.schema` is equivalent (both reference the same registry) and is consistent with the component test in `test_query_analyzer.py`.

**Alternatives considered**: Deriving schema branch from `info.schema` directly — not straightforward; the graphene/graphql-core schema does not expose the Infrahub `SchemaBranch` object.

---

## RES-004: Error Handling for Invalid Input

**Decision**: Wrap analyzer construction in a try/except to catch `GraphQLSyntaxError` from `parse()`, and check `is_valid` for schema validation errors (non-existent types). Raise a `GraphQLError` for both cases.

**Rationale**:
- The base `GraphQLQueryAnalyzer.__init__` calls `parse(query)` directly. An empty string or syntactically malformed query raises `GraphQLSyntaxError` (subclass of `GraphQLError`) at construction time.
- Schema validation (non-existent types) is caught by `analyzer.is_valid` which calls `graphql-core`'s `validate()`. This returns a list of `GraphQLError`s.
- Both error paths must surface as GraphQL errors (not Python exceptions), consistent with how other resolvers handle invalid input.

**Alternatives considered**: Returning `targets_unique_nodes: false` silently on error — rejected; the spec explicitly requires errors to be returned for both cases, validated by component tests.

---

## RES-005: Test Level

**Decision**: Component tests in `backend/tests/component/graphql/queries/test_graphql_query_report.py`.

**Rationale**: The resolver accesses the schema (built from the registry + branch) and the `InfrahubGraphQLQueryAnalyzer` which requires a `SchemaBranch` and `GraphQLSchema`. These are integration surfaces that require a live database and schema registration. The spec explicitly mandates component tests for the error edge cases. The existing `test_query_analyzer.py` and `test_status.py` establish the exact fixture pattern to follow (`db`, `default_branch`, `car_person_schema`, `prepare_graphql_params`).

**Alternatives considered**: Unit tests with mocked schema — rejected by constitution principle IV ("Prefer adapter/protocol patterns over mocking") and by the spec requiring component tests for error cases.
