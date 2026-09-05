# 16. Conjunctive Pre-filter for Targeted Uniqueness Validation

**Status:** Proposed
**Date:** 2026-09-04
**Author:** @ajtmccarty

## Context

`TargetedUniquenessValidationQuery` validates a composite uniqueness constraint for a set of
changed nodes. It picked one constraint element as an *anchor*, ran the only population-wide
`MATCH` on that element's value, then put every candidate through a liveness check and a
current-value resolution per remaining element.

The anchor choice decides almost everything. Issue #10493 reports a merge exhausting a 2 GiB
Neo4j transaction after updating ~30 nodes, because the anchored element was a relationship whose
peer had a very large fan-out: the query pulled the whole sibling set through per-candidate work.

The decisive constraint on any fix is that **the correct anchor is a property of the data, not of
the schema**. Two schemas can be textually identical — `[relationship, name__value]` with `name` a
plain non-unique `Text` attribute — and have opposite optimal anchors:

| Case | relationship fan-out | attribute repetition | better anchor |
|---|---|---|---|
| #10493 repro shape | ~50,000 siblings | value near-unique | the attribute |
| `DcimInterface [device, name__value]` | mean 44 (min 16, max 54, 5,350 devices) | mean 2,263 (104 distinct values over 235,400 nodes) | the relationship |

No static rule can separate these, because nothing in the schema distinguishes them. This was
confirmed empirically for three different static rules — see Alternatives.

All measurements below are from one database (a restored ~235k-interface dataset plus purpose-built
fixtures), `DcimInterface [device, name__value]`, 40 changed nodes. Timings are medians of 5 runs
with a discarded warm-up, executed without `PROFILE`; memory and page hits come from separate
`PROFILE` runs. "hub" is a fixture with one device carrying 50,050 interfaces with distinct names;
"mixed" is the natural population.

## Decision

Replace anchor selection with a single **conjunctive pre-filter**: a candidate must have an edge to
*every* one of the changed node's constraint values before any per-candidate work runs.

`_anchor_element_index` and `_render_anchor_probe` are removed; `_render_prefilter` replaces them,
and every element — including what used to be the anchor — now goes through the same per-element
resolution step.

The pre-filter deliberately carries **no branch or time predicate**, so it matches any edge that
ever existed. That makes it a necessary-but-not-sufficient condition: it can only shrink the
candidate set, never decide membership. Each surviving candidate's current value is still resolved
under the normal `branch_level DESC, from DESC, status ASC` rules before it counts as a collision.
Which value vertex the planner seeks first is left to Neo4j; every entry point is index-backed
(`node_uuid`, `attr_value_indexed`).

## Consequences

### Positive

- **Peak memory becomes independent of data shape** — ~190 KB on both fixtures, versus 1.47 MB
  (mixed) to 1.58 GB (hub) before. Candidates are discarded by cheap pattern matching before the
  expensive liveness and branch-resolution subqueries run, so row cardinality never explodes.
- **Removes the declaration-order footgun.** The previous code's cost depended on the order elements
  were written in: `[device, name]` cost 73,584 page hits and `[name, device]` cost 17,500,311 — a
  238x swing for a semantically identical constraint. The pre-filter renders identically in both
  orders (byte-identical page hits and rows).
- **Eliminates the OOM class.** Worst case across both fixtures drops from 27,038 ms / 1.58 GB to
  1,681 ms / 193 KB. A wrong entry point becomes a slow query rather than an aborted merge.

### Negative

- **Selective constraints get materially slower.** On the mixed shape, 28.5 ms -> 1,681 ms (59x).
  This is the real cost of the decision and the main reason to review it: we buy worst-case safety
  with common-case speed. Whether that is the right trade depends on how common hub-shaped
  constraints are in customer schemas, which nobody has measured.
- **The planner does not choose the best entry point unaided.** It picks the same entry the old
  static rule did (5,109,589 page hits on mixed against 73,584 achievable).

### Neutral

- Violation semantics are unchanged. Verified to report identical violations to both the previous
  implementation and the anchor-swap alternative, in both element orders, on a fixture with
  deliberate collisions including a same-name/different-peer case that must not collide.
