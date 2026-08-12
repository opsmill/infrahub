# Contract: Python target resolution

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

Infrahub exposes no new public interface for this feature. No REST endpoint, no GraphQL field, no CLI command, no SDK method changes. This document records the one **internal** contract it introduces, because two implementations must satisfy it and because getting its failure semantics wrong is how this feature ships stale data.

Supersedes an earlier draft that covered the reader axis only. Both axes need the same lookups, so both belong here.

## Purpose

Narrow the Python targets of a coalesced recompute from "every node of an owning kind" down to the nodes today's per-node automations would actually have refreshed, using a bounded number of lookups, and never fail closed.

Two narrowings, from the same data:

| Axis | Narrowing |
|---|---|
| Owner | keep a changed node only when one of its changed fields is a field the transform's query reads on that kind |
| Reader | resolve which nodes actually read the changed nodes, then apply the same field test on the reading kind |

The read-field test is not an optimisation. It is what the current triggers already do, so omitting it makes merges slower rather than faster.

## Shape

The protocol is `PythonTargetResolver`, with a single entry point:

```text
PythonTargetResolver.resolve(
    coalesced: CoalescedRecompute,
    changes: Sequence[MergeChange],
    branch: str,
    deleted_at: Timestamp | None,
) -> CoalescedRecompute
```

Same type in, same type out. Every consumer downstream is unaffected.

`changes` is the merge or rebase change set. The read-field test needs each changed node's changed fields, and the target does not carry them because the builder groups them away when it deduplicates. It is transient work data rather than a collaborator, so it is passed to the method rather than injected. Added during implementation; the first draft of this contract omitted it and the narrowing could not have been written against that signature.

`deleted_at` is the merge's own timestamp, and is `None` on a path with no deletes. Guarantee 8 below is the only thing that reads it.

## Guarantees the implementation MUST provide

1. **A bounded number of lookups, independent of the changed-node count.** One pass to derive the read fields, and a chunked subscriber lookup whose chunk count follows the submission limit already in use. What is forbidden is a lookup per node; that is the defect this feature exists to remove.

2. **Never return an unresolved target.** Every Python target in the returned value carries either a concrete node id set, or an explicit whole-kind marker. There is no in-between state, and an empty id set never means "everything" — it means nothing to do, and the target is dropped.

3. **Widen on any doubt, and only as far as one pair.** These all widen:
   - a lookup raised, timed out, or returned an error
   - the transform's read set is imprecise
   - the readers of a deleted node cannot be identified

   Widening applies to the affected attribute-and-kind pair alone. It never widens a second pair and never escalates to a whole-branch refresh.

4. **Never propagate an exception.** The caller runs inside a guard that swallows everything, so an escaping error would silently skip all four derived-value families, not just the Python one. Catch internally, widen, log, return.

5. **Record every widening.** The affected pair and the reason must both be recoverable from the logs. This is what FR-020 is checked against.

6. **Do not mutate the input.** Return a new value.

7. **Non-Python targets pass through untouched.** The three existing families resolve from the schema and must not be reshaped, reordered or dropped.

8. **Point-in-time resolution applies to deleted nodes only.** A node deleted by the merge has already had its membership records closed, so a current-time lookup finds nothing. But resolving *everything* at a pre-merge time would hide memberships the merge itself created, which is its own under-recompute. Resolve created and updated ids at current time, deleted ids at the earlier time, and take the union.

## Failure semantics

| Situation | Result |
|---|---|
| Lookup succeeds, targets found | Precise target, those node ids |
| Lookup succeeds, no targets found | Target dropped. Genuinely nothing to do. |
| Changed fields do not intersect the read fields | Target dropped. This is the case today's trigger already skips. |
| Lookup raises or times out | Widen that pair to its whole kind, log the reason |
| Read set is imprecise | Widen that pair to its whole kind, log the reason |
| Branch or kind missing from the schema | Widen that pair, log. Do not raise: one bad pair must not abort the pass. |

Rows two and four are the whole contract. "I looked and there is nothing" and "I could not look" must never collapse into the same answer.

## Implementations

| Implementation | Used by | Notes |
|---|---|---|
| Client-backed | Production, on the merge and rebase paths and at every chain level | Derives the read-field index and issues the chunked subscriber lookup. |
| In-memory | Unit and component tests | Returns a canned mapping and can be told to fail. Lets every row of the table above be exercised without a database, and keeps the existing pure builder tests free of new collaborators. |

The in-memory implementation is not a convenience. It is the second implementation that justifies defining a protocol under the project's design rule.

## What this contract deliberately does not cover

- **Chunking and dispatch.** Downstream of resolution, unchanged.
- **The schema-coverage subtraction.** It runs before resolution and is a pure function.
- **Whether the pass runs at all.** The feature switch is checked by the caller.
