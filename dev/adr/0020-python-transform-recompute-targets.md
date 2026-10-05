# 20. Python transform targets from analyzed queries and query-group subscribers

**Status:** Accepted
**Date:** 2026-09-28
**Author:** @opsmill-team

## Context

[ADR 0017](0017-coalesced-merge-rebase-recompute.md) replaced the per-node recompute fan-out of
merge and rebase with one coalesced pass. It covered three families: Jinja2 computed attributes,
display labels, and human-friendly ids. All three share one property. What each value reads, and
which nodes read a given node, are schema facts. The builder derives them from the schema branch
it already holds, and reads no database.

Python transform computed attributes have neither fact in the schema. What a transform reads is
known only from its GraphQL query. Which nodes read a given node is known only from the query
groups those nodes subscribed to on their last successful compute. Both are runtime database facts.
So the family stayed outside the pass, and its two per-node trigger types kept matching every
mutation origin.

A merge or a rebase replays each changed node as an event. Every automation the event matched
started its own flow. The owner trigger is built per attribute, the query-group trigger per
transform and read kind. On the measured datasets, where each kind declares one Python attribute,
that came to one flow per changed node. Each flow paid its own transform-metadata query, repository
resolution and per-node data query, to write a value the merge had already carried over. Two
further loops ran on top. The coalesced writes of the other three families re-fired the Python
automations. The Python writes carried the live origin back into the per-node paths of every
family.

The cost tracks the size of the change set, not the number of readers. The replays were measured on
two datasets of very different size. They dropped by roughly twenty times on a multi-site network,
and by two orders of magnitude on a data-centre fabric. The unique node sets and the stored values
were identical on both. The bigger the change, the bigger the drop, because the new count follows
the submission chunk size and not the node count.

## Decision

Add the Python family to the coalesced pass, and derive it behind an interface
(`core/merge/recompute_coalescing.py::PythonTargetResolver`). The narrowing then needs no database
or client import of its own. Two runtime sources feed that interface. The analyzed transform
queries say what each attribute reads. The query-group subscriber index says which nodes read a
given node; [Groups](../../docs/docs/groups/overview.mdx) defines query groups and subscribers.

Group the changes by their `(kind, action, changed fields)` signature before narrowing. The work
then runs once per distinct shape, and not once per changed node.

Set the failure policy to widen, never skip. Every signal that cannot be narrowed safely selects
the whole target kind instead, and the pass logs it.

Treat the pass and the origin filter as one unit. Both per-node trigger types
(`computed_attribute/models.py::ComputedAttrPythonTriggerDefinition` and
`::ComputedAttrPythonQueryTriggerDefinition`) match the live mutation origin, the way
[ADR 0016](0016-node-mutation-origin-label-suppression.md) already had the other three families
match it. Neither half works alone: the filter without the
pass leaves a replayed change unrecomputed, and the pass without the filter recomputes it twice.

A merge that changes the schema also starts the schema-scoped backfill, which refreshes whole
kinds. Keep the pairs it selects in the pass all the same. The backfill is a separate flow with no
retry, and the pass cannot see its outcome, so the pass must not depend on it. The overlap costs
the pass its own submissions for those attributes, on that merge only.

The selection rules that follow from these decisions, and the failure ladder that applies the
widening, are written in `dev/knowledge/backend/merge-recompute.md`.

## Consequences

### Positive

- The replay cost stops tracking the change size. A merge or a rebase now submits a few batched
  flows instead of one flow per changed node. The node sets and the stored values do not change.
- On a merge, the pass narrows what the owner trigger cannot. That trigger carries a field filter
  only when the query reads a field of its own kind. Without one, any update of that kind starts a
  recompute. For a query pinned to one object, the pass tests the changed fields against the read
  set and selects nothing when they do not overlap. A rebase is deliberately wider. It refreshes an
  updated node of the attribute's own kind whichever fields changed, because every value that node
  derived read the old base.

### Negative

Each item carries a label. **New** means this decision creates it. **Inherited** means the system
already had it. **By design** means it is the cost of the chosen fallback.

