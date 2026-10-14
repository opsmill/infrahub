# Replacing Graphene with Strawberry in the Infrahub GraphQL API

## Summary

- **The problem.** Graphene 3.4.3, released on 2024-11-09, is the latest release. It requires graphql-core `<3.3`, and graphql-core 3.3.0 was released on 2026-09-27. Strawberry 0.328 and later require graphql-core `>=3.3`. Infrahub cannot move to graphql-core 3.3 while it depends on Graphene.
- **What the POC shows.** Strawberry can generate the whole Infrahub schema at runtime. The test rebuilt the real `schema/schema.graphql` (1,227 types, 4,080 fields, 22,153 arguments) with Strawberry, and the printed SDL is identical to what Graphene produces today. The result is the same on Strawberry 0.327.7 with graphql-core 3.2.8 and on Strawberry 0.334.3 with graphql-core 3.3.0.
- **Breaking changes.** The GraphQL interface does not need to change. The remaining risks are server-side behaviour differences, listed below, that tests have to cover.
- **Performance.** Building the schema takes about the same time. Executing queries costs 10–20% more CPU in the GraphQL layer, measured without a database. Introspection takes the same time.
- **Combined design.** The POC also built the real schema from two parts: hand-written types with Strawberry, built once per process, and generated types with graphql-core, built for each schema. The SDL is identical. The generated part and the join take 0.11–0.12 s per schema, against 1.06–1.38 s for the same work with Graphene. Generated fields run without Strawberry's per-field overhead, and the existing generated resolvers keep receiving dicts.
- **Not decided.** It is not decided whether the hand-written part uses Strawberry or graphql-core. It is also not decided how the 16 hand-written types that depend on the Infrahub schema are written.

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

## Combined design: graphql-core for generated types, Strawberry for hand-written types

### Which types are hand-written and which are generated

`classify_types.py` sorts every type of the core schema into one of three groups. A type counts as generated when its name is a schema kind, or a kind with a prefix (`Edged`, `NestedEdged`, `Paginated`, `NestedPaginated`) or a suffix (`Create`, `Update`, `Upsert`, `Delete`, `CreateInput`, `UpdateInput`, `UpsertInput`).

| Group | Types | Root fields | Built |
|---|---|---|---|
| Hand-written types that do not depend on the Infrahub schema | 239 | Query 26, Mutation 37, Subscription 1 | once per process |
| Hand-written types that depend on the Infrahub schema | 16 | Query 2 (`InfrahubBranch`, `InfrahubRepositoryBranchStatus`) | for each schema |
| Generated types | 961 | Query 92, Mutation 269 | for each schema |

The 16 schema-dependent hand-written types are the types that `manager.py` changes at runtime today:

- 11 attribute types (`TextAttribute`, `NumberAttribute`, `Dropdown`, …). Their `source`, `owner` and `updated_by` fields return the generated types `LineageSource`, `LineageOwner` and `CoreGenericAccount`.
- `InfrahubBranchEdge` and `InfrahubRepositoryBranchStatusEdge`. Their `node_metadata` field returns the generated type `InfrahubNodeMetadata`.
- The 3 types that contain these edges: `InfrahubBranchType`, `InfrahubRepositoryBranchStatus` and `InfrahubRepositoryBranchStatusType`.

In the other direction, generated types use hand-written types for these purposes:

- scalars
- attribute input types (`TextAttributeCreate`, `TextAttributeUpdate`, …)
- the ordering input (`OrderInput`)
- the inputs that reference peers (`RelatedNodeInput`, `RelatedIPPrefixNodeInput`, `RelatedIPAddressNodeInput`)
- `PaginatedObjectPermission`

The hand-written interface `AttributeInterface` has its 11 implementations in the generated part.

### How the two parts are joined

1. Build the hand-written part with Strawberry, once per process. Its root types hold only the hand-written root fields.
2. For each Infrahub schema, build the generated types with graphql-core. A reference to a hand-written type uses the type object from the hand-written graphql-core schema.
3. Create new root types that hold the hand-written root fields plus the generated root fields. Then create one `GraphQLSchema` with both sets of types and the `@expand` directive.
4. Set `schema._strawberry_schema` to the Strawberry schema, because Strawberry's `Info.schema` reads it. This is a private attribute.

`combined.py` does this on the real core schema. Steps 2 and 3 take about 120 lines.

### Results on the real core schema