- `_supports_targeted` and the full-population fallback (`NodeUniqueAttributeConstraintQuery`) are
  untouched.

## Alternatives Considered

### Static anchor rule: prefer an indexed attribute (the #10493 patch)

Fixes the reported case decisively (independently reproduced: 128,208,120 -> 2,680 page hits,
1.58 GB -> 192 KB on the hub fixture) but inverts the pathology. On `DcimInterface` it is 229x worse
in page hits and 70x worse in memory than the code it replaces, degrading linearly with change size
(103 MB at 40 changed nodes, 513 MB at 200). It trades one shape's OOM for another's.

### Streaming instead of `collect()` alone

Rejected as insufficient. At a bad anchor on the hub fixture streaming still used 1.28 GB versus
`collect`'s 1.58 GB — only 19%, and unbounded, because the rows still flow even when no list is
materialised. Streaming is a ~20-30% effect; the anchor is a ~6,700x effect. It is not a safety net.

### `collect(candidate.uuid)` instead of `collect(candidate)`

Rejected: measurably worse. Memory rose 57% (mixed) and 48% (hub, 1.58 GB -> 2.34 GB) with page hits
essentially unchanged. Neo4j collects node *references* (compact); uuids are 36-character `String`
objects on the heap. Note this means Principle V's "never return entire nodes" is a wire-format
rule, not a transaction-memory one.

### Runtime selectivity probe

A capped `LIMIT` count per eligible anchor, picking the smaller. Correct in principle and would
choose well on both shapes, but adds a round trip per constraint group per batch, and the
pre-filter makes it unnecessary for *safety* — it would now be a pure CPU optimisation. Worth
revisiting as a follow-up rather than a prerequisite.

### Recurring job that reorders `uniqueness_constraints` by measured degree

Rejected as a complete solution. A single static order must serve every value of an element:
ordering by mean leaves the tail exposed (adding a 50k hub moves `DcimInterface`'s device mean only
to 53.3, so the "correct" order is unchanged and the OOM persists), while ordering by max sacrifices
the body (99.98% of devices would pay 51x to protect one). Separately, schemas are frequently
sourced from Git repositories, so in-place edits are reverted on the next sync. Its statistics
remain useful as a *classifier* — a high max/mean ratio is the OOM signature.

### `USING INDEX` hints to force the entry point

Tested; reproduces the static-anchor problem in different syntax. Hinting the relationship entry
gives 15.0 ms on mixed (better than any other option) but 3,526 ms on hub; hinting the attribute
entry gives the reverse. Hint syntax differs per element kind, and `USING INDEX` is a hard hint —
Neo4j errors rather than degrading when it cannot be satisfied. A *per-value* hint would be optimal;
a static one is not.

### Lowering `query_batch_size`

Not an alternative but a complementary lever, and worth separate consideration. It defaults to 500
(`checker.py`). On the hub fixture, page hits are exactly linear in window size while memory fits
`~308 MB + 31.8 MB x N` for N >= 2, extrapolating to roughly 16 GB at the default — which is how
~30 changed nodes produced a 2 GB transaction. Eight batches of 5 do identical total work to one
batch of 40 at 467 MB instead of 1.58 GB. It is a ~3x lever with a ~308 MB floor, so mitigation
rather than a fix.

## Open Questions

- **Selectivity against real edge history is unmeasured.** Every fixture used here is churn-free,
  and the pre-filter is history-blind by construction — a candidate that *once* held a value still
  passes it. #10493 names graph history as a factor in the original incident.
- **Only two-element constraint groups were exercised.** Three or more clauses give the planner more
  to intersect, with unknown effect.
- **Is the 59x common-case regression acceptable?** That depends on the prevalence of hub-shaped
  constraints in real schemas. If it is not, the pre-filter plus a per-value entry hint would give
  both bounds (15.0 ms mixed / 3.9 ms hub were both observed with the right hint), at the cost of
  reintroducing an entry-point decision — but one whose worst case is now ~1.7 s rather than an
  aborted merge.
