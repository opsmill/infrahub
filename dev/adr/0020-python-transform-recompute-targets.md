# 20. Python transform targets from analyzed queries and query-group subscribers

**Status:** Accepted
**Date:** 2026-09-28
**Author:** @opsmill-team

## Context

ADR 0017 replaced the per-node recompute fan-out of merge and rebase with one coalesced pass. It
covered three families: Jinja2 computed attributes, display labels, and human-friendly ids. All
three share one property. What each value reads, and which nodes read a given node, are schema
facts. The builder derives them from the schema branch it already holds, and reads no database.

Python transform computed attributes have neither fact in the schema. What a transform reads is
known only from its GraphQL query. Which nodes read a given node is known only from the query
groups those nodes subscribed to on their last successful compute. Both are runtime database facts.
So the family stayed outside the pass, and its two per-node trigger types kept matching every
mutation origin.

A merge or a rebase replays each changed node as an event. That replay started one recompute flow
per changed node. Each flow paid its own transform-metadata query, repository resolution and
per-node data query, to write a value the merge had already carried over. Two further loops ran on
top. The coalesced writes of the other three families re-fired the Python automations. The Python
writes carried the live origin back into the per-node paths of every family.

The cost tracks the size of the change set, not the number of readers. The replays were measured on
two datasets of very different size. They dropped by roughly twenty times on a multi-site network,
and by two orders of magnitude on a data-centre fabric. The unique node sets and the stored values
were identical on both. The bigger the change, the bigger the drop, because the new count follows
the submission chunk size and not the node count. The git-commit channel is separate and does not
change.

## Decision

Add the Python family to the coalesced pass, and derive it behind an interface
(`core/merge/recompute_coalescing.py::PythonTargetResolver`). The narrowing then needs no database
or client import of its own. Two runtime sources feed that interface. The analyzed transform
queries say what each attribute reads. The query-group subscriber index says which nodes read a
given node.

Group the changes by their `(kind, action, changed fields)` signature before narrowing. The work
then runs once per distinct shape, and not once per changed node.

Set the failure policy to widen, never skip. Every signal that cannot be narrowed safely selects
the whole target kind instead, and the pass logs it.

Treat the pass and the origin filter as one unit. Both per-node trigger types
(`computed_attribute/models.py::ComputedAttrPythonTriggerDefinition` and
`::ComputedAttrPythonQueryTriggerDefinition`) match the live mutation origin, the way ADR 0016
already had the other three families match it. The filter without the pass leaves a replayed change
unrecomputed. The pass without the filter recomputes it twice.

A merge that changes the schema also starts the schema-scoped backfill, which refreshes whole
kinds. Keep the pairs it selects in the pass all the same. The backfill is a separate flow with no
retry, and the pass cannot see its outcome, so the pass must not depend on it. The overlap costs one
extra batched submission per affected attribute, only on a merge that also changes the schema.

The selection rules that follow from these decisions, and the failure ladder that applies the
widening, are written in `dev/knowledge/backend/merge-recompute.md`.

## Consequences

### Positive

- The replay cost stops tracking the change size. A merge or a rebase now submits a few batched
  flows instead of one flow per changed node. The node sets and the stored values do not change.
- The pass narrows the owner axis, which the per-node path cannot. The owner trigger carries a
  field filter only when the query reads a field of its own kind. Without one, any update of that
  kind starts a recompute. The pass tests the changed fields against the read set, and selects
  nothing when they do not overlap.

### Negative

Each item carries a label. **New** means this decision creates it. **Inherited** means the system
already had it. **By design** means it is the cost of the chosen fallback.

- **New.** A merge that also changes the schema recomputes on both sides. The pass submits for each
  affected attribute, and the backfill refreshes the whole kind of each pair its own scope selects.
  A pair the pass widens gets a whole-kind recompute from both sides.
- **New.** The subscriber lookup can fail. This is the only family in the pass that reads the
  database and the API client. It therefore fails in ways the three schema-derived families cannot.
- **New.** A branch that declares a Python attribute waits for its workers to agree on the schema.
  The pass pays that wait on every flow run that builds a resolver, including each level of a
  chain.
- **By design.** A widened run recomputes a whole kind. That is far more work than the change
  caused. On a large kind it costs as much as the per-node path this pass replaces.
- **Inherited.** The reverse index can lag the value. A node's query group is refreshed by a
  separate flow. That flow is dispatched during the compute and completes independently of the
  value write. Any path that reaches a node through the index has a window where a change is lost
  rather than late. The per-node path reads the same index.
- **Inherited.** Each recompute upserts one query group per node it reads. Both paths read once
  per node, so the count does not change. During the upgrade that first stores the filter both run,
  and the count is about 2N.

### Neutral

- The run count is a step function of the submission chunk size, not a count of changed nodes. A
  change set that crosses a chunk boundary adds one run. Compare the unique node ids between
  versions, not the run counts.

## Alternatives Considered

### Declaring the transform read set in the schema

Rejected. A declared read set would make the dependency a schema fact. The Python family could then
share the derivation the other three use. But the GraphQL query is what actually runs, so a
declaration beside it is a second copy that drifts from it. A drifted declaration under-recomputes,
and nothing would detect the drift. Reading the query the transform runs keeps one source of truth.

### A schema-only shortcut on the owner axis

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
only the missing filter let them re-enter the Python automations. The coverage lands before the
filter, never after.

### Dropping the family when its resolution fails

Rejected. This was safe only while the per-node automations still answered a replay. Once they
match the live origin, nothing else refreshes those values. A dropped family is then a stale value
with no later repair. Every declared attribute widens instead.

### Keeping the landing switch as a supported setting

Rejected. One setting turned the pass and the origin filter on and off together. That is the right
way to land the work, and to roll it back in one step during review. As a shipped setting it is two
code paths to maintain and a deprecation cycle to honour. One wrong value also reopens the fan-out
on a running instance. The setting was removed before the release that ships the pass. The rollback
is now a code revert plus an automation reconcile (`infrahub upgrade`), because the filter is
stored in the Prefect automation.

### Matching the owner automation on creations only

Rejected. An owner update fires both the owner automation and the owner-kind query automation, so
matching creations only would remove the duplicate. It would also route every owner update through
the query-group reverse index, which can lag the value it indexes. An update that lands in that
window would be lost rather than late. The owner automation submits by node id and has no such
window, so it keeps matching updates until that lag is closed.
