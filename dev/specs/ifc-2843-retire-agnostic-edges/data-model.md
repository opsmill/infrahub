# Phase 1 Data Model: Retirement of branch-agnostic property edges

**Feature**: `specs/ifc-2843-retire-agnostic-edges` | **Date**: 2026-08-12

**No new persisted entities and no new persisted state.** The diff-derived and query-derived
candidate sets remove any need for a marker, worklist, or queue — this is an explicit
out-of-scope item in the spec. What follows describes the *existing* graph entities the
invariant is stated over, plus the in-memory types the new components exchange.

## Graph entities

### `Node` (branch-aware)

The owner of a branch-agnostic field.

| Aspect | Detail |
|---|---|
| Label | `:Node` |
| Existence edge | `(:Node)-[:IS_PART_OF]->(:Root)` |
| Liveness | An **active** `IS_PART_OF` edge satisfying a given branch's own branch-and-time filter, with isolation applied |
| Identity caveat | **Evaluated per vertex, never per UUID** — see "Same-UUID copies" below |

### `Attribute` with `branch_support: "agnostic"`

| Aspect | Detail |
|---|---|
| Label | `:Attribute` |
| Owner edge | `(:Node)-[:HAS_ATTRIBUTE {branch: <global>}]->(:Attribute)` — **also closed by retirement** |
| Property edges | `HAS_VALUE`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER` — all on the global branch |
| Subject of the invariant | **Every** open global edge of the vertex, owning edge included — not only the four property edges |
| Open state | `status: "active"` **and** `to IS NULL` |
| Retired state | `to` set to a timestamp; `status` unchanged (FR-013) |

The owning edge is closed for two reasons, not one. It is part of what keeps the value looking
live, and — because it is also the candidate anchor (FR-011) — leaving it open would keep the
vertex a candidate on every subsequent pass forever.

**Half-closed vertices.** The owning edge and the property edges can be closed independently in
existing data: either closed while the other stays open. Retirement therefore closes each only
where it is still open, rather than assuming the two move together (FR-002a). Once this feature
ships no *new* half-closed state can arise, since both are closed in one pass — but the
pre-existing ones are unreachable from an open-edge anchor, which is why the repair migration
widens its anchor to `status: "active"` regardless of `to` (FR-011a) and recovers same-UUID
protection from the predicate instead.

### `Relationship` with `branch_support: "agnostic"`

| Aspect | Detail |
|---|---|
| Label | `:Relationship` |
| Peer edges | Two `IS_RELATED` edges, one per peer node |
| Property edges | Same four as `Attribute`, on the global branch |
| Retention | Requires **both** peers live **and both** `IS_RELATED` edges active, on the *same* branch |

The two-peer requirement is a correctness constraint, not a refinement: a `Relationship` vertex
is reachable from either peer, so a one-peer predicate keeps it open as long as *either* peer
survives — which is wrong, because a relationship with one peer is not a relationship.

### `AttributeValue`

De-duplicated by value across the whole graph. Retirement **detaches** (closes the edge); it
must never delete a vertex any other attribute still references (FR-017). Deleting one left with
zero references is permitted but not required, and is not a deliverable.

**Pool interaction — do not change without reading this.** A `NumberPool` reserves a value with a
`(:NumberPool)-[:IS_RESERVED]->(:AttributeValueIndexed)` edge. Retirement deliberately **does not
touch `IS_RESERVED`**. It does not need to: the used-value query requires `IS_RESERVED`,
`HAS_VALUE` *and* `HAS_ATTRIBUTE` to all satisfy the branch filter simultaneously, so closing
`HAS_VALUE` alone is enough to drop the value from the used set and make it allocatable again
(SC-007). That is a three-edge dependency, and a future change to the pool queries could break
SC-007 without touching a line of this feature — which is why an explicit allocate/delete/retire/
reallocate component test exists.

### `Branch`

Not modified. Read for its metadata only — from `registry.branch` at the runtime enforcement
points, and from the database in the migration, which runs in an upgrade process where the
registry may never have been populated. The registry is a maintained cache: it is refreshed on
branch create, merge, rebase and delete via a broadcast message, adds branches it does not yet
know, and has a scheduled sweep behind that.

| Field | Role in the predicate |
|---|---|
| `name` | Identifies the branch in the filter |
| `origin_branch` | The branch it forked from |
| `branched_from` | Defines the fork window — the timestamp the origin branch is read at |
| `is_isolated` | Always `True` in practice; **must not be overridden** (FR-012) |
| `is_default` | Default branch reads itself at `at`, with no fork collapse |

Branch lifecycle events — rebase, merge, deletion — are occasions to **re-evaluate** the
predicate, never releases in themselves (FR-009).

## Edge state model

A global property edge is in exactly one of three states:

```text
OPEN      status = "active",  to IS NULL     → value is reserved; ≥1 branch retains it
RETIRED   status = "active",  to = <ts>      → closed by this feature
SUPERSEDED status = "active", to = <ts>      → closed by an ordinary value update
```

`RETIRED` and `SUPERSEDED` are **indistinguishable in the graph**, and deliberately so. A
time-close is a time-close; nothing marks *why* an edge closed. This is what makes retirement
invisible to a branch that forked before it (FR-014) — the branch reads through its fork window
and finds whichever edge was open at fork time, exactly as it would after an ordinary update.

The state this feature never produces:

```text
FORBIDDEN  a new edge with status = "deleted" on the global branch
```

FR-013 rules this out. A global status tombstone would strip the field from every branch
immediately, including branches that legitimately still hold the object live.

## Predicate evaluation rules

### Liveness

```text
live(node_vertex, B) ≡
    ∃ e : (node_vertex)-[e:IS_PART_OF]->(:Root)
        ∧ e.status = "active"
        ∧ e satisfies B's branch-and-time filter with isolation applied
