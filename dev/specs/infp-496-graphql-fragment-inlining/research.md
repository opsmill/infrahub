# Research: GraphQL Fragment Inlining

**Feature**: `infp-496-graphql-fragment-inlining`

---

## Decision: GraphQL Parsing Library

**Decision**: Use `graphql-core` (already a dependency in `python_sdk/`) for all fragment parsing and AST manipulation.

**Rationale**: `graphql-core` is already imported in `python_sdk/infrahub_sdk/graphql/utils.py` (`FragmentDefinitionNode`, `FragmentSpreadNode`, `OperationDefinitionNode`, etc.). It provides `parse()` for turning raw `.gql` text into an AST and `print_ast()` for serializing back to a string. No new dependency is needed.

**Key APIs used**:
- `graphql.parse(source: str) -> DocumentNode` — parse a `.gql` file into an AST
- `graphql.print_ast(ast: DocumentNode) -> str` — serialize AST back to GraphQL string
- `graphql.language.ast.FragmentDefinitionNode` — a fragment definition (`fragment Foo on Bar { ... }`)
- `graphql.language.ast.FragmentSpreadNode` — a use of a fragment (`...Foo`)
- `graphql.language.visitor.Visitor` + `visit()` — walk the AST to collect all spreads

**Alternatives considered**: Hand-written regex/string parsing — rejected for fragility with multi-line fragments and nested spreads.

---

## Decision: Where Fragment Resolution Logic Lives

**Decision**: All fragment parsing, resolution, and rendering logic lives in the Python SDK (`python_sdk/infrahub_sdk/`), not in the backend server.

**Rationale**: Mandated by FR-015 and the spec's Architecture section. `infrahubctl` executes queries from the local filesystem without a server import step, so fragment rendering must be available client-side. The backend's `import_all_graphql_query()` (in `backend/infrahub/git/integrator.py:574`) already calls `query.load_query()` — it will call the new SDK rendering function instead.

---

## Decision: SDK Spec in Submodule

**Decision**: A separate SDK-focused spec is created at `python_sdk/dev/specs/infp-496-graphql-fragment-inlining/spec.md` alongside this main repo plan.

**Rationale**: The SDK submodule has its own `.specify/` and `dev/` structure. The `dev/specs/` directory doesn't exist yet in the SDK, but the intent is for specs to live there for SDK features. Since FR-015 assigns all fragment rendering responsibility to the SDK, a focused spec there documents the SDK contract independently of the main repo. The main repo plan is authoritative for the overall feature; the SDK spec scopes to SDK responsibilities.

---

## Decision: New SDK Module Placement

**Decision**: New module `python_sdk/infrahub_sdk/graphql/fragment_renderer.py`.

**Rationale**: Existing `graphql/utils.py` contains `strip_typename_*` and `insert_fragments_inline` — both are Python AST utilities for code generation, not for GraphQL fragment inlining at import time. Keeping responsibilities separate avoids overloading that module. The new module slots naturally into the existing `graphql/` package alongside `utils.py`, `renderers.py`, etc.

**Alternatives considered**: Adding to `graphql/utils.py` — rejected because that file already handles a different concern (Python AST for code generation) and the new feature is substantial enough to warrant its own module.

---

## Decision: Error Handling Strategy

**Decision**: Fragment errors (missing fragment, duplicate name, cycle) raise typed exceptions in the SDK, caught by the backend's `import_all_graphql_query()` which logs per-query errors and continues importing other queries (satisfying FR-009).

**Key error types** (added to `python_sdk/infrahub_sdk/exceptions.py`):
- `FragmentNotFoundError(fragment_name, query_file)` — spread references unknown fragment (FR-007)
- `DuplicateFragmentError(fragment_name)` — same name defined twice across fragment files (FR-013)
- `CircularFragmentError(cycle_path)` — cycle detected during transitive resolution (FR-014)
- `FragmentFileNotFoundError(file_path)` — declared fragment file doesn't exist (FR-008)

---

## Decision: Config Model Extension Pattern

**Decision**: Add `InfrahubRepositoryFragmentConfig(name, file_path)` and `graphql_fragments: list[InfrahubRepositoryFragmentConfig]` to `InfrahubRepositoryConfig`, following the exact same pattern as `InfrahubRepositoryGraphQLConfig` / `queries`.

**YAML representation**:
```yaml
graphql_fragments:
  - name: interface_fragments
    file_path: fragments/interfaces.gql
  - name: device_fragments
    file_path: fragments/devices.gql
```

---

## Decision: Rendering Entry Point API

**Decision**: The renderer exposes a single top-level function:

```python
def render_query_with_fragments(
    query_str: str,
    fragment_files: dict[str, str],  # {logical_name_or_path: file_content}
) -> str:
```

The backend and `infrahubctl` pass the raw fragment file contents (already read from disk). The renderer parses them, builds the index, resolves transitive dependencies, and returns the fully-rendered query string. Queries with no fragment spreads are returned unchanged (FR-011).

**Alternatives considered**: Passing `Path` objects and having the renderer read files — rejected because the backend reads files from a git worktree directory and the SDK should not know about worktree paths. Passing pre-read content keeps the renderer pure and trivial to unit-test.

---

## Decision: infrahubctl Integration Points

The following `infrahubctl` call sites need updating to apply fragment rendering:

1. `ctl/utils.py:execute_graphql_query()` (line 109) — calls `query_object.load_query()` then `client.execute_graphql()`
2. `ctl/cli_commands.py:transform()` (line 345) — calls `repository_config.get_query(name=...).load_query()`

The `find_graphql_query()` path (line 159) scans for `.gql` files by name without a config context and cannot apply fragment rendering — acceptable because that path is used for schema inspection and code generation, not execution.

The cleanest approach: add a `render_query(relative_path, fragment_index)` method to `InfrahubRepositoryGraphQLConfig`, and update `execute_graphql_query()` to build the fragment index from `InfrahubRepositoryConfig.graphql_fragments` before executing.

---

## Decision: No New Database Schema Objects

**Decision**: Fragment files are not stored in the database. `CoreGraphQLQuery` continues to store a fully-rendered query string. No schema migration or `backend.generate` needed.

**Rationale**: Explicit spec requirement — "No new database object types are introduced." The rendered query is the only persisted artifact.

---

## Key File Locations

| What | Where |
|------|-------|
| SDK config model | `python_sdk/infrahub_sdk/schema/repository.py` |
| New fragment renderer | `python_sdk/infrahub_sdk/graphql/fragment_renderer.py` (new) |
| Existing graphql utils | `python_sdk/infrahub_sdk/graphql/utils.py` |
| SDK exceptions | `python_sdk/infrahub_sdk/exceptions.py` |
| Backend import pipeline | `backend/infrahub/git/integrator.py:574–630` |
| infrahubctl query execution | `python_sdk/infrahub_sdk/ctl/utils.py:109` |
| infrahubctl cli_commands | `python_sdk/infrahub_sdk/ctl/cli_commands.py:345` |
| SDK unit tests | `python_sdk/tests/unit/sdk/graphql/` |
| Backend component tests | `backend/tests/component/git/` |
| Fixture repos | `python_sdk/tests/fixtures/repos/` |
