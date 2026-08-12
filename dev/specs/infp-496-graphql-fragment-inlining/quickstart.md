# Quickstart: Implementing GraphQL Fragment Inlining

**Feature**: `infp-496-graphql-fragment-inlining`
**For**: Implementors working on this feature

---

## What You're Building

Users declare reusable `.gql` fragment files in their repositories. During repo sync (and
`infrahubctl` local workflows), the SDK resolves all fragment spreads — direct and transitive —
and stores a single, self-contained query document. No new DB types. No runtime resolution.

## Key Constraint

**All fragment logic lives in the Python SDK (`python_sdk/`), not in `backend/`.** The backend
calls SDK functions. It never duplicates the logic (FR-015).

---

## Implementation Order

```text
1. SDK: exceptions.py          → 4 new error classes
2. SDK: schema/repository.py   → InfrahubRepositoryFragmentConfig + graphql_fragments field
3. SDK: graphql/fragment_renderer.py  → new module (public: render_query_with_fragments)
4. SDK: tests/unit/            → unit tests for renderer + repository model
5. SDK: ctl/utils.py + ctl/cli_commands.py  → infrahubctl CLI integration
6. Backend: git/integrator.py  → call SDK renderer in import_all_graphql_query()
7. Backend: tests/component/   → component tests for full sync pipeline
8. Phase 4: changelog + docs
```

Phases 1–5 can be completed and tested entirely within `python_sdk/` before touching the backend.

---

## Step 1: Add Error Classes

**File**: `python_sdk/infrahub_sdk/exceptions.py`

Add after the existing `Error` base class pattern:

```python
class FragmentNotFoundError(Error):
    fragment_name: str
    query_file: str | None = None

class DuplicateFragmentError(Error):
    fragment_name: str

class CircularFragmentError(Error):
    cycle: list[str]

class FragmentFileNotFoundError(Error):
    file_path: str
```

Check how existing error classes are structured in that file — match the pattern exactly.

---

## Step 2: Extend Config Model

**File**: `python_sdk/infrahub_sdk/schema/repository.py`

1. Find `InfrahubRepositoryGraphQLConfig` — your new class mirrors it.
2. Add `InfrahubRepositoryFragmentConfig` with `name: str` and `file_path: Path`.
3. Add `load_fragments(relative_path: str = ".") -> list[str]` method.
4. Add `graphql_fragments: list[InfrahubRepositoryFragmentConfig] = Field(default_factory=list)`
   to `InfrahubRepositoryConfig`.

See `contracts/sdk-fragment-renderer.md` for the full class definition.

---

## Step 3: Write the Fragment Renderer

**File**: `python_sdk/infrahub_sdk/graphql/fragment_renderer.py` (new file)

Dependencies already available: `graphql.parse`, `graphql.print_ast`,
`graphql.language.ast.FragmentDefinitionNode`, `graphql.language.ast.FragmentSpreadNode`,
`graphql.language.visitor.Visitor`, `graphql.language.visitor.visit`.

Three functions:

**`build_fragment_index(fragment_files: list[str]) -> dict[str, FragmentDefinitionNode]`**:
- Parse each string with `graphql.parse()`
- Collect all `FragmentDefinitionNode` across all strings
- Raise `DuplicateFragmentError` on any duplicate name
- Return the dict

**`collect_required_fragments(query_doc, fragment_index) -> list[str]`**:
- Walk the doc with a `Visitor` collecting `FragmentSpreadNode.name.value` entries
- For each spread found, recursively collect spreads within that fragment's definition
- Track a `visiting` set (recursion stack) to detect cycles → `CircularFragmentError`
- Track a `visited` set to avoid reprocessing
- Raise `FragmentNotFoundError` for unknown names
- Return a topologically ordered list (each name once)

**`render_query_with_fragments(query_str, fragment_files) -> str`** (the public entry point):
- Early return if `fragment_files` is empty or query has no spreads
- Call `build_fragment_index(fragment_files)`
- Parse `query_str` into `query_doc`
- Call `collect_required_fragments(query_doc, fragment_index)`
- Assemble output `DocumentNode` from query operation nodes + required fragment nodes
- Return `graphql.print_ast(output_doc)`

---

## Step 4: Unit Tests

**File**: `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py` (new)

Must cover (see `python_sdk/dev/specs/infp-496-graphql-fragment-inlining/spec.md` for details):

- Direct spread from one file → rendered correctly
- Spreads across two files → both rendered
- Transitive dependency (A uses B, B in different file) → both included
- No spreads → query returned unchanged
- Same spread used twice → definition appears once
- Surplus definitions excluded
- `FragmentNotFoundError` for unresolved spread
- `DuplicateFragmentError` for duplicate name
- `CircularFragmentError` for A→B→A cycle