The results are the same on Strawberry 0.327.7 with graphql-core 3.2.8 and on Strawberry 0.334.3 with graphql-core 3.3.0.

- **SDL.** The combined schema prints the same SDL as today (30,412 lines after sorting).
- **Build time.** The times below cover only the creation of GraphQL types. They do not include the Infrahub code that reads the schema nodes and computes the filter arguments, which runs in every option.

  | Option | Hand-written part, once per process | Per schema |
  |---|---|---|
  | Graphene, whole schema | not separate | 1.06–1.38 s |
  | Strawberry, whole schema | not separate | 0.88–1.12 s |
  | Combined design | 0.09 s | 0.11–0.12 s |

- **One process, several branches.** Two schemas built one after the other share the same 239 hand-written type objects, and both execute queries.
- **Queries across the two parts.** One query reads the hand-written root field `Branch` (Strawberry resolver) and the generated root field `BuiltinTag`, with an `OrderInput` argument and an attribute `source` that returns an interface. It runs without errors.
- **Values that resolvers receive.**
  - The generated resolver receives the hand-written `OrderInput` as a dict, with enum values as Python enum members. This is the shape the current resolvers expect.
  - The hand-written mutation `BranchCreate` receives an instance of the Strawberry input class (`data.name`). The 37 static mutations already read their input by attribute, as in `data.name`.
- **Execution cost.** Generated fields run without Strawberry's wrapper, like the graphql-core column of the synthetic test. Hand-written fields pay Strawberry's per-field overhead. This matters for hand-written queries with large responses, such as the diff tree. That cost is not measured.

### Work the combined design requires

- **Generated part (rewrite of `manager.py`):**
  - Build graphql-core types, and add peers through field thunks instead of writing to `_meta.fields`.
  - Store the Infrahub schema in the `extensions` dict of each graphql-core type, and read it there in the 6 resolvers that use `graphene_type._meta.schema` today.
  - Turn the 15 mutation templates into plain classes. Each generated mutation field calls `mutate` with its schema, and `mutate` returns a dict instead of `cls(**result)`.
  - Change `InfrahubDataType` (`backend/infrahub/types.py`) to declare graphql-core types instead of Graphene classes.
  - Write the 16 schema-dependent hand-written types in graphql-core, inside the generated part.
- **Hand-written part:** rewrite 239 types and 64 root fields as Strawberry classes:
  - Enums wrap the existing Python enums.
  - `GenericScalar`, `FixedGenericScalar`, `Upload` and `BigInt` keep their names.
  - The event and task interfaces keep their `resolve_type`.
- **Strawberry APIs used.** The hand-written part uses only the documented decorators, plus the private `_strawberry_schema` link. The internal objects that whole-schema generation with Strawberry needs are not used: added fields, argument lists and `info._raw_info`.
- **Hand-written part without Strawberry.** The hand-written part can also be written in graphql-core, with the same join. This removes the Strawberry dependency, but the definitions are longer and Python type checking does not cover them.

### Risks of the combined design

- The hand-written type objects are shared by every schema in the process, so nothing may change them after they are built.
- The root types list the hand-written root fields first. Whether this matches Graphene's current field order in introspection is not verified.
- The Strawberry version still needs a pin, but the design depends on fewer Strawberry internals than whole-schema generation does.

## POC files

The scripts are not part of Infrahub and, except `classify_types.py`, do not import it. They run in their own virtual environment, because the Infrahub environment does not include Strawberry.

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
- `combined.py` builds the combined design on the real core schema and runs the checks above: `.venv/bin/python combined.py ../../schema/schema.graphql`
- `classify_types.py` writes `type_classification.json`, which `combined.py` reads. It needs the Infrahub environment: `uv run python poc/strawberry-graphql/classify_types.py` from the repository root.

`ruff.toml` limits linting in this directory to basic rules, because these are throwaway scripts.

## Sources

- Graphene repository: https://github.com/graphql-python/graphene
- Graphene on PyPI (3.4.3, 2024-11-09, `graphql-core<3.3,>=3.1`): https://pypi.org/project/graphene/
- Strawberry documentation: https://strawberry.rocks/docs
- Strawberry `create_type` and `merge_types`: https://strawberry.rocks/docs/guides/tools
- Strawberry on PyPI (0.334.3 requires `graphql-core<3.4.0,>=3.3.0`): https://pypi.org/project/strawberry-graphql/
- graphql-core on PyPI (3.3.0, 2026-09-27): https://pypi.org/project/graphql-core/
