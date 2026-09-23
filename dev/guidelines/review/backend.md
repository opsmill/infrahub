# Infrahub backend Python review

Flag violations of these Infrahub conventions in `backend/infrahub/**`, `python_testcontainers/**` and `tasks/**`. Ruff (`select = ALL`), mypy and ty already enforce import placement, `TYPE_CHECKING`, annotations, `X | None`/`list[...]`, override variance, naming and formatting. Do not repeat those. Review only added or changed lines.

## Exceptions (ruff BLE/TRY are disabled, so this is on you)

- Flag `except Exception` or bare `except:` where the call raises a knowable set of types. Ask for the narrowest types, grouped as a tuple. Infrahub errors are mostly siblings: `QueryTimeoutError` is not a `DatabaseError`.
- Flag a `try` around code that can't raise anything the caller must handle, such as building objects from validated data or putting a message on an internal queue. Non-critical side effects like telemetry belong off the request path, not silenced where they run.
- Broad catches are legitimate only in these cases: a top-level boundary (worker loop, request handler), a per-item loop that reports each failure, a best-effort side effect after the primary work committed, or add-context-then-`raise`. Flag one that is none of these, or that has no comment naming its case.
- Flag handlers that neither log, record nor re-raise (`except ...: pass`).
- Flag a best-effort fallback that narrows the result or under-executes. It must be at least as safe as the side effect never running.
- Flag a `try` body that covers more than the statement that can raise.
- Flag swallowed cancellation: an `isinstance(r, Exception)` filter over `gather(return_exceptions=True)`, or `CancelledError` counted as success.
- Flag catch-and-return inside `async with db.start_transaction()`, because it commits the partial work. Put the `try` outside the block.
- Flag `log.error` in an `except` block that has no comment saying the traceback is worthless (a routine disconnect) or harmful (a log filter keys on the exception type). The default is `log.exception`.
- Flag a new error raised from inside `except` without `from exc`.

## Typing beyond the checkers

- Flag every new `cast()`. Narrow with a positive `isinstance` that returns the value. A cast "recording" an earlier check still counts.
- Flag a new `# type: ignore`/`# ty: ignore`, or a new or extended `disable_error_code`/`[[tool.ty.overrides]]` entry that covers a violation the change introduced. Fix the code instead.
- Flag `getattr(obj, "x", default)` on typed objects, and `getattr(node, name)` where a typed accessor such as `node.get_relationship(name)` exists.
- Flag `isinstance(schema, NodeSchema)` guards that leave out `ProfileSchema`/`TemplateSchema`.
- Flag `str()` on an optional value such as `str(rel_schema.identifier)`, which yields `"None"`. Use the accessor that raises.
- Flag a bare `str` that takes a fixed set of values. Use `Literal` within one file, and a `StrEnum` when the set is shared, persisted, on GraphQL, or emitted as a metric label, log key or response field.
- Flag comparisons or Cypher that hardcode an enum's string value instead of using the member.
- Flag several mutually-exclusive booleans. Suggest a union of frozen dataclasses.
- Flag `T | Sequence[T]` "one or many" parameters and `Sequence[str]` parameters, since a bare `str` passes both. Take `list[str]`.

## Component design (new or reshaped classes)

- Flag collaborators built inside `__init__` or mid-run. Inject them through the constructor and wire the graph near the entry point.
- Flag an optional collaborator (`x: X | None = None` with an internal default). Collaborators are required, and a fan-out takes a required `list[...]` with callers passing `[]`.
- Flag late wiring: `set_x()`, `register_handler()`, `obj.on_change = fn`, or configuring a built object by assignment.
- Flag components that take a `Settings` object or read `config.SETTINGS` or other globals. They take plain values the factory resolves.
- Flag business logic in a `@flow` body, and singleton getters (`get_database()`) called anywhere but the top of the flow.
- Flag work items (nodes, schemas, diffs, payloads) stored on the instance. Pass them to the entry method. `db` goes to the constructor.
- Flag a dataclass that needs a collaborator to work. It should be a plain class.
- Flag new `save`/`get`/`from_db`/`to_db` methods on a model, and a Query `get_data()` that returns the model. Use a Repository plus a Query returning a `*QueryResult`.
- Flag `isinstance`/`match` dispatch across an open set of implementations. Use `supports()` plus an aggregator over an injected list. A closed set uses `match` with `assert_never`.
- Flag an out-of-domain client (metrics, tracing, telemetry) imported into domain logic. Use a `Protocol` in the consumer's vocabulary, with the adapter in its own module.
- Flag a `reset()`/`initialize()` that leaves memoized or derived state from the previous input.

