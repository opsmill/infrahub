# Implementation Plan: GraphQL Fragment Inlining at Import

**Branch**: `infp-496-graphql-fragment-inlining` | **Date**: 2026-03-13
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)
**SDK Spec**: [python_sdk/dev/specs/infp-496-graphql-fragment-inlining/spec.md](../../../python_sdk/dev/specs/infp-496-graphql-fragment-inlining/spec.md)

## Summary

Allow users to declare reusable `.gql` fragment files in their repositories and reference them in query files using standard fragment spread syntax. During repository sync (and in `infrahubctl` local workflows), the SDK parses each query, resolves all direct and transitive fragment dependencies across the declared fragment files, and produces a fully-rendered, self-contained query document. No new database types are introduced.

## Technical Context

**Language/Version**: Python 3.13 (backend), Python 3.10–3.14 (SDK)
**Primary Dependencies**: `graphql-core` (already in SDK), FastAPI (backend), Pydantic 2.10
**Storage**: Neo4j (no schema change — `CoreGraphQLQuery.query` stores rendered string as before)
**Testing**: pytest (unit + component tests), Prefect task integration
**Target Platform**: Infrahub server (backend) + infrahubctl CLI (SDK)
**Project Type**: SDK library + server backend integration
**Performance Goals**: Fragment resolution is O(n) in fragments declared; no performance-sensitive path
**Constraints**: No new dependencies. No schema migration. Fragment logic must live in SDK (FR-015).
**Scale/Scope**: Per-repository; affects repository sync pipeline and CLI execution paths

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ Pass | No database schema changes. `CoreGraphQLQuery.query` stores rendered string as before. |
| II. Branch-Safe by Default | ✅ Pass | `import_all_graphql_query()` already handles branch context. Rendered query stored per branch. |
| III. Type Safety & Explicit Contracts | ✅ Pass | New SDK module uses full type hints; new error classes are typed Pydantic-style. |
| IV. Test Discipline | ✅ Pass | Unit tests (renderer logic) + component tests (sync pipeline) + fixture repos required. |
| V. Query Performance & Efficiency | ✅ Pass | Fragment resolution is a pure in-memory string operation; no database queries added. |
| VI. Security & Input Boundaries | ✅ Pass | Fragment file contents are read from a trusted git worktree (same trust level as query files). GraphQL `parse()` provides safe AST parsing. |
| VII. Simplicity & Maintainability | ✅ Pass | Single new SDK module. Backend change is minimal (pass fragment file contents into existing pipeline). |

**Complexity Tracking**: No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-496-graphql-fragment-inlining/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Research decisions
└── tasks.md             # Task breakdown (output of /speckit.tasks)

python_sdk/dev/specs/infp-496-graphql-fragment-inlining/
└── spec.md              # SDK-focused spec (fragment renderer, config model, CLI)
```

### Source Code

Primary changes are in the **Python SDK submodule** (`python_sdk/`), with a small backend integration change.

```text
python_sdk/
├── infrahub_sdk/
│   ├── graphql/
│   │   ├── query_renderer.py        # NEW — fragment parser, resolver, renderer
│   │   └── utils.py                 # unchanged
│   ├── schema/
│   │   └── repository.py            # MODIFY — add InfrahubRepositoryFragmentConfig + graphql_fragments field
│   ├── ctl/
│   │   ├── utils.py                 # MODIFY — apply fragment rendering in execute_graphql_query()
│   │   └── cli_commands.py          # MODIFY — apply fragment rendering in transform()
│   └── exceptions.py                # MODIFY — add GraphQLQueryError base + 5 typed exceptions
└── tests/
    ├── unit/sdk/graphql/
    │   ├── test_fragment_renderer.py  # NEW — tests for build_fragment_index, collect_required_fragments, render_query_with_fragments
    │   └── test_query_renderer.py     # NEW — tests for render_query() high-level entry point
    ├── unit/sdk/
    │   └── test_repository.py         # MODIFY — add graphql_fragments tests
    └── fixtures/repos/
        └── fragment_inlining/         # NEW — fixture repo with fragment files + queries

backend/
├── infrahub/git/
│   └── integrator.py                # MODIFY — pass fragment file contents into rendering pipeline
└── tests/component/git/
    └── test_graphql_query_import.py  # NEW or MODIFY — component test for fragment sync
