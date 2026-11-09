# GraphQL Execution Paths

> Part of: `dev/knowledge/backend/` | Related: [mutations.md](mutations.md), [branch-status.md](branch-status.md), [api-backpressure.md](api-backpressure.md)

How graphql-core decides between synchronous and asynchronous field completion, why per-field hooks such as middleware must stay synchronous on the hot path, and why a query resolver opens its own database session.

## Sync vs async completion is decided per field

graphql-core has no global execution mode. For every resolved field it checks whether the resolver returned an awaitable:

- Plain value: the field completes synchronously, inline, with no event-loop involvement.
- Awaitable: the field takes the async completion path — a coroutine object is created, wrapped, awaited, and often gathered with its siblings.

A query whose resolvers all return plain values therefore executes as one synchronous pass, and `execute()` returns an `ExecutionResult` directly instead of an awaitable.

## Middleware multiplies by the number of fields

Middleware registered on `execute()` wraps **every field resolver**, including the default resolver used for plain attribute access and for every introspection meta-field. The consequence:

- An `async def` middleware makes every field return a coroutine — even fields whose resolver is a plain synchronous value. The entire execution is forced onto the async completion path, paying coroutine creation, `ensure_future`, and gather overhead per field.
- The overhead is roughly 10 µs per field. Ordinary queries resolve tens to hundreds of fields and never notice. An `IntrospectionQuery` against the full schema resolves on the order of a million fields: measured on the e2e image, introspection took 12.3 s through an async middleware versus 0.85 s on the synchronous path.

Because that work is pure CPU inside one coroutine, it never yields meaningfully: the worker's event loop is pinned for the whole execution, and every other request handled by that worker — including static asset serving — waits. One abandoned sandbox introspection starving the next page load was the root cause of the long-standing `ipam-breadcrumb` e2e flake.

## The pattern: synchronous dispatch, async only where needed

Write middleware as a plain `def` that returns the resolver's raw result, and return a coroutine only on the narrow path that genuinely needs to await something:

```python
def my_middleware(next, root, info, **kwargs):
    if <needs async work for this specific field>:
        return _async_gate(next, root, info, kwargs)
    return next(root, info, **kwargs)


async def _async_gate(next, root, info, kwargs):
    await do_the_async_check()
    result = next(root, info, **kwargs)
    if isawaitable(result):
        return await result
    return result
```

Returning the raw result is safe: graphql-core already handles awaitables returned by real async resolvers, so the middleware does not need to await on their behalf.

`raise_on_mutation_for_branch_status` (`backend/infrahub/graphql/middleware.py`) is the worked example: it gates only top-level mutation fields through its async branch, so queries — and the response payload fields of mutations — stay on the synchronous path. `backend/tests/unit/graphql/test_middleware.py` pins the invariant that query and introspection execution completes without returning an awaitable.

## When adding per-field hooks

- Prefer no middleware at all: a check that runs once per request belongs in the request handler (`InfrahubGraphQLApp._handle_http_request`), not in a per-field hook.
- If a hook must be middleware, keep the common path synchronous and branch to async only for the fields that need it.
- Resolvers themselves are unaffected by this guidance: a resolver that performs I/O should of course be `async` — the cost being avoided is wrapping the *synchronous* majority of fields in needless coroutines.

## A query resolver opens its own database session

Wrap the body of a query resolver that runs Cypher in a session of its own, and pass that `db` to everything it calls:

```python
# ✅ Good - this field reads on its own connection
async with graphql_context.db.start_session(read_only=True) as db:
    pool = await NodeManager.get_one(id=pool_id, db=db, branch=graphql_context.branch)

# ❌ Bad - every field of the request reads through this one session
pool = await NodeManager.get_one(id=pool_id, db=graphql_context.db, branch=graphql_context.branch)
```

The GraphQL app opens one session per request and puts it on `GraphqlContext.db`. graphql-core gathers the async fields of a query together, at the root and at every nested level, and a Neo4j session drives a single connection. Two resolvers reading through the request session at once fail with `RuntimeError: read() called while another coroutine is already waiting for incoming data`, or hang until the read times out.

- Keep the whole resolver body inside the `async with`, and return plain data. Anything that reads the database after the block closes fails.
- `graphql_context.db.schema` is held in memory, so reading it directly is safe.
- Mutations are different: graphql-core resolves mutation root fields one after another, and each mutation opens its own `start_transaction()`. This rule covers query resolvers.

`backend/tests/unit/graphql/queries/test_resolver_session_convention.py` scans the module of every root query field's resolver and fails on any use of the context database other than `.start_session(` or `.schema`.
