# Findings: merge and rebase recompute cost at scale

**Date**: 2026-06-24 · **Status**: Complete (counting layer + timing layer) · **Spec**: [spec.md](./spec.md)

Produced by running the profiling harness: the deterministic counting layer
(`backend/tests/component/merge_recompute/`) and the full-stack timing layer
(`backend/tests/integration_docker/test_merge_recompute_timing.py`, gated by
`INFRAHUB_PROFILE_TIMING`). Timings are from a local testcontainer stack
(2 API servers, 2 task workers, community Neo4j) and are stack-relative; the
growth shape and relative attribution are what transfer, not the absolute seconds.

## Headline: the cost model is cross-node, and the trailing recompute dominates

The original assumption — "one node event per changed node → one recompute job" —
is incomplete. Profiling established three things about what does and does not
dispatch asynchronous recompute:

1. **A same-node update recomputes inline.** When a node's own field changes
   (e.g. its `name`), its computed attribute / display label / human-friendly id
   are recomputed synchronously during the save. This creates **zero**
   asynchronous recompute work. A direct edit, and a merge of such edits, produced
   no recompute flow runs at all.
2. **A cross-node update fans out to readers.** When a node that other nodes
   *read* changes (here a peer referenced via `peer__name__value`), each reader
   recomputes asynchronously, once per family that reads across the relationship.
   The human-friendly id reads only the local name, so it does **not** fan out on a
   peer change; the computed attribute and display label do.
3. **A creation fans out to all of the new node's families.** Creating a node
   dispatches asynchronous recompute for every derived value it carries — computed
   attribute, display label, **and** human-friendly id. Seeding 2000 nodes
   dispatched ~5000 recompute flows (~1000 of each family per 1000 nodes carrying
   all three), so a merge that creates many nodes pays this fan-out too, not only
   one that edits read-targets.

So the asynchronous recompute cost is driven by cross-node updates
(`changed read-targets × readers × families-read-across-the-relationship`) and by
creations (`created nodes × families-on-the-node`), not by the raw changed-node
count and not by same-node edits.

## Counting layer (deterministic, in CI)

Emitted node events and the in-process cross-node fan-out estimate, per changed
node count, for the cross-node scenario (one reader per changed peer):

| operation | scale  | changed nodes | node events | derived fan-out (computed / display / hfid) |
|-----------|--------|---------------|-------------|---------------------------------------------|
| merge     | small  | 10            | 10 updated  | 10 / 10 / 0                                 |
| merge     | medium | 100           | 100 updated | 100 / 100 / 0                               |
| rebase    | small  | 10            | 10 updated  | 10 / 10 / 0                                 |

Same-node control (mutating the mains' own `name`): merge still emits one node
event per changed node, but the derived fan-out is `0 / 0 / 0` — confirming the
inline-recompute finding deterministically, with no worker.

Growth (counting layer): node events and cross-node fan-out are both **linear**
in the changed-node count.

## Timing layer (full stack, on demand)

Cross-node merge (changed peers each read by one main), executed recompute counted
by the recompute deployment names on the default branch as a before/after delta:

| scale  | changed nodes | merge critical path (s) | recompute window (s) | executed recompute runs |
|--------|---------------|-------------------------|----------------------|-------------------------|
| small  | 10            | 20.6                    | 6.2                  | 20                      |
| medium | 100           | 13.6                    | 56.8                 | 200                     |
| large  | 1000          | 27.6                    | 638.9 (~10.6 min)    | 2000                    |

`schema_migration_s` and `db_commit_s` are unattributed here (data-only merge; see
Not covered).

### Growth and the dominant cost center

Confirmed across three scales (10 / 100 / 1000):

- **Executed recompute runs**: **linear** — 20 → 200 → 2000, exactly two per changed
  node (computed attribute + display label), one reader each.
- **Trailing recompute window**: grows **linearly** (6.2 → 56.8 → 638.9 s; each 10×
  in changed nodes is ~10× the window) and **dominates at scale** — at 1000 changed
  nodes the trailing recompute is ~10.6 minutes against a 27.6 s merge call, in the
  ballpark of the epic's reported ~20-minute degraded-instance window.
- **Merge critical path**: **fixed overhead**, not a function of the changed-node
  count (13–28 s with no trend across 10×–100× scale; the variation is merge
  machinery / warmup noise).

**Dominant growing cost center: the trailing asynchronous cross-node recompute
fan-out** — the degraded-instance window. The synchronous merge is fixed overhead;
the cost that scales (linearly, to minutes) is the per-reader recompute the merge's
node events trigger.

## Implications for the coalescing redesign

- Coalescing should target the **asynchronous recompute fan-out**, not the merge
  transaction. The lever is reducing the number of recompute jobs the merge's node
  events dispatch (dedup readers, batch per-family, collapse duplicate targets),
  since that count drives the degraded window and grows linearly with the change.
- Cover **both** triggers: cross-node updates (fan out to readers) and creations
  (fan out to the new node's own families). A merge that creates many nodes pays
  the same cost as one that edits many read-targets, so the redesign cannot ignore
  the creation path.
- Same-node updates are already inline and cheap; they are not the problem.
- Per-family scope differs by trigger: a cross-node update only re-runs the
  families that read across the relationship (here computed attribute + display
  label, not the local-only human-friendly id), whereas a creation re-runs every
  family on the node (including the human-friendly id). The redesign's
  per-family handling must account for this.

## Not covered (honest scope)

- **Schema-migration cost** (T016) and **DB-commit attribution** (T017) were left
  unattributed (`None`): the profiled merges are data-only. Isolating migration
  cost needs a schema-changing merge differenced against a data-only one of equal
  size; this is a follow-up if the redesign needs it.
- **Fan-out ratio > 1**: this dataset uses one reader per changed node. A higher
  reader-per-node ratio would multiply the recompute count; the harness can model
  it by sharing peers across mains.
- Absolute seconds are stack-relative (local testcontainers); production hardware
  will differ. Growth shape and relative attribution are the transferable results.

## Reproduce

```bash
# Counting layer (deterministic; standalone Neo4j on localhost:7687)
uv run pytest backend/tests/component/merge_recompute/test_merge_recompute_counts.py -q

# Timing layer (full stack; build the image first)
INFRAHUB_IMAGE_VER=local-dev INFRAHUB_TESTING_IMAGE_VER=local-dev uv run invoke dev.build
INFRAHUB_PROFILE_TIMING=1 INFRAHUB_TESTING_IMAGE_VER=local-dev INFRAHUB_PROFILE_SCALE=100 \
  uv run pytest backend/tests/integration_docker/test_merge_recompute_timing.py -q -s
```
