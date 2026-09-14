# Prefect flow and task payloads

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md), [Async Tasks](../../knowledge/backend/async-tasks.md), [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md)

What a `@flow` may return, what a `@task` may receive, and how to pass data across those
boundaries without paying for Prefect's bookkeeping.

## What Prefect does with a value at a boundary

Every value that crosses a flow or task boundary is processed by Prefect before or after our
code runs. None of it shows up in Infrahub logs.

- Flow return values are traversed recursively to find futures. The traversal descends into
  every list, dict, set, dataclass, and Pydantic model, one Python call per object.
- Flow return values are persisted. The task worker runs with `PREFECT_RESULTS_PERSIST_BY_DEFAULT`
  enabled, so the return value is pickled, base64-encoded, and written to the Redis result
  storage block, unless the flow sets `persist_result=False`.
- Task arguments are traversed twice before the task starts: once to collect upstream
  dependencies, once to resolve futures. Tasks with the default cache policy also hash every
  argument to compute a cache key; every Infrahub task sets `cache_policy=NONE` to avoid this.
- Parameters of a subflow called in-process are traversed and re-validated, then JSON-encoded
  with `jsonable_encoder` and sent to the Prefect API, where they are stored with the flow run.

Measured on Prefect 3.7.5 with a synthetic 28k-node diff (1.23M objects) and a 3.1 MB GraphQL
response dict:

| Boundary | Cost |
|----------|------|
| Flow return traversal, 1.23M objects | 10 s |
| Flow return persisted to Redis, 1.23M objects | 1.4 s and a 70 MB key per run |
| Task argument traversals, 3.1 MB dict | 1.3 s per task call |
| In-process subflow parameter holding the core schema | 0.6 MB to 1.1 MB JSON sent to the Prefect API |

## Return only what the caller reads back

A flow result is read exactly once, by `execute_workflow` in the process that waited for the
run. Anything else a flow returns is traversed, pickled, and stored for nothing.

- Prefer returning nothing, or identifiers. Write the data to the database and let the caller
  read it back through the repository layer.
- If a flow must return a large object tree, set `persist_result=False` on the decorator and
  return the value inside Prefect's `quote()`. `quote()` stops the traversal; it does not stop
  persistence, which is why both are needed.
- Keep the flow's type annotations honest: mypy does not model `quote` as generic, so annotate the
  flow with a bare `quote` and unquote in a typed wrapper instead of at every call site.

```python
async def _update_diffs(self, ...) -> tuple[EnrichedDiffs, set[NodeIdentifier]]:
    quoted = await self._update_diffs_flow(...)
    return cast("tuple[EnrichedDiffs, set[NodeIdentifier]]", quoted.unquote())

@flow(name="update-diff", validate_parameters=False, persist_result=False)
async def _update_diffs_flow(self, ...) -> quote:
    ...
    return quote((enriched_diffs, node_identifiers_to_drop))
```

Flows whose result is consumed through `execute_workflow` keep persistence on. They return small
values by design: a list of messages, an enum, a rendered string.

## Wrap large task arguments in quote()

A task argument built from a GraphQL response, a diff, or a long list of identifiers is
traversed twice before the task body runs. Wrap it in `quote()` at the call site; Prefect removes
the annotation before calling the function, so the task body and its type annotations stay
unchanged.

```python
artifact_content = await self.render_jinja2_template.with_options(timeout_seconds=timeout)(
    commit=commit, location=location, data=quote(response)
)
```

- Wrap dicts and lists whose size scales with the data in the database. Identifiers, names, and
  small models do not need it.
- Keep `cache_policy=NONE` on every task. The default policy serializes all arguments to compute a
  cache key, and the result is then persisted to Redis.
- Document the expectation once, on the task definition, rather than at each call site.

## Pass references, not objects, to in-process subflows

Calling a `@flow` function directly from another flow creates a subflow run, and its parameters
are JSON-encoded and stored with that run in the Prefect database. `quote()` does not prevent
this, and objects that cannot be encoded are replaced by a placeholder string only after the
encoder has tried and failed.

- Pass branch names, node identifiers, and hashes, and resolve the objects inside the flow.
- Do not pass `SchemaBranch`, `InfrahubServices`, `InfrahubClient`, or enriched diffs as
  subflow parameters. The schema alone is more than half a megabyte of JSON per call.
- Set `validate_parameters=False` when the parameters are internal objects; it removes the
  traversal and the Pydantic re-validation of the arguments.
- When the subflow exists only to appear in the Prefect UI, consider a plain function instead.

## How to spot a payload problem

- A gap in the worker log between the last line a flow writes and Prefect's
  `Finished in state Completed()` line, with no database activity, is the return traversal and
  persistence.
- A task that takes seconds longer than its body, measured from the `Running` state, is the
  argument traversal.
- Result keys in the cache Redis database are 32-character hex strings whose value starts with
  `{"metadata":{"storage_key":`. A large one identifies the flow that should stop persisting.

## Checklist

- Does the flow return only what `execute_workflow` reads back? Otherwise return nothing or
  identifiers.
- If a large tree must be returned, is it inside `quote()` and is `persist_result=False` set?
- Are large task arguments wrapped in `quote()` at the call site?
- Does every task set `cache_policy=NONE`?
- Do in-process subflows receive identifiers rather than schema, service, or diff objects, with
  `validate_parameters=False`?