**File**: `python_sdk/tests/unit/sdk/test_repository.py` (modify)

- Parse `.infrahub.yml` with `graphql_fragments` section
- `load_fragments()` for a file path returns single-element list
- `load_fragments()` for a directory returns one entry per `.gql` file
- `load_fragments()` raises `FragmentFileNotFoundError` for missing path

---

## Step 5: infrahubctl Integration

**File**: `python_sdk/infrahub_sdk/ctl/utils.py`

Find `execute_graphql_query()`. Before calling `client.execute_graphql(query=...)`:

```python
all_fragment_contents: list[str] = []
for frag in repository_config.graphql_fragments:
    all_fragment_contents.extend(frag.load_fragments())
query_str = render_query_with_fragments(
    query_str=query_object.load_query(),
    fragment_files=all_fragment_contents,
)
```

**File**: `python_sdk/infrahub_sdk/ctl/cli_commands.py`

Find `transform()` (~line 345). Same pattern where `load_query()` is called before execution.

---

## Step 6: Backend Integration

**File**: `backend/infrahub/git/integrator.py`

Find `import_all_graphql_query()` (~line 574). See `contracts/sdk-fragment-renderer.md` for
the exact code pattern to insert.

Key points:
- `FragmentFileNotFoundError` re-raises (halts the sync — FR-008)
- Per-query errors (`FragmentNotFoundError`, `DuplicateFragmentError`, `CircularFragmentError`)
  are logged and that query is skipped; other queries continue (FR-009)

---

## Step 7: Fixture Repository

**Location**: `python_sdk/tests/fixtures/repos/fragment_inlining/`

Create this structure:

```text
.infrahub.yml
fragments/
  interfaces.gql    # defines interfaceFragment, portFragment
  devices.gql       # defines deviceFragment (uses ...interfaceFragment), chassisFragment
queries/
  query_two_files.gql        # uses ...interfaceFragment ...deviceFragment
  query_no_fragments.gql     # no spreads — stored as-is
  query_transitive.gql       # uses ...deviceFragment only (transitive resolves interfaceFragment)
  query_missing_fragment.gql # uses ...undeclaredFragment — should fail with clear error
```

`.infrahub.yml` example:

```yaml
graphql_fragments:
  - name: interface_fragments
    file_path: fragments/interfaces.gql
  - name: device_fragments
    file_path: fragments/devices.gql
graphql_queries:
  - name: query_two_files
    file_path: queries/query_two_files.gql
  - name: query_no_fragments
    file_path: queries/query_no_fragments.gql
  - name: query_transitive
    file_path: queries/query_transitive.gql
  - name: query_missing_fragment
    file_path: queries/query_missing_fragment.gql
```

---

## Step 8: Component Tests

**File**: `backend/tests/component/git/test_graphql_query_import.py`

Map each test to a User Story:

| Test | User Story |
|---|---|
| Two fragment files, query uses one from each → stored query has exactly those two | US1 |
| Query with no spreads → stored unchanged | US1 SC3 |
| Transitive dependency → both definitions in output | US2 |
| Unresolved fragment → that query errors, others succeed | US4 |
| Re-sync after fragment change → stored query updated | US5 |
| Missing fragment file path → sync error with path in message | Edge case |

---

## Verify Your Work

```bash
# SDK unit tests
cd python_sdk && uv run pytest tests/unit/sdk/graphql/test_fragment_renderer.py -v
cd python_sdk && uv run pytest tests/unit/sdk/test_repository.py -v -k fragment

# Backend component tests
uv run pytest backend/tests/component/git/test_graphql_query_import.py -v

# Linting (SDK)
cd python_sdk && uv run invoke format lint-code

# Linting (backend)
uv run invoke format lint
```

---

## Key Files Reference

| File | Action |
|---|---|
| `python_sdk/infrahub_sdk/exceptions.py` | Add 4 error classes |
| `python_sdk/infrahub_sdk/schema/repository.py` | Add fragment config model + field |
| `python_sdk/infrahub_sdk/graphql/fragment_renderer.py` | New module |
| `python_sdk/infrahub_sdk/ctl/utils.py` | Apply rendering in execute_graphql_query() |
| `python_sdk/infrahub_sdk/ctl/cli_commands.py` | Apply rendering in transform() |
| `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py` | New unit tests |
| `python_sdk/tests/fixtures/repos/fragment_inlining/` | New fixture repo |
| `backend/infrahub/git/integrator.py` | Call SDK renderer in import pipeline |
| `backend/tests/component/git/test_graphql_query_import.py` | New component tests |
| `changelog/` | Towncrier fragment |
| `docs/` | Update .infrahub.yml reference |
