# Replacing Graphene with Strawberry in the Infrahub GraphQL API

## Summary

- **The problem.** Graphene 3.4.3, released on 2024-11-09, is the latest release. It requires graphql-core `<3.3`, and graphql-core 3.3.0 was released on 2026-09-27. Strawberry 0.328 and later require graphql-core `>=3.3`. Infrahub cannot move to graphql-core 3.3 while it depends on Graphene.
- **What the POC shows.** Strawberry can generate the whole Infrahub schema at runtime. The test rebuilt the real `schema/schema.graphql` (1,227 types, 4,080 fields, 22,153 arguments) with Strawberry, and the printed SDL is identical to what Graphene produces today. The result is the same on Strawberry 0.327.7 with graphql-core 3.2.8 and on Strawberry 0.334.3 with graphql-core 3.3.0.
- **Breaking changes.** The GraphQL interface does not need to change. The remaining risks are server-side behaviour differences, listed below, that tests have to cover.
- **Performance.** Building the schema takes about the same time. Executing queries costs 10–20% more CPU in the GraphQL layer, measured without a database. Introspection takes the same time.
- **Not decided.** It is not decided whether to use Strawberry for the dynamic part of the schema, or to build graphql-core types directly and keep Strawberry, if anywhere, for the hand-written static types.

## How Infrahub uses Graphene today

Graphene is only the schema-building layer. Infrahub already parses, validates and executes every query with graphql-core directly:

- `backend/infrahub/graphql/execution.py` runs the query with graphql-core.
- `backend/infrahub/graphql/app.py` is a fork of `starlette-graphene3`.

`GraphQLSchemaManager.generate()` (`backend/infrahub/graphql/manager.py`) returns `graphene_schema.graphql_schema`, which is a plain graphql-core `GraphQLSchema`. Strawberry also produces a graphql-core schema (`strawberry.Schema(...)._schema`). So the execution engine, the middleware, the validation rules, the query analyzer and the subscription runner all stay the same.

Graphene-specific code that would have to be rewritten:

| Area | Size | What Infrahub relies on |
|---|---|---|
| Generated types (`manager.py`) | 1,307 lines | `type(name, (ObjectType,), attrs)`, plus 13 writes to `_meta.fields` after a class is created (relationships, hierarchy, metadata, `is_externally_managed`) |
| Static types | 119 ObjectType, 51 InputObjectType, 3 Interface, 20 Enum | `Meta` options, `__init_subclass_with_meta__` (17 overrides) |
| Mutations | 52 `Mutation` subclasses: 37 static, 15 templates for generated mutations | `mutate` dispatches on the class name, returns `cls(**result)`, and receives `InputObjectType` containers (dicts with attribute access, about 105 attribute reads) |
| Resolvers | 6 functions, 11 lines | `info.parent_type.graphene_type._meta.schema`, which reads the Infrahub schema back from the GraphQL type |
| Data types (`backend/infrahub/types.py`) | 45 references | each `InfrahubDataType` declares Graphene classes for query, create, update and filter |
| Scalars | `GenericScalar` (42 uses), `FixedGenericScalar`, `Upload` | custom `parse_literal` |
| Interface resolution | `resolve_type` returns a Graphene class | Graphene turns the class into a type name |
| Tests | 6 test files import Graphene; 21 reads of `_meta.fields` | |

## Feasibility: dynamic schema generation with Strawberry

Strawberry is designed around Python type annotations on hand-written classes. Infrahub can still generate types at runtime, but only through Strawberry's lower-level objects, not through decorators:

| Infrahub need | Strawberry mechanism used in the POC | Status of the API |
|---|---|---|
| Object types and interfaces created from the Infrahub schema | `types.new_class(...)` with `__annotations__`, then `strawberry.type` / `strawberry.interface`; `strawberry.tools.create_type` | documented |
| Implementing several generics | Python base classes (`types.new_class(name, (Iface1, Iface2), ...)`) | documented |
| Peers added after every type exists, including cycles | append `StrawberryField` objects to `cls.__strawberry_definition__.fields` before calling `strawberry.Schema()` | internal |
| Hundreds of filter arguments per field (`name__value`, `tags__name__values`, …) | `StrawberryField(...)` with `field.arguments = [StrawberryArgument(...)]` | internal, but stable classes |
| `snake_case` names | `StrawberryConfig(auto_camel_case=False)` | documented |
| Resolvers that return dicts | `StrawberryConfig(default_resolver=...)` plus an `is_type_of` that returns `True` | documented |
| Interface type from `__kind__` | `resolve_type` classmethod on the interface | documented |
| Existing resolvers that expect `GraphQLResolveInfo` | a wrapper that passes `info._raw_info` | private attribute |
| `GenericScalar`, `Upload`, `BigInt` with the same names | `strawberry.scalar(..., parse_literal=...)` | documented |
| `@expand` directive | `StrawberryDirective` | documented |
| Default values printed as `= null`, or not printed at all | `default=None` versus `default=strawberry.UNSET` | documented |

