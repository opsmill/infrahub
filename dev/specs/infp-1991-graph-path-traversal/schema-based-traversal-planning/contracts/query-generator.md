# Internal Contract: `render_plan_to_cypher`

**Module**: `backend/infrahub/graph_traversal/_cypher.py` — private helper shared by `PathTraversalQuery` and `ReachableNodesQuery` only.
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
) -> RenderedCypher:
    """Dispatch on branch.is_default to the strategy below."""

# Private — selected by render_plan_to_cypher based on branch.is_default:
def _render_default_branch(*, plan, source_id, branch, max_results) -> RenderedCypher: ...
def _render_user_branch(*, plan, source_id, branch, max_results) -> RenderedCypher: ...

@dataclass(frozen=True, slots=True)
class RenderedCypher:
    text: str
    params: dict[str, Any]
    return_labels: tuple[str, ...]
```

`render_plan_to_cypher` chooses one of two strategies and returns the same `RenderedCypher` shape from either:

| Strategy | When | Why |
|---|---|---|
| `_render_default_branch` | `branch.is_default` is `True` | On the default branch there is at most one authoritative edge between any pair of vertices: at the requested time `$at` it is current iff `e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)`. No `ORDER BY r.branch_level DESC, r.from DESC LIMIT 1` subquery is needed. An inline four-predicate `WHERE` on each `IS_RELATED` edge replaces the per-edge `CALL` block; queries are smaller and Neo4j's planner can fold the conjunction into a simple edge-property filter. |
| `_render_user_branch` | `branch.is_default` is `False` | On a user branch, the authoritative edge per pair is "latest on (default, global, user) with user winning on ties." The default-branch shortcut does not apply. We use a **single quantified-path-pattern (QPP) MATCH** parameterized by `$allowed_path_maps` (a nested map encoding the planner's `plan.routes` as `start_kind → rel_name → set[end_kind]`) instead of one `UNION ALL` branch per route. This collapses N route MATCHes into one declarative walk and lets Neo4j's planner pick the search strategy. Deletion on the user branch is checked with `NOT EXISTS { ... :IS_RELATED {status: "deleted", branch: $user_branch} ... }`. |

Importable only from other modules in `graph_traversal/`. The `_` prefix on the module name signals "internal to `graph_traversal/`"; nothing in `planning/` may import it.

## Inputs

| Parameter | Purpose | Validation |
|---|---|---|
| `plan` | The planner's output. | If `plan.routes` is empty, raise `ValueError("plan has no routes; caller must short-circuit")`. |
| `source_id` | UUID of the starting object. | Must be a string; embedded only as a parameter, never interpolated. |
| `branch` | For obtaining branch+time filter clause via `branch.get_query_filter_path(at=...)`. | Reused as-is. |
| `at` | Point-in-time. | Same. |
| `max_results` | Cap returned rows. For `TerminalById` mode the caller passes `max_paths` (≤ 100); for `TerminalByKinds` mode the caller passes `max_results` (≤ 200). The renderer accepts the union range `1 ≤ value ≤ 200`; per-mode caps are enforced by the Query class (`PathTraversalQuery` / `ReachableNodesQuery`) before this function is called. | `1 ≤ max_results ≤ 200`. |

## Output

A `CypherQuery` with:

- `text` — a single Cypher statement with `UNION ALL` branches.
- `params` — bound values for relationship identifiers, node UUIDs, branch+time filter inputs, and limits. **Kind names are interpolated as Neo4j labels in `text`** (not bound parameters) so the label index drives the match — see "Notes on the shape" below for the Constitution VI rationale.
- `return_labels` — the column order matching `extract_path_data(neo4j.Path)`'s expectations.

## Generated Cypher shape

Both strategies model the same underlying graph: every schema-level hop materializes as **two** `IS_RELATED` edges meeting at an intermediate `:Relationship` vertex whose `name` property holds the relationship identifier. The two arrows' orientations encode the schema's `RelationshipDirection`:

| `Hop.direction` | Cypher pattern from `:start_kind` to `:end_kind` |
|---|---|
| `OUTBOUND` | `(:start_kind)-[:IS_RELATED]->(:Relationship {name: $rel})-[:IS_RELATED]->(:end_kind)` |
| `INBOUND`  | `(:start_kind)<-[:IS_RELATED]-(:Relationship {name: $rel})<-[:IS_RELATED]-(:end_kind)` |
| `BIDIR`    | `(:start_kind)-[:IS_RELATED]->(:Relationship {name: $rel})<-[:IS_RELATED]-(:end_kind)` |

Kind names appear as **Neo4j labels** on `:Node` vertices (not as `{kind: $kind}` property predicates). Nodes in the Infrahub graph carry their kind as an additional label alongside `:Node` — verified at [`backend/infrahub/core/query/path.py:153`](../../../../backend/infrahub/core/query/path.py).

Where the two strategies differ is **how edge validity is enforced**, which dominates query cost.

---

### Strategy A — `_render_default_branch` (when `branch.is_default`)

One `UNION ALL` branch per route, each route in its own `CALL { ... }` subquery, with edge validity inlined as four property predicates (`e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)`). No per-edge `CALL`-with-`LIMIT 1` subqueries are needed — on the default branch there is at most one authoritative edge between two vertices, so the latest-version-resolution dance is unnecessary. The `from`/`to` predicates are required (not just convenient) so the query honors the request's `$at`.

For a plan with two routes — route 0: `Source —OUT→ Kind1 —BIDIR— Kind2 —IN→ Terminal`; route 1: `Source —OUT→ AlternateTerminal`:

```cypher
CALL {
  // ── Route 0 ──────────────────────────────────────────────────
  MATCH (source:Node {uuid: $source_id})
  MATCH (source)-[r0a:IS_RELATED]->(rel_r0_h0:Relationship {name: $rel_route0_hop0})-[r0b:IS_RELATED]->(n_r0_h0:Kind1)
  WHERE r0a.branch IN [$default_branch, $global_branch] AND r0a.status = "active"
    AND r0a.from <= $at AND (r0a.to IS NULL OR r0a.to >= $at)
    AND r0b.branch IN [$default_branch, $global_branch] AND r0b.status = "active"
    AND r0b.from <= $at AND (r0b.to IS NULL OR r0b.to >= $at)
  MATCH (n_r0_h0)-[r1a:IS_RELATED]->(rel_r0_h1:Relationship {name: $rel_route0_hop1})<-[r1b:IS_RELATED]-(n_r0_h1:Kind2)
  WHERE r1a.branch IN [$default_branch, $global_branch] AND r1a.status = "active"
    AND r1a.from <= $at AND (r1a.to IS NULL OR r1a.to >= $at)
    AND r1b.branch IN [$default_branch, $global_branch] AND r1b.status = "active"
    AND r1b.from <= $at AND (r1b.to IS NULL OR r1b.to >= $at)
  MATCH (n_r0_h1)<-[r2a:IS_RELATED]-(rel_r0_h2:Relationship {name: $rel_route0_hop2})<-[r2b:IS_RELATED]-(target_r0:Terminal)
  WHERE r2a.branch IN [$default_branch, $global_branch] AND r2a.status = "active"
    AND r2a.from <= $at AND (r2a.to IS NULL OR r2a.to >= $at)
    AND r2b.branch IN [$default_branch, $global_branch] AND r2b.status = "active"
    AND r2b.from <= $at AND (r2b.to IS NULL OR r2b.to >= $at)
  WITH source, rel_r0_h0, n_r0_h0, rel_r0_h1, n_r0_h1, rel_r0_h2, target_r0
  MATCH path = (source)-[:IS_RELATED]->(rel_r0_h0)-[:IS_RELATED]->(n_r0_h0)
              -[:IS_RELATED]->(rel_r0_h1)<-[:IS_RELATED]-(n_r0_h1)
              <-[:IS_RELATED]-(rel_r0_h2)<-[:IS_RELATED]-(target_r0)
  WHERE <terminal predicate for target_r0>
  RETURN path, length(path) AS depth

  UNION ALL

  // ── Route 1 ──────────────────────────────────────────────────
  MATCH (source:Node {uuid: $source_id})
  MATCH (source)-[r0a:IS_RELATED]->(rel_r1_h0:Relationship {name: $rel_route1_hop0})-[r0b:IS_RELATED]->(target_r1:AlternateTerminal)
  WHERE r0a.branch IN [$default_branch, $global_branch] AND r0a.status = "active"
    AND r0a.from <= $at AND (r0a.to IS NULL OR r0a.to >= $at)
    AND r0b.branch IN [$default_branch, $global_branch] AND r0b.status = "active"
    AND r0b.from <= $at AND (r0b.to IS NULL OR r0b.to >= $at)
  MATCH path = (source)-[:IS_RELATED]->(rel_r1_h0)-[:IS_RELATED]->(target_r1)
  WHERE <terminal predicate for target_r1>
  RETURN path, length(path) AS depth
}
WITH path, depth
ORDER BY depth ASC, path
LIMIT $max_results
RETURN path, depth
```

Bound params: `$source_id`, `$at` (the request's point-in-time as a serialized timestamp), `$rel_route{R}_hop{H}` (one per hop), `$default_branch`, `$global_branch`, `$destination_id` (TerminalById only), `$max_results`.

---

### Strategy B — `_render_user_branch` (when `branch.is_default` is `False`)

A single MATCH using a **quantified path pattern (QPP)** parameterized by `$allowed_path_maps`. Routes are collapsed into per-edge constraints; the QPP iterates `{1, $max_path_length}` repetitions of the `(a)→(rel)←(b)` schema-hop. Edge validity is "active on default/global/user branch, not subsequently deleted on the user branch."

`$allowed_path_maps` is the planner's `plan.routes` rewritten as a nested map: `{start_kind: {rel_name: [end_kind, ...]}}`. The renderer derives it deterministically from `plan.routes`: for each `Hop(start_kind, end_kind, relationship_identifier)` appearing in any surviving route, add `end_kind` to `allowed_path_maps[start_kind][relationship_identifier]`. Generic-typed peers were already expanded to their concrete inheritors by the planner (per [planner.md §Behavior — required](planner.md#behavior--required) step 2), so every kind in the map is concrete.

```cypher
MATCH (source:Node {uuid: $source_id})
MATCH (target:Node {uuid: $target_id})  -- omitted for TerminalByKinds; see below

