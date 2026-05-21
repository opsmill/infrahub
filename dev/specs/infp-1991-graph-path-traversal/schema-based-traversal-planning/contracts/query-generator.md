# Internal Contract: `render_plan_to_cypher`

**Module**: `backend/infrahub/graph_traversal/_cypher.py` — private helper consumed by `PathTraversalQuery` and `ReachableNodesQuery` only.
**Plan**: [../plan-schema-planning.md](../plan-schema-planning.md)
**Data model**: [../data-model-schema-planning.md](../data-model-schema-planning.md)

Pure function. No I/O. No async. Converts a `Plan` into the Cypher query text and final parameter dict ready for `Query.execute()`. Lives outside the `planning/` sub-package because Cypher emission is the responsibility of the Query class layer, not the planner (see [planner.md §Caller Contract](planner.md#caller-contract)).

## Surface

```text
def render_plan_to_cypher(
    *,
    plan: Plan,
    source_id: str,
    branch: Branch,
    at: Timestamp,
    max_results: int,
) -> RenderedCypher: ...

@dataclass(frozen=True, slots=True)
class RenderedCypher:
    text: str
    params: dict[str, Any]
    return_labels: tuple[str, ...]
```

Importable only from other modules in `graph_traversal/`. The `_` prefix on the module name signals "internal to `graph_traversal/`"; nothing in `planning/` may import it.

## Inputs

| Parameter | Purpose | Validation |
|---|---|---|
| `plan` | The planner's output. | If `plan.is_empty`, raise `ValueError("plan has no adjacency")`. |
| `source_id` | UUID of the starting object. | Must be a string; embedded only as a parameter, never interpolated. |
| `branch` | Provides `branch.is_default` (dispatch flag) and `branch.name` (user-branch deletion filter). | Reused as-is. |
| `at` | Point-in-time. Serialized via `at.to_string()` and bound as `$at`. | Same. |
| `max_results` | Cap returned rows. | `1 ≤ max_results ≤ 200`. Raise `ValueError` otherwise. Per-mode caps (`max_paths` for `TerminalById` ≤ 100, `max_results` for `TerminalByKinds` ≤ 200) are enforced by the Query class before calling the renderer. |

## Output

A `RenderedCypher` with:

- `text` — a single Cypher statement (one MATCH chain plus a QPP MATCH).
- `params` — bound values for the source/target UUIDs, branch+time filter inputs, the planner-derived `allowed_path_maps` / `all_rel_names`, and `max_results`. **Kind names appear as Neo4j labels in `text`** (not bound parameters) so the label index drives the match.
- `return_labels` — always `("path_data", "depth")`.

## Generated Cypher shape

A schema-level hop materializes as **two** `IS_RELATED` edges meeting at an intermediate `:Relationship` vertex whose `name` property holds the relationship identifier. The schema's `RelationshipDirection` (`OUTBOUND` / `INBOUND` / `BIDIR`) controls how the two arrows are oriented in storage:

| Schema direction | Storage orientation (start → end) |
|---|---|
| `OUTBOUND` | `(:start_kind)-[:IS_RELATED]->(:Relationship {name})-[:IS_RELATED]->(:end_kind)` |
| `INBOUND`  | `(:start_kind)<-[:IS_RELATED]-(:Relationship {name})<-[:IS_RELATED]-(:end_kind)` |
| `BIDIR`    | `(:start_kind)-[:IS_RELATED]->(:Relationship {name})<-[:IS_RELATED]-(:end_kind)` |

The planner does **not** track direction on its output (the per-hop adjacency map is direction-free), and the renderer emits **undirected** `-[:IS_RELATED]-` arrows in the QPP so a single pattern matches all three storage orientations. The table above documents how data is laid out on disk, not how the QPP pattern reads it.

Concrete and generic kind names appear as **Neo4j labels** on `:Node` vertices (concrete kinds also appear as `{kind: $kind}` property predicates).

### Unified single-QPP design

A single quantified-path-pattern MATCH covers both default-branch and user-branch requests. The planner-derived `$allowed_path_maps` (a nested `{start_kind: {rel_name: [end_kind, ...]}}` map) enforces the structural `(start_kind, rel_name, end_kind)` constraint per QPP iteration.

The QPP body uses **undirected** `-[:IS_RELATED]-` arrows because storage orientation depends on the schema relationship's `RelationshipDirection` — a single quantified pattern can't encode all three (`OUTBOUND`/`INBOUND`/`BIDIR`) with directed arrows. `$allowed_path_maps` does the structural work that directed arrows would otherwise have done.

```cypher
MATCH (source:Node {uuid: $source_id})-[source_active:IS_PART_OF]->(:Root)
WHERE source_active.branch IN $valid_branches AND source_active.status = "active"
  AND source_active.from <= $at AND (source_active.to IS NULL OR source_active.to >= $at)
WITH source ORDER BY source_active.from DESC LIMIT 1

MATCH (target:Node {uuid: $target_id})-[target_active:IS_PART_OF]->(:Root)
WHERE target_active.branch IN $valid_branches AND target_active.status = "active"
  AND target_active.from <= $at AND (target_active.to IS NULL OR target_active.to >= $at)
WITH source, target ORDER BY target_active.from DESC LIMIT 1

MATCH path = (source) (
  (a:<start-labels>)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(b:<end-labels>)
  WHERE rel.name IN $all_rel_names
    AND r1.branch IN $valid_branches AND r1.status = "active"
    AND r1.from <= $at AND (r1.to IS NULL OR r1.to >= $at)
    AND r2.branch IN $valid_branches AND r2.status = "active"
    AND r2.from <= $at AND (r2.to IS NULL OR r2.to >= $at)
    <user-branch deletion filter — see below>
    AND rel.name IN keys($allowed_path_maps[a.kind])
    AND b.kind IN $allowed_path_maps[a.kind][rel.name]
){1, <plan.max_depth as literal int>} <target_pattern>
WITH path, length(path) / 2 AS depth
ORDER BY depth ASC, path
LIMIT $max_results
RETURN [n IN nodes(path) | {uuid: n.uuid, kind: n.kind, name: n.name}] AS path_data, depth
```

`<target_pattern>` is `(target)` for `TerminalById` (the variable is pre-bound by the by-uuid match) and `(target:$any($terminal_kinds))` for `TerminalByKinds` (Cypher 5 dynamic-label syntax on the path's final node). The query projects `path_data` — a list of `{uuid, kind, name}` dicts, one per `nodes(path)` entry — rather than the full Neo4j `Path` object, so only the three properties the Query class reads cross the driver.

The branch differences reduce to two pieces:

- **`$valid_branches`** binds to `[default_branch, global_branch]` on the default branch and `[default_branch, global_branch, user_branch]` on a user branch.
- **User-branch deletion filter** is inserted into the QPP body only when `branch.is_default` is `False`:
  ```cypher
  AND NOT EXISTS {
    (a)-[del:IS_RELATED {status: "deleted", branch: $user_branch}]-(rel)
    WHERE del.from > r1.from
      AND del.from <= $at
      AND (del.to IS NULL OR del.to >= $at)
  }
  AND NOT EXISTS {
    (rel)-[del:IS_RELATED {status: "deleted", branch: $user_branch}]-(b)
    WHERE del.from > r2.from
      AND del.from <= $at
      AND (del.to IS NULL OR del.to >= $at)
  }
  ```
  The `del.from > rN.from` asymmetry treats a deletion as superseding the active edge only if the deletion happened *after* the active edge began. The default branch has no version race between (default, global) and (user) branches, so this check is unnecessary there.

### Endpoint matches — migration-safe by-uuid lookup

A single UUID can map to more than one `:Node` vertex when a kind migration leaves the old vertex in place alongside the new one. The endpoint matches resolve this by selecting the currently-live vertex via its active `IS_PART_OF` edge to `Root`, then picking the most recently activated row across all candidates:

```cypher
MATCH (source:Node {uuid: $source_id})-[source_active:IS_PART_OF]->(:Root)
WHERE source_active.branch IN $valid_branches AND source_active.status = "active"
  AND source_active.from <= $at AND (source_active.to IS NULL OR source_active.to >= $at)
WITH source ORDER BY source_active.from DESC LIMIT 1
```

The target match for `TerminalById` follows the same shape, carrying `source` forward in its `WITH`.

### Target match for `TerminalByKinds`

When the terminal predicate is a kind set rather than a specific UUID, there is no upfront target `MATCH`. The label constraint is inlined into the outer path-MATCH's final node with Cypher 5's dynamic-label syntax:

```cypher
MATCH path = (source) ( ... ){1, <max>} (target:$any($terminal_kinds))
```

Putting the constraint on the path's final node (instead of pre-binding every candidate via `MATCH (target:$any($terminal_kinds))` upstream) lets Neo4j drive target selection from the path search rather than first materializing a potentially huge candidate set. A label-union `(target:KindX|KindY|...)` is *not* used because the union of terminal kinds may overlap with intermediate kinds; `$any($terminal_kinds)` binds only on the path's final node so it doesn't conflict with intermediates that share a label.

## Parameters

| Param | Type | Always? | Source |
|---|---|---|---|
| `$source_id` | str | yes | renderer arg |
| `$target_id` | str | `TerminalById` only | `plan.terminal_predicate.node_id` |
| `$terminal_kinds` | sorted list[str] | `TerminalByKinds` only | `plan.terminal_predicate.kinds` |
| `$at` | str | yes | `at.to_string()` |
| `$valid_branches` | list[str] | yes | `[default, global]` (default branch) or `[default, global, user]` (user branch) |
| `$user_branch` | str | user branch only | `branch.name` |
| `$all_rel_names` | sorted list[str] | yes | sorted union of every `rel_name` key in `plan.adjacency` |
| `$allowed_path_maps` | dict[str, dict[str, list[str]]] | yes | `plan.adjacency` with inner `frozenset` end-kind sets converted to sorted lists |
| `$max_results` | int | yes | renderer arg |

The QPP quantifier bound `plan.max_depth` is **interpolated as a literal integer**, not parameter-bound, because Cypher's QPP `{m, n}` syntax rejects parameters in that position. The value is server-validated to `[1, 20]` and never user-supplied raw, so direct interpolation is safe.

## Behavior — required

1. **Validate inputs**: raise `ValueError` when `plan.is_empty` is `True` or `max_results` is out of `[1, 200]`.
2. **Derive `$allowed_path_maps`** from `plan.adjacency`: convert every inner `frozenset[str]` end-kind set to a sorted `list[str]`. No accumulation pass is needed — the planner already emits the adjacency in the required shape.
3. **Derive label unions**: `start_kinds = sorted(keys(allowed_path_maps))`; `end_kinds = sorted(union of every end_kind in the map)`.
4. **Derive `$all_rel_names`**: sorted union of every `rel_name` key in `plan.adjacency`.
5. **Dispatch on `branch.is_default`** only for two things:
   - `$valid_branches`: 2-element on default branch, 3-element on user branch.
   - Inject the user-branch deletion filter into the QPP body when `branch.is_default` is `False`.
6. **Pick the target binding**:
   - `TerminalById`: bind `$target_id`, use the upfront by-uuid `MATCH (target:Node {uuid: $target_id})...LIMIT 1` template; the outer path-MATCH's final node is `(target)` (variable already bound).
   - `TerminalByKinds`: bind `$terminal_kinds` (sorted), emit no upfront target match; the outer path-MATCH's final node is `(target:$any($terminal_kinds))`.
7. **Interpolate the source match, target match, QPP body, target pattern, and `plan.max_depth`** into the outer `_QUERY` template.
8. **Return** `RenderedCypher(text=text, params=params, return_labels=("path_data", "depth"))`.

## Behavior — forbidden

- Must not call the planner, the database, the schema, or the permission system. Pure function over `Plan` + a few primitives.
- Must not interpolate **user-supplied** strings into Cypher. Kind names (interpolated as labels) and relationship identifiers (bound as parameters) come from the planner, which sources them from the schema. User-supplied filter strings (`kind_filter`, `excluded_kinds`, etc.) influence which `Plan` routes exist but never appear in the generated Cypher.
- Must not exceed the existing `Query` base contract — `text`, `params`, `return_labels` are all the caller needs.

## Caller integration

The Query class holds a guaranteed non-empty `Plan` on `self.plan`; the GraphQL resolver enforces the empty-plan short-circuit upstream (see [planner.md §Caller Contract](planner.md#caller-contract)). The Query's `__init__` raises `ValueError` as a backstop if a caller passes an empty plan.

```python
# backend/infrahub/graph_traversal/path.py
from infrahub.graph_traversal._cypher import render_plan_to_cypher

class PathTraversalQuery(Query):
    async def query_init(self, db, **kwargs):
        rendered = render_plan_to_cypher(
            plan=self.plan,
            source_id=self.source_id,
            branch=self.branch,
            at=self.at,
            max_results=self.max_paths,
        )
        self.query_lines = [rendered.text]
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)
```

`PathTraversalQuery._extract_path_data` (private static method on the Query class) consumes the returned `path_data` list and produces `PathData` from `infrahub.graph_traversal.results`. The renderer's return labels are `("path_data", "depth")`.

## Tests

Snapshot tests on the full Cypher text are explicitly **out of scope** — they are brittle, drift with every formatting change, and don't actually verify correctness. End-to-end correctness lives in `backend/tests/component/graph_traversal/test_path_traversal_query.py`: those tests run the rendered Cypher against a real Neo4j and verify the returned paths. The renderer's defensive validation (empty plan, out-of-range `max_results`) is exercised transitively through the Query-class tests; there is no standalone `test_cypher.py`.

## Alternative: per-route UNION ALL for default branch

The current implementation uses the unified QPP shape for both branches. An alternative shape — one `UNION ALL` branch per route, each in its own `CALL { ... }` subquery, with direction-specific arrows per hop — is preserved here as a documented fallback in case benchmark evidence (SC-002) shows the QPP form regresses on the default branch.

> The Cypher snippet below predates the structured `path_data` projection. If adopted, the alternative shape would also project `[n IN nodes(path) | {uuid, kind, name}] AS path_data` instead of returning the full `Path` object, and the planner would no longer need direction information on each hop since the unified shape carries the same `(start_kind, rel_name, end_kind)` adjacency for both. The fan-out shape is preserved for reference only.

The fan-out shape would look like:

```cypher
CALL {
  // ── Route 0 ──────────────────────────────────────────────────
  MATCH (source:Node {uuid: $source_id})
  MATCH (source)-[r0a:IS_RELATED]->(rel_h0:Relationship {name: $rel_route0_hop0})-[r0b:IS_RELATED]->(n_h0:Kind1)
  WHERE r0a.branch IN [$default_branch, $global_branch] AND r0a.status = "active"
    AND r0a.from <= $at AND (r0a.to IS NULL OR r0a.to >= $at)
    AND r0b.branch IN [$default_branch, $global_branch] AND r0b.status = "active"
    AND r0b.from <= $at AND (r0b.to IS NULL OR r0b.to >= $at)
  -- ... hop 1, hop 2 ... with direction-appropriate arrows per Hop.direction
  WITH source, rel_h0, n_h0, rel_h1, target
  MATCH path = (source)-[:IS_RELATED]->(rel_h0)-[:IS_RELATED]->(n_h0)
              -[:IS_RELATED]->(rel_h1)<-[:IS_RELATED]-(target)
  WHERE target.uuid = $destination_id
  RETURN path, length(path) AS depth

  UNION ALL

  // ── Route 1 ──────────────────────────────────────────────────
  ...
}
WITH path, depth
ORDER BY depth ASC, path
LIMIT $max_results
RETURN path, depth
```

Each route is its own UNION ALL branch within an outer `CALL`. Variable names (`rel_h{H}`, `n_h{H}`, `target`, `r{H}a`/`r{H}b`) reuse across branches because UNION ALL branches are independent scopes. Each hop's `MATCH` uses the direction-specific arrow pattern from the table above, with the four-predicate inline `WHERE` on each edge. The default branch has no version race, so no per-edge `CALL`-with-`LIMIT 1` subquery is needed.

### When to switch

The alternative gives Neo4j's planner per-route specialization. Whether that beats the unified QPP depends on (a) the number of routes the planner emits, (b) the cardinality of the start-kind and end-kind label sets, and (c) how well the QPP planner uses the label index. Decide based on `EXPLAIN` output and benchmark numbers from SC-002. If `EXPLAIN` on the unified QPP shows an `AllNodesScan`, or if p95 latency on 100k-node graphs is materially worse than the per-route shape, switch the default branch to this alternative.

### Implementation impact

Reintroducing this strategy is a localized change inside `_cypher.py`:

1. Reintroduce a `_render_default_branch_union_all` function producing the fan-out shape.
2. Make `render_plan_to_cypher` dispatch on `branch.is_default`:
   ```python
   if branch.is_default:
       return _render_default_branch_union_all(plan=plan, source_id=source_id, at=at, max_results=max_results)
   return _render_user_branch_qpp(plan=plan, source_id=source_id, branch=branch, at=at, max_results=max_results)
   ```
3. The user-branch QPP renderer drops the `branch.is_default` conditionals (it's user-branch only).
4. Component tests don't change — the public contract (`Plan` in → paths out) is identical.

### Parameter set deltas

The UNION ALL shape introduces per-route, per-hop relationship-identifier params (`$rel_route{R}_hop{H}`) and drops `$allowed_path_maps` / `$all_rel_names` for the default branch. `$destination_id` replaces `$target_id` for `TerminalById` (each route's terminal vertex is aliased `target_r{R}`). All other params are the same.