Problems found while building the POC:

- Strawberry resolves annotations by evaluating them. A module that uses `from __future__ import annotations` together with types defined inside a function fails with `NameError`. The generator must build arguments explicitly.
- Strawberry finds the `info` parameter by its `strawberry.Info` annotation. Today's resolvers declare `info: GraphQLResolveInfo`, so they need a wrapper, or a rewrite to use Strawberry's `Info`.
- By default, Strawberry checks that a value returned for an object type is an instance of its class. Infrahub resolvers return dicts, so every generated type needs `is_type_of`.
- Strawberry converts input arguments into instances of the input classes, not dicts. The mutation code reads `data` as a dict (`dict(data)`, `data.get`, `data.update`, `data._pop`).
- `graphql.utilities.lexicographic_sort_schema` rebuilds enum types as plain graphql-core enums, which drops Strawberry's serializer. Print the schema before sorting it, as `infrahub dev export-graphql-schema` already does.

Maintenance of Strawberry:

- It is still a 0.x release line: 1,137 releases on PyPI, 12 of them between 2026-10-05 and 2026-10-12.
- The mechanisms marked "internal" above can change in a minor release, so the version would need a tight pin and the parity test would need to run in CI.

## Impact on API users

- **Schema structure.** No breaking change is needed. The POC showed this on the real core schema:
  - type names, field names and argument names
  - nullability, list wrapping and default values (including `= null` versus no default)
  - descriptions and deprecation reasons
  - enums with value descriptions, the four custom scalars, `@expand`, and the `Subscription` type

  The rebuilt SDL is identical after sorting (30,412 lines in both).
- **Field order in introspection and the live `/schema.graphql`.** Strawberry orders fields by definition order, with inherited interface fields first. A generator can reproduce Graphene's order, but the POC did not verify this because it compared sorted output. GraphQL clients do not normally depend on field order.
- **Behaviour differences found, all server-side:**
  - **Enum output.** Graphene accepts an enum member, its value or its name returned by a resolver. Strawberry rejects the name (`Enum 'Color' cannot represent value: 'LIGHT_BLUE'`). Any Infrahub resolver that returns enum names must return members or values instead. Otherwise the field returns an error.
  - **DateTime input.** Five ISO 8601 formats were tested (`Z` offset, fractional seconds with an offset, a date only, the basic format, a space separator). Graphene and Strawberry parse all five to the same result. Wider coverage is not known.
  - **`GenericScalar`.** Strawberry's own JSON scalar is named `JSON`, so keeping the `GenericScalar` and `FixedGenericScalar` names needs custom scalars. The POC defines them.
  - **Error messages.** These come from graphql-core and Infrahub's error formatter, so they do not change while Infrahub keeps its own HTTP app instead of Strawberry's.
- **Python SDK and frontend.** They read the SDL or introspection only. Generated frontend types and `infrahubctl graphql generate-return-types` read `schema/schema.graphql`, which does not change. The CI job `graphql-schema` (`uv run invoke schema.validate-graphqlschema`) already detects any SDL drift.

## Performance

All measurements use Python 3.14 in the same container, taking the median of several runs. No database was involved, so the numbers isolate the GraphQL layer.

### Building the schema

| Test | Graphene 3.4.3 | Strawberry | graphql-core only |
|---|---|---|---|
| Real core schema rebuilt from its type definitions | 1.06–1.38 s | 0.88–1.12 s (annotations reused); 1.8–2.3 s (annotations created for each argument) | 0.56–0.79 s |
| Synthetic schema with 894 types and 82,738 arguments | 1.13 s | 1.85 s (annotations reused); 3.98 s (annotations created for each argument) | 0.26 s |
| `GraphQLSchemaManager.generate()` today, for comparison | 2.0–2.2 s, of which `graphene.Schema()` (called twice) is about 40% in a profile | | |

- Strawberry evaluates the type annotation of every argument separately. Reusing one `StrawberryAnnotation` object per GraphQL type halves the build time. A Strawberry generator must do this, because Infrahub schemas are dominated by filter arguments (for example, `CoreRepository` has 384 query arguments).
- `generate()` calls `graphene.Schema()` twice: once to build the partial schema for subscriptions, then for the final schema. This is a cost unrelated to the library choice.

### Executing queries

The test query returns 1,000 nodes, each with 8 attributes of 4 fields, one cardinality-one peer and one cardinality-many count. That makes about 40,000 resolved fields. The query is identical for the three builders.

| Resolvers | Graphene | Strawberry | graphql-core only |
|---|---|---|---|
| Synchronous | 172–177 ms | 191–210 ms | 177–188 ms |
| Asynchronous list and peer resolvers | 189–219 ms | 220–246 ms | 208–236 ms |
| Introspection of the synthetic schema | 1.73–2.23 s | 1.70–2.11 s | 1.75–2.04 s |

