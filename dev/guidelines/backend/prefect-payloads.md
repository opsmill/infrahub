# Prefect flow and task payloads

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md), [Async Tasks](../../knowledge/backend/async-tasks.md), [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md)

Rules for what a `@flow` returns, what a `@task` receives, and what an in-process subflow takes as
parameters. What Prefect does with each of those values is explained in
[What crosses a flow or task boundary](../../knowledge/backend/async-tasks.md#what-crosses-a-flow-or-task-boundary).

## Return only what the caller reads back

Return nothing, or identifiers, and let the caller read the data back through the repository layer.
Prefect walks and persists every flow return value, and only the result of a flow run through
`execute_workflow` is ever read back; those flows return small values by design.

When a flow must hand a large object tree to an in-process caller, return it inside `quote()` and
set `persist_result=False` on the decorator. `quote()` stops the walk and `persist_result=False`
stops the persistence, so both are needed. `quote` derives from `tuple[T]`, which mypy types as a
plain tuple, so annotate the flow with a bare `quote` and restore the payload type in one typed
wrapper with a positive `isinstance` check that returns the value, never with `cast()`.

```python
async def _update_diffs(self, ...) -> tuple[EnrichedDiffs, set[NodeIdentifier]]:
    quoted = await self._update_diffs_flow(...)
    enriched_diffs, node_identifiers_to_drop = quoted.unquote()
    if not isinstance(enriched_diffs, EnrichedDiffs) or not isinstance(node_identifiers_to_drop, set):
        raise TypeError("expected (EnrichedDiffs, set) from the update-diff flow")
    return enriched_diffs, node_identifiers_to_drop

@flow(name="update-diff", validate_parameters=False, persist_result=False)
async def _update_diffs_flow(self, ...) -> quote:
    ...
    return quote((enriched_diffs, node_identifiers_to_drop))
```

## Wrap large task arguments in quote()

Wrap any task argument whose size scales with the data in the database, such as a GraphQL response,
a diff, or a long list of identifiers, in `quote()` at the call site. Prefect walks each argument
twice before the task body runs and strips the annotation before calling the function, so the task
body and its type annotations stay unchanged. Identifiers, names, and small models do not need it.

```python
artifact_content = await self.render_jinja2_template.with_options(timeout_seconds=timeout)(
    commit=commit, location=location, data=quote(response)
)
```

Keep `cache_policy=NONE` on every task; the default policy hashes every argument for a cache key
and persists the result. State the quoting expectation once, in the task's docstring, rather than
at each call site.

## Pass identifiers, not objects, to in-process subflows

Pass branch names, node identifiers, and hashes to a `@flow` called from another flow, and resolve
the objects inside it. Subflow parameters are JSON-encoded and stored with the run in the Prefect
database, and `quote()` does not prevent that. Never pass `SchemaBranch`, `InfrahubServices`,
`InfrahubClient`, or an enriched diff as a subflow parameter.

Set `validate_parameters=False` when the parameters are internal objects; it removes the walk and
the Pydantic re-validation of the arguments. When the subflow exists only to appear in the Prefect
UI, use a plain function instead.
