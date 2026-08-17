# Data Model: Batch Python Computed-Attribute Recompute

No database schema changes. The entities below are in-memory processing structures.

## AttributeValueWrite (existing, reused)

One recomputed value destined for persistence.

| Field | Type | Notes |
|---|---|---|
| node_id | str | target node |
| field | str | computed attribute name |
| value | str \| None | recomputed value; only `str` reaches the writer on this path |

Source: `backend/infrahub/core/recompute/bulk_write.py`. Validation: this feature only enqueues writes whose `value` is `str` (R4).

## Transform batch result (new, transient)

`list[tuple[str, AttributeValueWrite | Exception]]` — node id paired with its outcome from the concurrent batch.

State transitions: collected → partitioned into `writes: list[AttributeValueWrite]` + `skipped: list[(node_id, reason)]` → writes dispatched, skips logged.

## Skipped node record (new, log-only)

`(node_id, reason)` where reason ∈ {"transform raised …", "transform returned <type>, expected a string"}. Surfaced as flow-run warning logs; no persistence (recovery surface is an explicit non-goal / follow-up).

## Invariants

- A node appears at most once per batch (ids deduplicated upstream at trigger time).
- A skipped node's stored value is untouched by the batch.
- `writes` ⊎ `skipped` = batch input (every node accounted for).
- Persisting a value equal to the stored one produces no changelog entry → no event → no cascade (writer invariant, relied upon).