```

**Structure Decision**: SDK-first. All fragment rendering logic is in `python_sdk/infrahub_sdk/graphql/fragment_renderer.py`. The backend change is additive — it reads declared fragment file contents and passes them into the SDK renderer before storing the result. The existing `import_all_graphql_query()` sync loop structure is preserved.

---

## Phase 1: SDK — Fragment Renderer (python_sdk)

All work in this phase is inside `python_sdk/`. See the [SDK spec](../../../python_sdk/dev/specs/infp-496-graphql-fragment-inlining/spec.md) for detailed API contracts.

### 1.1 Typed Error Exceptions

**File**: `python_sdk/infrahub_sdk/exceptions.py`

Add a base class plus five typed exception classes. All extend `GraphQLQueryError` which in turn extends `Error`:

```python
class GraphQLQueryError(Error):
    """Base class for all errors raised during GraphQL query rendering."""

class QuerySyntaxError(GraphQLQueryError):
    """A query string or fragment file contains invalid GraphQL syntax."""

class FragmentNotFoundError(GraphQLQueryError):
    """A query uses a fragment spread for which no definition was found."""
    fragment_name: str
    query_file: str | None = None

class DuplicateFragmentError(GraphQLQueryError):
    """The same fragment name appears more than once across declared fragment files."""
    fragment_name: str

class CircularFragmentError(GraphQLQueryError):
    """A circular dependency was detected among fragments."""
    cycle: list[str]

class FragmentFileNotFoundError(GraphQLQueryError):
    """A file declared under graphql_fragments does not exist in the repository."""
    file_path: str
```

Also update `handle_exception()` in `ctl/utils.py` to catch `GraphQLQueryError` so CLI commands print a clean error and exit.

### 1.2 Config Model Extension

**File**: `python_sdk/infrahub_sdk/schema/repository.py`

Add `InfrahubRepositoryFragmentConfig` (same structure as `InfrahubRepositoryGraphQLConfig`).
Add `graphql_fragments: list[InfrahubRepositoryFragmentConfig]` to `InfrahubRepositoryConfig`.
Add `has_fragment(name: str) -> bool` and `get_fragment(name: str) -> InfrahubRepositoryFragmentConfig` methods to `InfrahubRepositoryConfig`, following the same pattern as `has_query` / `get_query`.

```python
class InfrahubRepositoryFragmentConfig(InfrahubRepositoryConfigElement):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Logical name for this fragment file or directory")
    file_path: Path = Field(..., description="Path to a .gql fragment file or a directory of .gql files, relative to repo root")

    def load_fragments(self, relative_path: str = ".") -> list[str]:
        """Return raw content of all fragment files at file_path.

        If file_path is a .gql file, returns a single-element list.
        If file_path is a directory, returns one entry per .gql file found.
        Raises FragmentFileNotFoundError if file_path does not exist.
        """
        resolved = Path(f"{relative_path}/{self.file_path}")
        if not resolved.exists():
            raise FragmentFileNotFoundError(file_path=str(self.file_path))
        if resolved.is_dir():
            return [f.read_text(encoding="UTF-8") for f in sorted(resolved.glob("*.gql"))]
        return [resolved.read_text(encoding="UTF-8")]
```

### 1.3 Fragment Renderer Module

**File**: `python_sdk/infrahub_sdk/graphql/query_renderer.py` (new)

Public functions — all importable by callers:

**`build_fragment_index(fragment_files)`**:

- Signature: `build_fragment_index(fragment_files: list[str]) -> dict[str, FragmentDefinitionNode]`
- Parse each string with `graphql.parse()` — raise `QuerySyntaxError` on invalid syntax
- Extract all `FragmentDefinitionNode` entries across all strings
- Raise `DuplicateFragmentError` if any fragment name appears more than once (whether within a single string or across multiple strings)
- Return `dict[str, FragmentDefinitionNode]`

**`collect_required_fragments(query_doc, fragment_index)`**:

- Walk `query_doc` collecting all `FragmentSpreadNode` names from operation definitions only (not from inline fragment definitions already present in the query)
- Recursively collect spreads within each required fragment's definition
- Detect cycles with a visited set + recursion stack → raise `CircularFragmentError`
- Raise `FragmentNotFoundError` for any unresolved name
- Return ordered list of required fragment names (topological order, each once)

**`render_query_with_fragments(query_str, fragment_files) -> str`** (low-level public entry point):

- Signature: `render_query_with_fragments(query_str: str, fragment_files: list[str]) -> str`
- If query has no spreads → return `query_str` unchanged (FR-011)
- Build fragment index (across all strings in `fragment_files`), collect required, assemble output `DocumentNode`
- Return `graphql.print_ast(output_doc)`

**`render_query(name, config, relative_path) -> str`** (high-level public entry point):

- Signature: `render_query(name: str, config: InfrahubRepositoryConfig, relative_path: str = ".") -> str`
- Load the query file from config, parse it; return raw string if no spreads or no `graphql_fragments` declared
- Load all declared fragment file contents, delegate to `render_query_with_fragments`
- This is the entry point used by both `infrahubctl` CLI paths and the backend `import_all_graphql_query()`

### 1.4 Unit Tests

**File**: `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py` (new) — tests for low-level functions:

- Single direct spread from one file → renders correctly
- Spreads across two files → renders both
- Transitive dependency across files → both included
- No spreads in query → returned unchanged
- Same spread used twice → definition appears once
- Surplus fragment definitions excluded from output
- `FragmentNotFoundError` for unresolved spread
- `DuplicateFragmentError` for same name in two files
- `CircularFragmentError` for A→B→A cycle
- `QuerySyntaxError` for invalid syntax in query or fragment file
- Inline fragments (`... on TypeName { }`) do not trigger external resolution

**File**: `python_sdk/tests/unit/sdk/graphql/test_query_renderer.py` (new) — tests for `render_query()`:

- Loads query + fragments from config, returns rendered document
- With no `graphql_fragments` in config → returns query unchanged

Also extend `python_sdk/tests/unit/sdk/test_repository.py`:

- Parse `.infrahub.yml` with `graphql_fragments`
- `load_fragments()` reads content
- `load_fragments()` raises `FragmentFileNotFoundError` for missing file

---

## Phase 2: Backend — Import Pipeline (backend/)

### 2.1 Update `import_all_graphql_query()`

**File**: `backend/infrahub/git/integrator.py`

Replace the `load_query()` call with `render_query()`. Any SDK error (missing fragment, duplicate, circular, missing file) fails the sync immediately (FR-009):

```python
local_queries: dict[str, str] = {}
for query_config in config_file.queries:
    try:
        local_queries[query_config.name] = render_query(
            name=query_config.name,
            config=config_file,
            relative_path=commit_wt.directory,
        )
    except InfrahubSdkError as exc:
        log.error(f"Query '{query_config.name}': {exc}")
        raise
