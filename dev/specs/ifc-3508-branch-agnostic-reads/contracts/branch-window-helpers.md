# Contract: Branch Window Helpers

Module: `backend/infrahub/core/query/branch_windows.py`. It is a leaf module: it imports only `infrahub.core.constants`, plus `Timestamp` for type hints. Every query that needs an answer across branches imports from it. No other module builds the list of live branch windows.

## Collecting the windows

```python
def build_branch_windows_query(
    *,
    at: Timestamp,
    enabled: bool,
    carry: Sequence[str] = (),
    variable_name: str = "branch_windows",
    time_param: str = "windows_at",
) -> tuple[str, dict[str, Any]]: ...
```

- When `enabled` is false, it returns `WITH NULL AS <variable_name>` (plus the `carry` variables) and no parameters. A read on one branch therefore keeps its query plan.
- When `enabled` is true, it returns a `MATCH (branch:Branch) … WITH <carry>, collect({name, origin_name, origin_at}) AS <variable_name>` clause and the parameters `<time_param>` and `global_branch_name`.
- The clause aggregates every row before it, so it must open the query, or be preceded only by the variables listed in `carry`.
- Windows exclude `-global-` and branches whose status is `DELETING`. The default branch has a NULL origin. For other branches, `origin_at = min(branched_from, $<time_param>)`.

## Testing one edge against one window

```python
def render_window_filter(*, edge: str, window: str = "window", time_param: str = "windows_at") -> str: ...
```

The rendered predicate is true when the edge is visible in the window, as defined in data-model.md. For a single window, it accepts the same edges as `Branch.get_query_filter_path(is_isolated=True)` for that branch.

## Ranking two edges

```python
def render_outranks(*, edge: str, competitor: str = "r") -> str: ...
```

The rendered predicate is true when `competitor` has a higher `branch_level` than `edge`, or the same level and a later `from`. It is meant for `NOT EXISTS { MATCH … competitor … WHERE <render_window_filter(competitor)> AND <render_outranks(edge)> }`.

## Choosing one window per node (PR 6)

```python
def render_window_choice(*, window_list: str, request_branch_param: str, default_branch_param: str) -> str: ...
```

The rendered Cypher expression sorts a list of windows so that the request branch comes first, then the default branch, then the others by name. The caller takes the first window of the sorted list in which the node exists.

## Callers after PR 3

- `core/query/subquery.py`: the window form of `build_subquery_filter`, which PRs 5 and 6 bring in.
- `core/query/ipam.py`: the four `…FetchFree` queries.
- `core/query/resource_manager.py`: the number pool fragments. They keep their "hiding edge" rule (research R1).
- `core/query/agnostic_retention.py` and `core/query/branch_agnostic_retirement.py`: the retirement check.
- Later: `core/query/relationship.py` (PR 4 and PR 6) and `core/query/node.py` (PR 6).

## Unit tests

`backend/tests/unit/core/query/test_branch_windows.py` covers:

- the disabled form;
- the parameters;
- that the carried variables appear in the `WITH`;
- that the rendered predicates name the variables passed in.

Behavior against a database is tested through the callers' component tests.