MATCH path = (source) (
  (a:TypeA|TypeB|...)-[r1:IS_RELATED]->(rel:Relationship)<-[r2:IS_RELATED]-(b:TypeC|TypeD|...)
  WHERE rel.name IN $all_rel_names
    AND r1.branch IN $valid_branches AND r1.status = "active"
    AND r1.from <= $at AND (r1.to IS NULL OR r1.to >= $at)
    AND r2.branch IN $valid_branches AND r2.status = "active"
    AND r2.from <= $at AND (r2.to IS NULL OR r2.to >= $at)
    -- A deletion on the user branch supersedes the active edge only if it happened *after*
    -- the active edge began AND is itself current at $at.
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
    -- Plan-derived structural filter: the (a.kind, rel.name, b.kind) triple must be in the plan
    AND rel.name IN keys($allowed_path_maps[a.kind])
    AND b.kind IN $allowed_path_maps[a.kind][rel.name]
){1, $max_path_length} (target)

WITH path, length(path)/2 AS depth  -- 2 IS_RELATED edges per schema hop
ORDER BY depth ASC, path
LIMIT $max_results
RETURN path, depth
```

Bound params:
- `$source_id`, `$target_id` (for `TerminalById`).
- `$at`: the request's point-in-time, serialized to the same timestamp form the existing `from`/`to` edge properties use.
- `$valid_branches`: list `[default_branch, global_branch, user_branch]`.
- `$user_branch`: the user branch name (used inside the deletion-`EXISTS`).
- `$all_rel_names`: the flat set of every `rel_name` that appears anywhere in `$allowed_path_maps`. Used as a fast pre-filter on the relationship vertex.
- `$allowed_path_maps`: the nested `{start_kind: {rel_name: [end_kind, ...]}}` map derived from `plan.routes`.
- `$max_path_length`: equals `plan.max_depth` (each QPP iteration = one schema hop).
- `$max_results`.

The label-union `(a:TypeA|TypeB|...)` pre-filter uses the union of every `start_kind` across `plan.routes`; `(b:TypeC|TypeD|...)` uses the union of every `end_kind`. These let Neo4j use the label index for the first vertex of each iteration. The `$allowed_path_maps[a.kind][rel.name]` predicate then enforces that *this specific* `(start, rel, end)` triple is one the planner approved.

For `TerminalByKinds` mode, replace `MATCH (target:Node {uuid: $target_id})` with `MATCH (target:Node)` and add a `WHERE any(l IN labels(target) WHERE l IN $terminal_kinds)` predicate after the QPP MATCH. The label-union form `(target:KindX|KindY|...)` is *not* used here because the union of terminal kinds may overlap with intermediate kinds; we want the terminal-kind constraint to bind only on the path's final node.

### Notes on the shapes

Default-branch-strategy specifics:

- **Per-route CALL subquery.** Each route lives inside its own `CALL { ... }` block. `UNION ALL` simply concatenates results.
- **Edge validity is a single inline conjunction.** On the default branch there is no version race to resolve: an edge is valid at `$at` iff `e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)`. Neo4j folds the conjunction into edge-property filtering. No per-edge `CALL`-with-`LIMIT 1` subquery is emitted. The `$at` predicate is required (not just convenient) because Infrahub's temporal model supports point-in-time queries; an edge may be active *now* but inactive at `$at` if `$at` predates its `from` or post-dates its `to`.
- **Path reconstruction**: after all per-hop matches succeed, a final `MATCH path = (source)-[…]-(target_rR)` re-binds the validated vertices into a `path` value for the return shape. The variables are all already bound; Neo4j reuses them.

User-branch-strategy specifics:

- **One QPP MATCH for all routes.** The whole plan collapses into a single quantified-path-pattern MATCH parameterized by `$allowed_path_maps`. No `UNION ALL` over routes is emitted.
- **Active-and-not-deleted-on-user-branch.** Each `IS_RELATED` edge in the iteration is validated by `branch IN $valid_branches AND status = "active" AND from <= $at AND (to IS NULL OR to >= $at)` plus a `NOT EXISTS { …{status: "deleted", branch: $user_branch}… WHERE del.from > <active edge>.from AND del.from <= $at AND (del.to IS NULL OR del.to >= $at) }` clause. The deletion-edge comparison `del.from > r1.from` (and `> r2.from`) ensures we only treat a deletion as superseding the active edge if it happened *after* the active edge began — otherwise the deletion is an old marker that has already been overridden by the active edge we're matching. The `del.from <= $at AND (del.to IS NULL OR del.to >= $at)` clause requires the deletion to itself be current at `$at`. Together these replace the latest-authoritative-edge `LIMIT 1` pattern needed by the old generic-variable-length shape.
- **`a.kind` is read as a property here.** The QPP's label-union `(a:TypeA|TypeB|...)` prunes the search space via the label index; once a kind is bound, the renderer uses `a.kind` (a property) as the key into the nested `$allowed_path_maps` parameter, because Cypher cannot use a parameter as a label inside a QPP iteration. `a.kind` is consistent with how the existing `path.py` stores and reads node kinds.
- **Plan-derived structural filter.** `AND rel.name IN keys($allowed_path_maps[a.kind]) AND b.kind IN $allowed_path_maps[a.kind][rel.name]` enforces that every step of the walk is a (start, rel, end) triple the planner approved. Routes the planner pruned (permission, user-filter) contribute no entries to the map, so the QPP cannot walk through them.

Shared between strategies:

- **Kind labels are text-interpolated, not parameter-bound** (in the per-route MATCHes of strategy A and the label-union in strategy B). Cypher does not let parameters be labels in patterns where the label index can be used. Kind names are safe to interpolate as label literals because (a) the planner sources them from the schema, (b) schema kind names are validated alphanumeric by Infrahub's schema layer, and (c) the renderer asserts each kind name matches `^[A-Za-z][A-Za-z0-9]*$` before insertion. **Relationship identifiers, node UUIDs, branch names, and the `$allowed_path_maps` body remain parameter-bound.**
- **Relationship name** is on the `:Relationship` vertex's `name` property and is parameter-bound (`$rel_route{R}_hop{H}` in strategy A; one of `$all_rel_names` in strategy B).
- **Each schema hop = two `IS_RELATED` edges.** Strategy A makes both edges visible as named edge variables (`r0a`, `r0b`); strategy B's QPP iteration matches both per repetition.
- **`$at` is required by both strategies.** Even when the request implicitly asks for "now" (i.e. `at = current_time`), the temporal predicates must still be emitted: `from <= $at AND (to IS NULL OR to >= $at)`. Omitting `$at` would silently let `at`-in-the-past queries return paths that don't exist at the requested time. The renderer binds `$at` from the function parameter without exception.
- **Terminal predicate**:
  - `TerminalById`: emitted as `WHERE target_rR.uuid = $destination_id` inside each route subquery (each route's terminal vertex is aliased `target_r0`, `target_r1`, …). All routes share `$destination_id` as a single parameter.
  - `TerminalByKinds`: each route already commits to a specific terminal kind via its `:end_kind` label, so the kind constraint is structural; no extra `WHERE` clause is needed for kind filtering. The terminal id is unconstrained.
- **Time filter (`$at`)**: both strategies bind `$at` directly from the renderer's `at` parameter (serialized in the same form the edge `from`/`to` properties use). The existing `branch.get_query_filter_path(at=at)` helper is **not** used by either new strategy — strategy A inlines its own four-predicate conjunction (branch, status, `from <= $at`, `to IS NULL OR to >= $at`), and strategy B inlines the same conjunction inside the QPP iteration plus the deletion-asymmetry check. The helper's all-in-one filter was tuned for the old single-MATCH variable-length shape and is no longer needed.
- **Validation against EXPLAIN/PROFILE**: the per-hop CALL pattern is the established Infrahub idiom for "latest authoritative edge" (see [`path.py:184-196`](../../../../backend/infrahub/core/query/path.py)). The implementation MUST run `EXPLAIN` on a representative generated query during the benchmark task (SC-002) to confirm Neo4j is using the label index on the route's kind labels and the relationship-index on `(:Relationship).name`. If `EXPLAIN` shows an `AllNodesScan`, the implementation needs adjustment before merge.

## Behavior — required

`render_plan_to_cypher`:

1. Dispatch on `branch.is_default`: `True` → `_render_default_branch`, `False` → `_render_user_branch`. Both return the same `RenderedCypher` shape.
2. Validate every interpolated kind label against `^[A-Za-z][A-Za-z0-9]*$` before insertion (defence-in-depth; the planner already only emits schema-resident kinds). Raise `ValueError` if a kind name fails the check. This check applies to both strategies and to both per-route labels (strategy A) and label-union members (strategy B).
3. Apply `LIMIT $max_results` after `ORDER BY depth ASC, path` for stable shortest-first ordering (SC-002 reproducibility).

`_render_default_branch`:

4. Generate one `UNION ALL` branch per route, in `plan.routes` order. Each branch is its own `CALL { ... }` subquery so that variable scoping is isolated per route.
5. Inside each route subquery, emit hops sequentially. For hop H, emit the two-`IS_RELATED`-edge `MATCH` pattern corresponding to `Hop.direction`, with `Hop.start_kind` and `Hop.end_kind` as Neo4j labels, the relationship identifier as a parameter on the `:Relationship` vertex, and **named edge variables** `r{H}a` and `r{H}b` so the inline WHERE can reference them.
6. After each hop's MATCH, emit an inline `WHERE` that asserts, for both `r{H}a` and `r{H}b`: `e.branch IN [$default_branch, $global_branch] AND e.status = "active" AND e.from <= $at AND (e.to IS NULL OR e.to >= $at)`. No `CALL`-with-`LIMIT 1` subquery is emitted.
7. After all hops are validated, emit a final `MATCH path = (source)-[…full route pattern…]-(target_r{R})` that re-binds the already-validated vertices into a `path` value for the return shape.
8. Bind `$default_branch`, `$global_branch`, and `$at` once at the top of `params`. `$default_branch` and `$global_branch` come from the registry; `$at` is the renderer's `at` argument serialized to the same form `IS_RELATED.from`/`to` use.
9. Variable-name discipline: `rel_r{R}_h{H}` (Relationship vertex of hop H in route R), `n_r{R}_h{H}` (end-kind node of hop H), `target_r{R}` (the route's terminal vertex), `r{H}a`/`r{H}b` (the two `IS_RELATED` edges of hop H within a route). Names are scoped to one `CALL { ... }` block.

`_render_user_branch`:

10. Derive `$allowed_path_maps` deterministically from `plan.routes`: iterate every `Hop` in every `Route` and accumulate `allowed_path_maps[hop.start_kind].setdefault(hop.relationship_identifier, set()).add(hop.end_kind)`. Convert the inner sets to sorted lists for deterministic output.
11. Derive `$all_rel_names` = the sorted union of every `relationship_identifier` appearing anywhere in `$allowed_path_maps`.
12. Derive the start-kind union label list `(a:TypeA|TypeB|...)` = sorted union of `keys($allowed_path_maps)`. Derive the end-kind union label list `(b:TypeC|TypeD|...)` = sorted union of every kind that appears as a value in any inner list of `$allowed_path_maps`.
13. Set `$max_path_length = plan.max_depth`.
14. Emit a single `MATCH path = (source)( … QPP iteration body … ){1, $max_path_length} (target)` (or `(target:Node) WHERE …` for `TerminalByKinds`).
15. Inside the iteration body, emit:
    - The active-edge predicates for both `r1` and `r2`: `branch IN $valid_branches AND status = "active" AND from <= $at AND (to IS NULL OR to >= $at)`.
    - Two `NOT EXISTS { … {status: "deleted", branch: $user_branch} … WHERE del.from > <active edge>.from AND del.from <= $at AND (del.to IS NULL OR del.to >= $at) }` clauses (one for the `(a, rel)` edge, one for the `(rel, b)` edge). The `del.from > r{N}.from` predicate is essential — without it, the QPP would treat an *older* deletion as still superseding a *newer* active edge, which is wrong.
    - The plan-derived structural filter `rel.name IN keys($allowed_path_maps[a.kind]) AND b.kind IN $allowed_path_maps[a.kind][rel.name]`.
16. Compute `depth` from path length: `length(path) / 2` (every schema hop is two `IS_RELATED` edges, so `length(path)` is always even).
17. Bind `$valid_branches = [default_branch, global_branch, user_branch]`, `$user_branch` (= `branch.name`), and `$at` (renderer's `at` argument, serialized) once.

## Behavior — forbidden

- Must not call the planner, the database, the schema, or the permission system. Pure function over `Plan` + a few primitives.
- Must not interpolate **user-supplied** strings into Cypher. Kind names (interpolated as labels) and relationship identifiers (bound as parameters) come from the planner, which sources them from the schema; user-supplied filter strings (`kind_filter`, `excluded_kinds`, etc.) influence which `Plan` routes exist but never appear in the generated Cypher directly.
- Must not depend on Neo4j-only features beyond what the codebase already uses (no APOC, no dynamic-label `:$()` syntax).
- Must not exceed the existing `Query` base contract — `text`, `params`, `return_labels` are all the caller needs.

## Caller integration (`PathTraversalQuery.query_init`, `ReachableNodesQuery.query_init`)

The Query class holds a guaranteed non-empty `Plan` on `self.plan` (the GraphQL resolver enforces the empty-plan short-circuit upstream — see [planner.md §Caller Contract](planner.md#caller-contract)). The Query's `__init__` raises `ValueError` if a caller passes an empty plan; no short-circuit path exists in `query_init`. All imports live at module top.

```python
# backend/infrahub/graph_traversal/path.py
from infrahub.graph_traversal._cypher import render_plan_to_cypher
from infrahub.graph_traversal.planning import TerminalById