```

The compare/create/update/delete loop below is unchanged.

### 2.2 Fixture Repos

**Location**: `python_sdk/tests/fixtures/repos/fragment_inlining/`

```text
.infrahub.yml
fragments/
  interfaces.gql    # defines interfaceFragment, portFragment
  devices.gql       # defines deviceFragment, chassisFragment
queries/
  query_two_files.gql        # uses ...interfaceFragment ...deviceFragment
  query_no_fragments.gql     # no spreads
  query_transitive.gql       # uses ...deviceFragment (which uses ...interfaceFragment)
  query_missing_fragment.gql # uses ...undeclaredFragment
```

### 2.3 Component Tests

**File**: `backend/tests/component/git/test_graphql_query_import.py`

Scenarios mapping to spec user stories:

- US1: Sync repo with two fragment files → stored query contains only the two referenced fragments
- US1 SC3: Query with no spreads → stored unchanged
- US2: Transitive dependency → both fragments in output
- US4: Unresolved fragment → sync fails with `FragmentNotFoundError` identifying the missing fragment
- US5: Re-sync after fragment file change → stored query reflects updated definition
- Edge: Missing fragment file → sync error identifying the file

---

## Phase 3: infrahubctl CLI Integration (python_sdk)

### 3.1 `ctl/utils.py`

Update `execute_graphql_query()` to call `render_query()` instead of `load_query()`:

```python
# Before
query_str = query_object.load_query()

# After
query_str = render_query(name=query, config=repository_config)
```

### 3.2 `ctl/cli_commands.py`

In `transform()` where `load_query()` is called directly, apply the same `render_query()` pattern:

```python
# Before
query_str = repository_config.get_query(name=transform.query).load_query()

# After
query_str = render_query(name=transform.query, config=repository_config)
```

---

## Phase 4: Documentation & Changelog

- **Changelog fragment** in `changelog/` — user-facing entry describing `graphql_fragments` support
- **Docs** in `docs/` — update `.infrahub.yml` reference page with `graphql_fragments` section
- **SDK docs** — run `uv run invoke docs-generate` after docstring changes (AGENTS.md requirement)

---

## Execution Order

```text
1. SDK 1.1 — exceptions            (no deps)
2. SDK 1.2 — config model          (depends on 1.1)
3. SDK 1.3 — fragment renderer     (depends on 1.1)
4. SDK 1.4 — unit tests            (depends on 1.2, 1.3)
5. SDK 3   — CLI integration       (depends on 1.2, 1.3)
6. Backend 2 — import pipeline     (depends on SDK 1.1–1.3)
7. Phase 4 — docs and changelog    (last)
```

Phases 1.1–1.4 can be developed and tested entirely within `python_sdk/` before touching the backend.

---

## Out of Scope

- Fragment type condition validation at import time (deferred to execution per spec Assumptions)
- Cross-repository fragment references (explicitly excluded by spec)
- New database object type for fragment files (explicitly excluded by spec)
- Frontend changes (feature is import-pipeline and CLI only)
