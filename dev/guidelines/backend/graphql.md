# GraphQL API Standards

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md), [Python Testing Standards](testing.md)

<!-- Extracted from specs/ifc-2504-graphql-query-report on 2026-08-14 -->

Conventions for hand-written additions to Infrahub's GraphQL API. Schema-driven node queries and
mutations are generated from the schema and are not covered here.

## Root-level query fields

A root-level query field is a custom entry point on the root `Query` type, as opposed to the node
queries generated from the schema. Adding one takes four pieces, in one new module under
`backend/infrahub/graphql/queries/`.

1. A graphene `ObjectType` describing the response.
2. A standalone `async` resolver function, not a method on a class.
3. A module-level `Field(...)` bound to that resolver, named exactly as the field should appear in the
   schema.
4. Registration: export the `Field` from `queries/__init__.py` (import plus `__all__`), then assign it as
   a class attribute on `InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py`.

```python
class QueryStatistics(ObjectType):
    node_count = Field(Int, required=True, description="Number of nodes matched by the query.")


async def resolve_query_statistics(_root: None, info: GraphQLResolveInfo, query: str) -> dict[str, int]:
    graphql_context: GraphqlContext = info.context
    ...


InfrahubQueryStatistics = Field(
    QueryStatistics,
    query=String(required=True, description="The raw GraphQL query string to analyze."),
    description="Return statistics describing how Infrahub will execute a query.",
    resolver=resolve_query_statistics,
    required=True,
)
```

Use a `graphene.Mutation`-style class only for operations that mutate state.

### Return a container, not a bare scalar

Even when the field answers a single yes/no question today, return an `ObjectType` holding that one field
rather than a bare `Boolean`. Adding a second field to an object type is backward compatible; changing a
scalar field into an object type is not.

### Mark fields required and describe them

Every field a resolver always populates is declared `required=True`. Give each field and each argument a
`description` - these strings are the API reference, published in the exported GraphQL schema and read by
API consumers who cannot see the resolver. Describe what the value means to a caller, not how it is
computed.

## Resolver conventions

- **Branch comes from the context, never from an argument.** Read `info.context` as `GraphqlContext` and
  use `graphql_context.branch`. Do not add a `branch` argument to a new field; the request already
  carries branch context and every other query resolves it the same way.
- **Reach the schema branch through the registry.** `GraphqlContext` does not expose `SchemaBranch`
  directly. Use `registry.schema.get_schema_branch(name=graphql_context.branch.name)`. Deriving it from
  `info.schema` does not work: the graphene/graphql-core schema does not carry the Infrahub
  `SchemaBranch`.
- **Keep the resolver thin.** A resolver adapts the request to a component and shapes the response. When
  it grows real logic, move that logic into a component under `backend/infrahub/` and call it - the
  resolver is not a place where behavior should accumulate. Never reimplement analysis or business rules
  that already exist elsewhere; call the existing owner so the API and the internal consumer cannot
  diverge.

## Invalid user input

Input that a caller controls and can get wrong - a query string, an identifier, a filter expression -
must fail loudly.

- Raise a `GraphQLError` so the failure surfaces in the response's `errors` array rather than as an
  unhandled Python exception.
- Never absorb invalid input into a default or falsy result. A caller who submits a malformed query and
  receives `false` cannot tell a real answer from a swallowed error.
- Validate before analyzing. Where a helper already exposes a validity check, run it and surface its
  errors rather than letting a downstream call fail in a less legible place.
- Keep the message about the input. Do not let stack traces or internal paths reach the caller.

## Testing

Resolvers that touch the schema registry or a `SchemaBranch` belong in
`backend/tests/component/graphql/queries/`, executed through the full GraphQL stack with
`prepare_graphql_params` rather than by calling the resolver function directly - the wiring into
`InfrahubBaseQuery` is part of what the test needs to cover. Every input-error path gets its own test
case; assert on the exact error message, as required by
[Python Testing Standards](testing.md).

Resolver logic that operates purely on in-memory inputs still belongs in a unit test. Pick the cheapest
tier the logic actually needs.