```

B's filter is the pair set produced by the branch-window builder:

```text
default branch:      {(global, B.name): at}
non-default branch:  {(global, B.origin_branch): min(at, B.branched_from),
                      (global, B.name):          at}
```

The `min(at, branched_from)` collapse **is** the fork window. It is why a branch that forked
between an object's creation and its deletion still counts as retaining: it reads the origin
branch as of the fork, where the object was alive.

Edge activity resolves with the constitution's mandated ordering:
`branch_level DESC, from DESC, status ASC`.

### Retention

```text
retains(B, V:Attribute) ≡
    ∃ n : live(n, B) ∧ active(HAS_ATTRIBUTE(n → V), B)

retains(B, V:Relationship) ≡
    ∃ p₁, p₂ : live(p₁, B) ∧ live(p₂, B)
             ∧ active(IS_RELATED(p₁ → V), B)
             ∧ active(IS_RELATED(p₂ → V), B)
```

### Retirement

```text
retire(V) when ¬∃ B ∈ open_branches : retains(B, V)
```

Applied as `SET e.to = $at` on every open global property edge of `V`.

### Candidate traversal constraint (FR-011 / FR-011a)

Two anchors, because the runtime paths and the repair migration have different jobs.

| | Runtime enforcement points | Repair migration |
|---|---|---|
| Anchor | Global owning edges that are **open and active** | Global owning edges with `status: "active"`, **open or closed** |
| Same-UUID protection from | The anchor (superseded copies have closed edges) | The **predicate** — a vertex is retained if *any* linked node vertex is live with an active owning edge |
| Reaches half-closed vertices | No — and does not need to (FR-002a) | Yes — that backlog is its responsibility |
| Cost | Selective; on the node-delete hot path | Wider; batched and off every hot path |

Neither anchor may start from node reachability alone. The open-edge anchor is also the
selectivity anchor: global owning edges exist only for branch-agnostic fields, so a deployment
with none matches zero rows.

The migration's widened anchor is safe precisely because the predicate — not the anchor — carries
the same-UUID protection there. Evaluating retention across *all* node vertices linked to the
field vertex is what the invariant literally says, so a vertex shared with a live copy is still
never retired.

### Same-UUID copies

Name, namespace, and inheritance changes leave several `:Node` vertices sharing one `uuid`, each
pointing at the **same** field vertex over its own global edge, with the superseded vertex's edge
closed as it is duplicated.

Two consequences, both load-bearing:

1. `live` is evaluated per **vertex**, joined on internal vertex identity — never on `uuid`.
2. Kind and inheritance migrations are **not** enforcement points. They already close the
   superseded vertex's global edge in the same pass, so the constrained traversal never reaches
   the shared vertex. Adding them as enforcement points would close a live object's value edges.

### Profiles and templates

Covered without enumeration. The predicate anchors on the `:Node`, `:Attribute` and
`:Relationship` labels rather than on schema kinds, so profile and template copies are included
automatically — unlike the per-kind `Kind|ProfileKind|TemplateKind` pattern the schema migrations
must follow.

## Orphan shapes repaired by `m076`

| # | Shape | Origin | Repair | Reported as |
|---|---|---|---|---|
| 1 | Node vertex present, open global edges, **no active existence edge on any branch** | Node deletion and schema removal, which tombstone at branch level and leave global edges open. **Confirmed at scale in the reported dataset** (~6,400 effectively-deleted nodes still holding an active global value). | **Close** — `SET e.to = <migration run time>` | edges closed |
| 1b | As above, but **half-closed**: owning edge closed and property edges open, or the reverse | Present in the reported data. Unreachable from an open-edge anchor, which is why FR-011a widens the migration's anchor. | **Close whichever edge is still open** | edges closed |
| 2 | `Attribute` / `Relationship` vertex with **no linked node vertex at all** | Branch deletions predating the existing agnostic-peer cleanup, which hard-deleted the existence edge and left the global edges pointing at nothing. Known to exist; **unquantified** — the measurement above is anchored on `(:Node)-[:HAS_ATTRIBUTE]->` and structurally cannot see this shape. | **Hard-delete** the vertex | vertices removed |
| 3 | Two attributes sharing one `AttributeValue`, one orphaned | Value de-duplication | Detach the orphan only; the surviving attribute keeps its value | (counted under 1 or 2) |
| 4 | Anything else the predicate cannot resolve | Pre-existing data oddities | **Report, do not raise** — the upgrade completes (FR-016) | errors list |

Shape 2 is why the migration hard-deletes rather than closes: such a vertex cannot be reached,
diffed, or time-travelled to, so a time-close would leave permanent garbage with no reader and
no future path to removal. Note that its prevalence is *not* established — the migration handles
all shapes and must not be sequenced or justified on the assumption that any one dominates.

## In-memory types (new)

> **Revised 2026-08-17.** The branch-window and candidate-bound types are gone. Windows are derived
> inside Cypher from `(:Branch)` rather than built in Python and passed in, and each enforcement
> point has its own query rather than one query parameterised by a discriminated bound — so neither
> type has a consumer. See plan.md §"Design revision".

Each query exposes its result as a frozen dataclass, per Principle III; none is persisted.

```text
NodeAgnosticRetirementResult   frozen  — edges_closed: int
```

The repair migration's result will additionally carry the count of hard-deleted vertices, which is
what FR-016 and SC-003 report to the upgrade log. Query results are exposed through a `get_data()`
method returning a frozen dataclass — never raw Neo4j records (Principle III).

**Superseded**: `BranchWindow`, `BranchWindowSet`, `RetirementCandidates` (explicit ids /
fork-point / unbounded), `RetirementResult(edges_closed, vertices_removed)`.