class PathTraversalQuery(Query):
    def query_init(self, ...):
        max_results = (
            self.max_paths
            if isinstance(self.plan.terminal_predicate, TerminalById)
            else self.max_results
        )
        rendered = render_plan_to_cypher(
            plan=self.plan,
            source_id=self.source_id,
            branch=self.branch,
            at=self.at,
            max_results=max_results,
        )
        self.query_lines = [rendered.text]
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)
```

Existing `extract_path_data(neo4j.Path)` and the result-shaping in `path.py` / `reachable.py` operate on the returned `path` and `depth` columns exactly as they do today.

## Tests required

Snapshot tests on the full Cypher text are explicitly **out of scope** — they are brittle, drift with every formatting change, and don't actually verify correctness. The real correctness gate is the component test suite running the generated query against a live database (see [../plan-schema-planning.md §Source Code](../plan-schema-planning.md#source-code-repository-root) — `backend/tests/component/graph_traversal/`). The unit tests below are *structural assertions* on the rendering: they catch contract violations (injection-prone interpolation, missing parameter bindings, missed direction arrows) without locking in incidental text formatting.

- `test_cypher.py` (in `backend/tests/unit/graph_traversal/`)
  - **Boundary**: `from infrahub.graph_traversal.planning import *` does NOT expose `render_plan_to_cypher` (proves the planning/ package contains no Cypher).
  - **Defensive non-empty assertion**: passing an empty `plan.routes` to `render_plan_to_cypher` raises `ValueError`. (The GraphQL resolver is the actual short-circuit point; this is a backstop for callers that bypass it.)
  - **Parameter-binding completeness**: every parameter in `rendered.params` appears as `$<name>` in `rendered.text`. Conversely, no `$<name>` appears in `rendered.text` that is missing from `rendered.params` (regex extraction of `$\w+`).
  - **Kind-label validation**: every label interpolated into `rendered.text` matches `^[A-Za-z][A-Za-z0-9]*$` (regex scan of `:<Label>` occurrences).
  - **Strategy dispatch**: `render_plan_to_cypher(... branch=<default_branch_mock> ...)` produces a `RenderedCypher.text` containing `UNION ALL` (or just `CALL {` for a 1-route plan) and the literal `.from <= $at`; the same plan rendered with `branch=<user_branch_mock>` produces text containing the QPP literal `){1,`, `$allowed_path_maps` references, and `del.from > r1.from` (the deletion-asymmetry marker). Use boolean substring checks to keep the test resilient to formatting.

  Default-branch strategy:
  - **Route fan-out**: number of `UNION ALL` keyword occurrences in `rendered.text` equals `len(plan.routes) - 1`.
  - **Per-route isolation**: number of top-level `CALL {` blocks within the `UNION ALL` body equals `len(plan.routes)` — proves each route is in its own subquery.
  - **Per-hop edge validation**: every named edge variable `r{H}a` / `r{H}b` in each route's pattern is followed within the same route block by a `WHERE` clause containing all four of `.branch IN [$default_branch, $global_branch]`, `.status = "active"`, `.from <= $at`, and `(<var>.to IS NULL OR <var>.to >= $at)` for that variable.
  - **`$at` is bound and used**: `rendered.params["at"]` is set; `rendered.text` references `$at` at least `2 * Σ len(route.hops)` times (twice per `IS_RELATED` edge: once in the `from` predicate and once in the `to` predicate).
  - **No latest-authoritative subqueries**: `rendered.text` MUST NOT contain `ORDER BY r.branch_level DESC, r.from DESC` (that pattern is the pre-refactor shape and would defeat the perf win).
  - **No post-hoc UNWIND**: `rendered.text` MUST NOT contain `UNWIND range(0, size(rels)` or `collect(edge_active)`.

  User-branch strategy:
  - **Single QPP MATCH**: `rendered.text` contains exactly one `MATCH path = (source) (` substring and exactly one `){1, $max_path_length}` substring; zero `UNION ALL` occurrences.
  - **Allowed-path-map plumbing**: `rendered.params["allowed_path_maps"]` is a `dict[str, dict[str, list[str]]]`. For every `Hop` in every `Route` in `plan.routes`, `hop.end_kind in rendered.params["allowed_path_maps"][hop.start_kind][hop.relationship_identifier]`. Conversely, no kind appears in the map that is absent from `plan.routes`.
  - **All-rel-names**: `rendered.params["all_rel_names"]` equals the sorted set of every `relationship_identifier` appearing in `plan.routes`.
  - **Active-edge `$at` predicates inside the QPP iteration**: `rendered.text` contains, for both `r1` and `r2`, the predicates `.from <= $at` and `(<var>.to IS NULL OR <var>.to >= $at)`.
  - **Deletion-EXISTS pair**: `rendered.text` contains exactly two `NOT EXISTS {` blocks inside the QPP iteration. Each block (a) references `{status: "deleted", branch: $user_branch}`, (b) contains `del.from > r1.from` or `del.from > r2.from` (matching the active edge of the same direction), and (c) contains `del.from <= $at AND (del.to IS NULL OR del.to >= $at)`.
  - **Depth arithmetic**: `rendered.text` contains `length(path) / 2 AS depth` (two `IS_RELATED` edges per schema hop).

  Shared:
  - **Defensive non-empty assertion**: passing an empty `plan.routes` to `render_plan_to_cypher` raises `ValueError` (independent of branch).
  - **Parameter-binding completeness**: every parameter in `rendered.params` appears as `$<name>` in `rendered.text`. Conversely, no `$<name>` appears in `rendered.text` that is missing from `rendered.params`.
  - **Kind-label validation**: every label interpolated into `rendered.text` matches `^[A-Za-z][A-Za-z0-9]*$` (regex scan of `:<Label>` and label-union `:Label1|Label2` occurrences).
  - **Direction encoding** (default-branch strategy only; the user-branch QPP body has a fixed arrow shape): for a single-hop default-branch `Plan` with `Hop.direction = OUTBOUND`, the text contains `-[r0a:IS_RELATED]->(rel_` then `)-[r0b:IS_RELATED]->(`; for `INBOUND`, contains `<-[r0a:IS_RELATED]-(rel_` then `)<-[r0b:IS_RELATED]-(`; for `BIDIR`, contains `-[r0a:IS_RELATED]->(rel_` then `)<-[r0b:IS_RELATED]-(`.
  - **Terminal mode parity (User Story 3, SC-006)**: for the same `Plan.routes` and same branch, swapping `plan.terminal_predicate` between `TerminalById(...)` and `TerminalByKinds(...)` changes `rendered.text` only inside the terminal predicate clauses — verified by diffing both renders.

Correctness (paths actually returned for a known graph) lives in `backend/tests/component/graph_traversal/test_path_traversal_query.py` and `test_reachable_nodes_query.py`.