- **New.** An unpinned query widens to its whole kind on every merge or rebase that changes a kind
  it reads, creations included. No failure is needed for this. A query that any number of objects
  can answer has no narrower answer, because membership records the last read and not the next.
- **New.** A merge that also changes the schema recomputes on both sides. The pass submits for each
  affected attribute, and the backfill refreshes the whole kind of each pair its own scope selects.
  A pair the pass widens gets a whole-kind recompute from both sides.
- **New.** The subscriber lookup can fail. This is the only family in the pass that reads the
  database and the API client. It therefore fails in ways the three schema-derived families cannot.
- **New.** A branch that declares a Python attribute waits for its workers to agree on the schema.
  The pass pays that wait once per resolution of a non-empty change set. A chain level that wrote
  nothing never pays it.
- **By design.** A widened run recomputes a whole kind. That is far more work than the change
  caused. On a large kind it costs as much as the per-node path this pass replaces.
- **Inherited.** A separate flow refreshes a node's query group, so the reverse index can lag the
  value. Any path that reaches a node through it has a window where a change is lost rather than
  late. The per-node path reads the same index.
- **Inherited.** The schema-scoped backfill stamps its whole-kind writes with the live origin, so
  on a schema-changing merge they re-enter the per-node paths. The filter removes the other echo
  loops but not this one.

### Neutral

- The run count is a step function of the submission chunk size, not a count of changed nodes. A
  change set that crosses a chunk boundary adds one run.

## Alternatives Considered

### Declaring the transform read set in the schema

Rejected. A declared read set would make the dependency a schema fact. The Python family could then
share the derivation the other three use. But the GraphQL query is what actually runs, so a
declaration beside it is a second copy that drifts from it. A drifted declaration under-recomputes,
and nothing would detect the drift. Reading the query the transform runs keeps one source of truth.

### A schema-only shortcut for owner changes

Rejected. The attribute's own kind is in the schema, so an owner change could be selected without
reading anything. But a Python transform recomputes through a task worker, a git worktree and a
transform run, where the Jinja2 families render in process. Selecting every changed owner node
would run a transform per changed node, on a path that runs none today once the readers resolve.

### Resolving widened targets in the submitter

Rejected. The submitter logs and skips a submission it cannot make, so one failure does not drop
the rest of the pass. Widening there would turn widen-on-failure into skip-on-failure. That is the
one outcome the policy forbids. Widening belongs in the resolver, where a failure can still produce
a target.

### Silencing the per-node automations without teaching the pass about Python

Rejected. The filter stops the replay, but nothing would then recompute a replayed change. It also
loses chained values. The coalesced writes of the other families carry the recompute origin, and
only the missing filter let them re-enter the Python automations.

### Dropping the family when its resolution fails

Rejected. This was safe only while the per-node automations still answered a replay. Once they
match the live origin, nothing else refreshes those values. A dropped family is then a stale value
with no later repair. Every declared attribute widens instead.

### Keeping the landing switch as a supported setting

Rejected. One setting turned the pass and the origin filter on and off together. That is the right
way to land the work, and to roll it back in one step during review. As a shipped setting it is two
code paths to maintain and a deprecation cycle to honour. One wrong value also reopens the fan-out
on a running instance. The rollback is instead a code revert plus an automation reconcile
(`infrahub upgrade`), because the filter is stored in the Prefect automation.

### Matching the owner automation on creations only

Deferred. An owner update can fire both the owner trigger and the query-group trigger for its own
kind. That needs the query to read a field of that kind, and the update to touch that field.
Matching creations only would remove the duplicate. It would also leave the owner trigger covering
creations alone, and the two kinds of update it drops today fare differently. An update to a field
the query reads would go through the query-group reverse index. That index can lag the value, which
opens a window where an update is lost rather than late. An update to any other field would lose
its path altogether. No query-group trigger is built for a kind the query reads no field from. The
owner trigger submits by node id and has neither problem, so it keeps matching updates until that
lag is closed.
