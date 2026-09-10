# Contract: core primitive (Python)

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03

The primitive is callable without GraphQL (FR-009). Two callers: the GraphQL resolver (increment B) and
`get_repositories_commit_per_branch` (increment C).

## Query class

`infrahub.core.query.repository::RepositoryBranchAttributesQuery`

```python
class RepositoryBranchAttributesQuery(Query):
    name = "repository-branch-attributes"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        repository_ids: list[str],
        branch_names: list[str],
        attribute_names: list[str],
        default_branch_name: str,
        global_branch_name: str,
        **kwargs: Any,
    ) -> None: ...

    def get_data(self) -> Generator[RepositoryBranchAttributeValue, None, None]: ...
```

- Constructor takes primitives only. `at` and `db` arrive through the base `Query.init` path; the
  query binds `$at` from `self.at`.
- One statement: `UNWIND $branch_names AS branch_name MATCH (br:Branch {name: branch_name})`, then
  `MATCH (n:Node)-[:HAS_ATTRIBUTE]->(a:Attribute) WHERE n.uuid IN $repository_ids AND a.name IN
  $attribute_names`, `WITH DISTINCT` on `(n, a, branch_name, br.branched_from)`, one `CALL` subquery
  electing the visible `HAS_ATTRIBUTE` edge and one electing the visible `HAS_VALUE` edge, both with
  the per-branch predicate in [data-model.md](../data-model.md) and the standard election order.
- Returns only `n.uuid`, `branch_name`, `a.name`, `a.uuid`, `av.value`, `r_value.branch`,
  `r_value.from`.
- No `LIMIT`: the statement is bounded by `len(branch_names) * len(attribute_names) *
  len(repository_ids)` rows by construction. Callers chunk `branch_names`.

Result dataclass (frozen): `RepositoryBranchAttributeValue(repository_id, branch_name,
attribute_name, attribute_id, value, own_value, updated_at)`.

## Reader component

`infrahub.core.repository_branch_status.reader::RepositoryBranchAttributesReader`

```python
class RepositoryBranchAttributesReader:
    def __init__(self, db: InfrahubDatabase, default_branch_name: str, global_branch_name: str) -> None: ...

    async def read(
        self,
        repository_ids: Sequence[str],
        branch_names: Sequence[str],
        attribute_names: Collection[str],
        at: Timestamp | None = None,
    ) -> RepositoryBranchAttributes: ...
```

- Built at the entry point (resolver, sync flow) with `registry.default_branch` and
  `GLOBAL_BRANCH_NAME`; the component itself never touches `registry`.
- Empty `branch_names` or empty `attribute_names` returns an empty lookup without executing.
- Runs exactly one `RepositoryBranchAttributesQuery` per call. Chunking is the caller's decision.
- `branch_names` is the caller's, and the two callers source it differently on purpose. The resolver
  reads it from the database, because its row set must match the branches page the user sees and a
  branch created seconds ago may not have reached every worker's registry yet. The periodic sync
  reads it from `registry.branch`, which is what it reads today and what its once-a-minute cadence
  tolerates. Neither is a default for a third caller to copy without deciding.

Result: `infrahub.core.repository_branch_status.models::RepositoryBranchAttributes`

```python
@dataclass(frozen=True)
class RepositoryBranchAttributes:
    def get(self, repository_id: str, branch_name: str, attribute_name: str) -> RepositoryBranchAttributeValue | None: ...
    def for_branch(self, repository_id: str, branch_name: str) -> dict[str, RepositoryBranchAttributeValue]: ...
```

`get` returns `None` for a triple that produced no row. That is the Python-side backfill; callers treat
`None` as "no visible value" (the repository never had that attribute created on any visible branch),
which cannot happen for the attributes in scope after repository creation.

## Direct-call example (FR-009 verification)

```python
reader = RepositoryBranchAttributesReader(
    db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME
)
result = await reader.read(
    repository_ids=[repository.id],
    branch_names=["main", "branch2"],
    attribute_names={"commit"},
)
assert result.get(repository.id, "branch2", "commit").value == "commit21"
assert result.get(repository.id, "main", "commit").own_value is False   # creation value lives on the global branch
```

## Periodic sync usage (increment C)

```python
for chunk in batched(branch_names, REPOSITORY_BRANCH_READ_CHUNK_SIZE):
    values = await reader.read(
        repository_ids=repository_ids, branch_names=chunk, attribute_names=("commit", "internal_status")
    )
```

Query count for N branches: `1` (repository nodes) `+ ceil(N / 100)`. Asserted with
`tests.helpers.db_query_counter::CountingInfrahubDatabase.count_for(RepositoryBranchAttributesQuery.name)`.
