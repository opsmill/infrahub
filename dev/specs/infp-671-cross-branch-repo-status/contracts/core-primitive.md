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
- One statement: `MATCH (n:Node) WHERE n.uuid IN $repository_ids`, then `MATCH
  (n)-[:HAS_ATTRIBUTE]->(a:Attribute) WHERE a.name IN $attribute_names` as a separate match so the
  node seek is pinned rather than left to the planner's choice between the `node_uuid` and
  `attr_name` indexes, `WITH DISTINCT n, a`, then `UNWIND $branch_names AS branch_name MATCH
  (br:Branch {name: branch_name})` carrying `n, a, branch_name` and the default-branch window, one
  `CALL` subquery electing the visible `HAS_ATTRIBUTE` edge and one electing the visible `HAS_VALUE`
  edge, both with the per-branch predicate in [data-model.md](../data-model.md) and the standard
  election order. The node match and its deduplication sit **above** the `UNWIND`: below it they
  share no variable with `branch_name`, so the planner drives them as the right side of a cartesian
  `Apply` and repeats the uuid seek and the attribute expansion once per branch.
- Returns only `n.uuid`, `branch_name`, `a.name`, `a.uuid`, `av.value`, `r_value.branch`,
  `r_value.from`.
- No `LIMIT`: the statement is bounded by `len(branch_names) * len(attribute_names) *
  len(repository_ids)` rows by construction. Callers chunk `branch_names`. The read is therefore
  unpageable and rejects a `limit` or `offset` argument rather than silently discarding it; it sets
  `self.limit` to that bound floored at 1, so a READ with neither set is not treated as unpaginated.
  The floor is only reachable by a direct caller passing an empty repository, branch or attribute
  list, each of which the reader answers without executing the statement.

Result dataclass (frozen): `RepositoryBranchAttributeValue(repository_id, branch_name,
attribute_name, attribute_id, value, own_value, updated_at)`.

## Reader component

`infrahub.core.repository_branch_status.reader::RepositoryBranchAttributesReader`

```python
class RepositoryBranchAttributesReader(RepositoryBranchAttributesSource):
    def __init__(self, db: InfrahubDatabase, default_branch_name: str, global_branch_name: str) -> None: ...

    async def read(
        self,
        repository_ids: Sequence[str],
        branch_names: Sequence[str],
        attribute_names: Collection[str],
        at: Timestamp | None = None,
    ) -> RepositoryBranchAttributes: ...
```

- Built by `infrahub.core.repository_branch_status.factory::build_repository_branch_attributes_source(db)`
  with `registry.default_branch` and `GLOBAL_BRANCH_NAME`. Both callers use that factory: the
  GraphQL field hands it to the resolver as its source factory, and the sync calls it once at the
  top of the function. The component itself never touches `registry`.
- An empty `repository_ids`, `branch_names` or `attribute_names` returns an empty lookup without
  executing: each makes the statement unable to match a row.
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
`None` as "no visible value" (the repository never had that attribute created on any visible branch).
For a `LOCAL` attribute this cannot happen after repository creation, because its creation edge is on
the global branch. For an `AWARE` one (`CoreReadOnlyRepository.commit` and `ref`) it does: on every
branch but the one the repository was created from, and on branches forked before the creation
(data-model.md).

The lookup is built with `RepositoryBranchAttributes.from_values(values)`. Two values for the same
triple raise `ResourceMultipleFoundError`, which the reader lets propagate: it means the graph holds
two attributes of one name on that branch, and picking one would hide the fault.

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
        repository_ids=repository_ids,
        branch_names=chunk,
        attribute_names=("commit", "internal_status"),
        at=at,
    )
```

`at` is one `Timestamp` taken before the repository-node read and passed to it and to every chunk,
so the whole read resolves at one point in time.

Query count for N branches: `ceil(N / 100)` attribute reads, on top of one `NodeManager.query` for
the repository nodes. That call is several statements (`node_get_list`, then the info and attribute
reads behind `get_many`), fixed in number whatever N is. With no repository the function returns
after the node read and issues no attribute read. Asserted with
`tests.helpers.db_query_counter::CountingInfrahubDatabase.count_for(RepositoryBranchAttributesQuery.name)`
and `count_for("node_get_list") == 1`.