## Correctness

- Flag blocking sync I/O inside `async def`.
- Flag Cypher with interpolated values. Use `$params`.
- Flag N+1 patterns: per-node loads in a loop, or fetch-then-mutate-each. Ask for a set-based query.
- Flag truthiness checks on optional numbers (`if offset:`). Use `is not None`.
- Flag `path.startswith(p)` on allow-lists or exclusions, since `/healthcheck` matches `/health`. Require `path == p or path.startswith(f"{p}/")`.
- Flag `json.dumps(default=str)` that feeds a hash or cache key.
- Flag `from infrahub.core import registry`. Use `from infrahub.core.registry import registry`.
- Flag positional arguments to project functions. Use keywords (`execute(db=db)`). Single-argument builtins and `log.info("msg")` are fine.
- Flag untyped `dict`s used as structured data. Use Pydantic at boundaries and frozen dataclasses internally.
- Flag new `config.py` numeric fields with loose bounds, `float` fields without `allow_inf_nan=False`, and invariants between settings not enforced by a `@model_validator(mode="after")`.
- Flag functions or classes in `constants.py`.
- Flag `datetime.UTC` and `typing.Self` in `python_testcontainers`, which targets 3.10.
- Flag edits to generated files (`core/schema/generated/`, `core/protocols.py`, `graphql_queries/*.py`).
- Flag ASGI middleware that doesn't pass non-`http` scopes through, raises to short-circuit instead of sending a response, or is registered after `InfrahubCORSMiddleware`.

## Comments and docstrings

- Flag comments that narrate or restate code (`# loop over nodes`). Comments stay silent by default and give only a non-obvious why, in one sentence.
- Flag comments about history or rejected approaches ("previously", "no longer", "instead of X"). Contract negatives like "never raises" are fine.
- Flag ticket, issue or spec IDs and URLs (`INFP-556`, `FR-003`, `T042`, GitHub links), and spec-coined jargon.
- Flag comments or docstrings naming other classes, functions or callers ("used by `FooService`"). Protocols, raised exception types and upstream-library workarounds are fine.
- Flag `Args`/`Returns`/`Raises` entries that restate the signature. Public functions get one contract line; clearly named private helpers get none.
- Flag dataclass fields documented in the class docstring, or given a docstring that repeats the field name.

## Do NOT flag

- Function-local imports in `tasks/*.py`, which are deliberate so `invoke` stays light, or a `# noqa: PLC0415` import that states a reason.
- Legacy `StandardNode`/`Branch` persistence, an optional collaborator added to existing code to avoid a large call-site change, or problems in untouched code. Drive-by refactors are out of scope.
- A broad `except Exception` that logs and re-raises, or one that names its case.
- Existing mypy/ty suppressions, or a scoped `# type: ignore[code]  # reason` added while re-enabling a rule.
- A missing interface when there is only one implementation, unless it would keep an out-of-domain dependency out.
- Temporal edge cases in migrations and retention queries. They run at the current time with the system down, and `at` is only a consistent "now".
- Missing transactions in a function that takes `db`, since the caller owns the transaction boundary. Cascading deletes are committed separately on purpose.
- Explanatory comments on Cypher, or on upstream library behavior the call site can't show. Repeating a short Cypher fragment instead of abstracting it.
- `PoolExhaustedError` and other `infrahub.exceptions` errors propagating to the API as intended responses.
- Orphaned Attributes (attributes with no node). They are not supposed to exist, so queries don't handle them.

Sources: dev/guidelines/backend/{python,exceptions,typing,checklist,asgi-middleware}.md, .agents/rules/{backend-component-design,code-doc-style,python-module-layout,python-typing}.md, backend/AGENTS.md, AGENTS.md, pyproject.toml
