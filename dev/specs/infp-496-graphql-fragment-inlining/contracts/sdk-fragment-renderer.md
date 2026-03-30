# SDK Contract: Fragment Renderer

**Module**: `infrahub_sdk/graphql/fragment_renderer.py`
**Feature**: `infp-496-graphql-fragment-inlining`

---

## Public API

### `render_query_with_fragments`

```python
def render_query_with_fragments(
    query_str: str,
    fragment_files: list[str],
) -> str:
```

**Purpose**: Render a GraphQL query by inlining all required fragment definitions. Returns a
self-contained, executable GraphQL document string.

**Parameters**:

| Name | Type | Description |
|---|---|---|
| `query_str` | `str` | Raw GraphQL query document (operation definition, optionally with inline fragment defs) |
| `fragment_files` | `list[str]` | List of raw fragment file contents. Each string must be a valid GraphQL document containing only `fragment` definitions. |

**Returns**: `str` — A single valid GraphQL document containing the operation followed by all
required fragment definitions (directly or transitively referenced). Fragment definitions appear
in topological order (depended-upon fragments before their dependents).

**Guarantees**:

- If `fragment_files` is empty, returns `query_str` unchanged.
- If `query_str` contains no fragment spreads, returns `query_str` unchanged (FR-011).
- Each required fragment definition appears exactly once in the output, regardless of how many
  times the spread appears in the query (FR-005).
- Fragment definitions not required by the query are excluded from the output (FR-005).
- The output is formatted by `graphql.print_ast()` — whitespace may differ from the input.

**Raises**:

| Exception | Condition |
|---|---|
| `FragmentNotFoundError` | A spread references a name not found in any `fragment_files` entry (FR-007) |
| `DuplicateFragmentError` | The same fragment name is defined more than once across `fragment_files` (FR-013) |
| `CircularFragmentError` | A circular dependency chain is detected among fragments (FR-014) |

**Example**:

```python
query_str = """
query GetDevice($id: String!) {
  InfraDevice(ids: [$id]) {
    edges {
      node {
        ...deviceFragment
      }
    }
  }
}
"""

interfaces_gql = """
fragment interfaceFragment on InfraInterface {
  name { value }
  speed { value }
}
"""

devices_gql = """
fragment deviceFragment on InfraDevice {
  hostname { value }
  interfaces {
    edges {
      node {
        ...interfaceFragment
      }
    }
  }
}
"""

result = render_query_with_fragments(
    query_str=query_str,
    fragment_files=[interfaces_gql, devices_gql],
)
# result contains query operation + interfaceFragment + deviceFragment definitions
```

---

## Internal Functions (not public API)

### `build_fragment_index`

```python
def build_fragment_index(
    fragment_files: list[str],
) -> dict[str, FragmentDefinitionNode]:
```

Parses each string in `fragment_files` using `graphql.parse()`. Extracts all
`FragmentDefinitionNode` entries. Raises `DuplicateFragmentError` if any fragment name appears
more than once (across or within strings). Returns a dict mapping fragment name to its AST node.

### `collect_required_fragments`

```python
def collect_required_fragments(
    query_doc: DocumentNode,
    fragment_index: dict[str, FragmentDefinitionNode],
) -> list[str]:
```

Walks `query_doc` collecting all `FragmentSpreadNode` names (direct). Recursively collects
spreads within each required fragment's definition (transitive). Detects cycles using a visited
set and recursion stack; raises `CircularFragmentError` on cycle detection. Raises
`FragmentNotFoundError` for any unresolved name. Returns an ordered list of required fragment
names in topological order (each name appears exactly once).

---

## Error Types (additions to `infrahub_sdk/exceptions.py`)

```python
class FragmentNotFoundError(Error):
    """A query uses a fragment spread for which no definition was found."""
    fragment_name: str
    query_file: str | None = None

class DuplicateFragmentError(Error):
    """The same fragment name appears more than once across declared fragment files."""
    fragment_name: str

class CircularFragmentError(Error):
    """A circular dependency was detected among fragments."""
    cycle: list[str]

class FragmentFileNotFoundError(Error):
    """A file declared under graphql_fragments does not exist in the repository."""
    file_path: str
```

---

## Config Model Contract

### `InfrahubRepositoryFragmentConfig`

**Module**: `infrahub_sdk/schema/repository.py`

```python
class InfrahubRepositoryFragmentConfig(InfrahubRepositoryConfigElement):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Logical name for this fragment file or directory")
    file_path: Path = Field(
        ...,
        description="Path to a .gql fragment file or a directory of .gql files, relative to repo root",
    )

    def load_fragments(self, relative_path: str = ".") -> list[str]:
        """Return raw content of all .gql files at file_path."""
```

**`.infrahub.yml` representation**:

```yaml
graphql_fragments:
  - name: interface_fragments
    file_path: fragments/interfaces.gql
  - name: device_fragments
    file_path: fragments/devices.gql
```

---

## Backend Integration Contract

**File**: `backend/infrahub/git/integrator.py` (modification to `import_all_graphql_query()`)

The backend calls the SDK renderer. It does not duplicate any fragment logic.

```python
from infrahub_sdk.graphql.fragment_renderer import render_query_with_fragments
from infrahub_sdk.exceptions import (
    FragmentFileNotFoundError,
    FragmentNotFoundError,
    DuplicateFragmentError,
    CircularFragmentError,
)

# Step 1: Load all fragment file contents (fails fast on missing file — FR-008)
all_fragment_contents: list[str] = []
for fragment_config in config_file.graphql_fragments:
    all_fragment_contents.extend(
        fragment_config.load_fragments(relative_path=commit_wt.directory)
    )

# Step 2: Render each query; per-query errors are logged and skipped (FR-009)
local_queries: dict[str, str] = {}
for query_config in config_file.queries:
    raw = query_config.load_query(relative_path=commit_wt.directory)
    try:
        local_queries[query_config.name] = render_query_with_fragments(
            query_str=raw,
            fragment_files=all_fragment_contents,
        )
    except (FragmentNotFoundError, DuplicateFragmentError, CircularFragmentError) as exc:
        log.error("Query '%s': %s", query_config.name, exc)
        # Skip — other queries continue (FR-009)
```

---

## infrahubctl Integration Contract

**File**: `python_sdk/infrahub_sdk/ctl/utils.py` (modification to `execute_graphql_query()`)

```python
all_fragment_contents: list[str] = []
for frag in repository_config.graphql_fragments:
    all_fragment_contents.extend(frag.load_fragments())
query_str = render_query_with_fragments(
    query_str=query_object.load_query(),
    fragment_files=all_fragment_contents,
)
```

**File**: `python_sdk/infrahub_sdk/ctl/cli_commands.py` (modification to `transform()` at line ~345)

Same pattern as above.