- Strawberry wraps every field. A field without a resolver goes through a wrapper and then the default resolver. A field with a resolver builds a Strawberry `Info` object and converts every declared argument. This is the source of the 10–20% overhead.
- In production, Neo4j queries and Infrahub's own resolver code are a large share of request time, so the change in total request time would be smaller than 10–20%. The exact share is not measured.
- graphql-core's per-field execution is the same in all three cases, so the rule in `dev/knowledge/backend/graphql-execution.md` (keep middleware synchronous) still applies.

### Current capabilities that become harder

- Adding fields to a type after it is created. Strawberry has no public API for this, so the POC appends to `__strawberry_definition__.fields`. Building fields in a second pass, after every class exists, avoids the mutation but changes the structure of `manager.py`.
- Reading the Infrahub schema back from the GraphQL type (`graphene_type._meta.schema`). Replace it with graphql-core's `extensions` dict on the type, or with a map from type name to schema in the GraphQL context.
- Raw graphql-core resolvers with dict inputs. Keeping them means either a wrapper that converts inputs back to dicts, which costs CPU, or rewriting the mutation code for input class instances.

### Possible improvements

- Moving to graphql-core 3.3, which Graphene blocks. This change did not measure any performance effect of graphql-core 3.3 itself.
- Python type checking of the static types and mutations, because Strawberry types are annotated classes.

## Alternative: build the generated schema directly with graphql-core

The POC also built the synthetic schema directly with graphql-core (`build_core.py`). The SDL was identical and the query results were identical.

| Criterion | Strawberry | graphql-core only |
|---|---|---|
| Fit for runtime generation | through internal objects | native: `GraphQLObjectType(name, fields=thunk, interfaces=...)`, and cycles resolve through thunks |
| Schema build time | about the same as Graphene | 40–77% less time than Graphene in the two tests |
| Per-field execution overhead | +10–20% | none added |
| Existing resolvers and dict inputs | need wrappers or a rewrite | unchanged |
| Static, hand-written types | annotated, type-checked classes | verbose definitions |
| Dependency risk | 0.x, frequent releases, internal APIs | reference implementation, already a direct dependency |

A combination is possible: hand-written types in Strawberry, and generated types in graphql-core, joined into one `GraphQLSchema`. The POC did not test this combination.

## POC files

The scripts are not part of Infrahub and do not import it. They run in their own virtual environment, because the Infrahub environment does not include Strawberry.

Set up the environment on the same graphql-core version as Infrahub (Strawberry 0.327.7 is the latest release that supports graphql-core 3.2):

```bash
cd poc/strawberry-graphql
uv venv .venv --python 3.14
uv pip install --python .venv/bin/python "graphql-core==3.2.8" "graphene==3.4.3" "strawberry-graphql==0.327.7"
```

To test the latest Strawberry on graphql-core 3.3 instead, install `"strawberry-graphql==0.334.3"` alone. Graphene must then be installed with `--no-deps`, because it requires graphql-core `<3.3`.

Scripts:

- `rebuild_real.py` rebuilds the real core schema with Strawberry and compares the SDL with the current one: `.venv/bin/python rebuild_real.py ../../schema/schema.graphql`
- `rebuild_real_graphene.py` does the same rebuild with Graphene, as the baseline for build time: `.venv/bin/python rebuild_real_graphene.py ../../schema/schema.graphql`
- `run.py` builds a synthetic Infrahub-like schema three ways and measures:
  - build time
  - query execution time
  - introspection time
  - mutation input handling

  Usage: `.venv/bin/python run.py --nodes 150 --generics 25 --attrs 8 --rels 6 --rows 1000`. It uses these builders:
  - `spec.py` defines the synthetic schema and query.
  - `build_graphene.py` builds it the way `backend/infrahub/graphql/manager.py` does today.
  - `build_strawberry.py` builds it with Strawberry. `build_strawberry_cached.py` is the same, except that it reuses one annotation object per argument type.
  - `build_core.py` builds it directly with graphql-core.
- `checks.py` compares enum serialization and DateTime parsing between Graphene and Strawberry: `.venv/bin/python checks.py`

`ruff.toml` limits linting in this directory to basic rules, because these are throwaway scripts.

## Sources

- Graphene repository: https://github.com/graphql-python/graphene
- Graphene on PyPI (3.4.3, 2024-11-09, `graphql-core<3.3,>=3.1`): https://pypi.org/project/graphene/
- Strawberry documentation: https://strawberry.rocks/docs
- Strawberry `create_type` and `merge_types`: https://strawberry.rocks/docs/guides/tools
- Strawberry on PyPI (0.334.3 requires `graphql-core<3.4.0,>=3.3.0`): https://pypi.org/project/strawberry-graphql/
- graphql-core on PyPI (3.3.0, 2026-09-27): https://pypi.org/project/graphql-core/
