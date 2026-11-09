# Contracts: Batch Python Computed-Attribute Recompute

## External API — unchanged

- GraphQL mutation `InfrahubUpdateComputedAttribute`: remains published and functional (public API). This feature only stops calling it internally.
- No REST/GraphQL schema changes; no generated-file changes expected beyond none.

## Internal flow contract — `computed_attribute_process_transform` (stable)

Parameters (unchanged, Prefect deployment contract):

```
branch_name: str
node_kind: str
object_ids: list[str]          # ≤ get_submission_chunk_size() ids
computed_attribute_name: str
computed_attribute_kind: str
context: EventContext
```

Behavioral contract (changed internals, preserved observables):

| Observable | Before | After |
|---|---|---|
| Final attribute values | v | v (identical) |
| NodeUpdated event per really-changed node | yes (from mutation) | yes (from bulk writer, live origin) |
| Events / cascade for unchanged values | yes → echo | none |
| Client-visible mutations issued | N | 0 |
| Flow run visible under branch tag filter | yes | yes (tag at submission) |
| One node's failure | fails its own task | skipped + logged; siblings persist |

## Event contract

`NodeUpdatedEvent` granularity, payload, and origin (live) for really-changed nodes are identical to a direct attribute update — downstream consumers (webhooks, dependent computed attributes, UI) require no changes.
