# Phase 0 Research: Coalesce Python transform computed attributes on merge and rebase

**Feature**: [spec.md](./spec.md) | **Date**: 2026-08-11

Four questions blocked the design. All four are resolved. Three of them changed the specification; those changes are already applied and are called out below.

---

## R1 — Does the reader refresh survive a deleted peer?

**Decision**: It does not, and the cause is worse than assumed. Two independent failures are stacked, and the first is a hard stop. Both are fixed inside this feature.

**Findings**:

1. `ComputedAttrPythonQueryTriggerDefinition` (`backend/infrahub/computed_attribute/models.py:285-289`) subscribes to `NodeUpdatedEvent` only. Its sibling `ComputedAttrPythonTriggerDefinition` (`models.py:227`) subscribes to created and updated. **Neither has a delete leg.** So `query_transform_targets` is never reached for a deleted node, on a merge or on a live edit.
2. Even once it fires, the lookup returns nothing. `Node.delete()` runs `RelationshipDeleteAllQuery` before `NodeDeleteQuery` (`backend/infrahub/core/node/__init__.py:1236-1251`), and that query matches **every** active `IS_RELATED` edge, the `group_member` edge included (`backend/infrahub/core/query/relationship.py:1363-1366`). By the time `GATHER_GRAPHQL_QUERY_SUBSCRIBERS` runs with `members__ids: [X]`, X is no longer a member.

This is the same class of failure as IFC-2852, reached through the query group rather than a direct reverse relationship, so the fix in PR #9845 could not have covered it. That fix (commit `9306bef57`, one non-test file, `recompute_coalescing.py` +64/-18) added a **self-keyed** lookup on `UPDATED` whenever a changed field names a relationship, because the reader is never saved when its peer is deleted on another branch. The coalesced `DELETED` branch still emits only the dead reverse lookup (`recompute_coalescing.py:227-231`).

One case accidentally works today: if the delete also produces an `UPDATED` changelog on a surviving reader whose kind and field the transform's query reads, the update trigger fires for that reader and the group resolves normally. A transform whose query reads the deleted node directly has no such rescue.

**Existing coverage**: none. The only test touching `query_transform_targets` (`backend/tests/functional/computed_attributes/test_computed_attribute.py:189`) drives it after an attribute update. The delete-event assertions in `backend/tests/unit/computed_attribute/test_triggers.py:83,93` are for the transform lifecycle triggers, which is easy to mistake for coverage of this path.

**Consequence for the plan**: FR-009 is two changes, not one. Add the delete leg to the reader trigger, and resolve the subscribers as of a time before the delete. The spec's Edge Cases and Assumptions were updated to say so.

**Alternatives considered**:
- *Capture group members at delete time and pass them on the event.* Rejected for now: it widens the event payload and couples the delete path to the recompute path. Reconsider if the point-in-time lookup proves expensive.
- *Split the delete gap into its own ticket.* Rejected. It is the same reader-resolution code this feature rewrites, so splitting would mean touching it twice.

---

## R2 — Where does the async reader lookup belong?

**Decision**: A third injected collaborator between the builder and the submitter. The owner axis stays entirely inside the existing synchronous builder.

**The key finding that shrinks the work**: the two axes have completely different resolution costs.

| Axis | Resolvable from the schema alone? | Evidence |
|---|---|---|
| Which kinds own a Python computed attribute | **Yes, pure, no I/O** | `get_python_attributes_per_node()` is a dict read on the processed schema branch (`schema_branch_computed/facade.py:52` → `python_transform.py:84`) |
| Which fields feed that attribute | **No** | `TransformReadSet` is only ever built from a GraphQL query report, and the query text lives on a database node. The schema stores the transform's *name* only. |
| Which nodes read a changed node | **No, definitively I/O** | Subscriber-group membership is runtime data with no schema representation (`computed_attribute/tasks.py:660-707`) |

> **⚠️ Corrected. This paragraph was wrong and is kept for the record.**
>
> The original conclusion was: "because the invariant permits over-recompute, the owner axis can be
> added as a fourth family in the pure builder using an over-approximation, without filtering on the
> transform's read fields; only the reader axis needs I/O."
>
> That is a misreading of the invariant. Over-recompute is permitted as a *fallback when something
> cannot be determined*, not as a shortcut to avoid determining it. Today's owner-axis automation
> already filters on the transform's read fields, so dropping the filter refreshes **more** nodes
> than today. On a merge that touches only fields no transform reads it goes from zero transform
> executions to one per changed node. That violates FR-005 and would make merges slower.
>
> **Corrected conclusion**: both axes need the read-field filter, both need the same derivation, so
> both go through the resolver. This makes the design simpler, not more complex: one collaborator,
> one round of I/O, one place owning the widen-on-failure policy. See the Revision section at the
> end of this document.

**Options evaluated**:

| Option | Test churn | Verdict |
|---|---|---|
| (a) Make `build()` async, inject the resolver into the builder | 12 builder unit tests become async and gain a collaborator they do not need; 7 more constructor sites | Rejected. Destroys the one pure component in the pipeline and the documented "build step needs no database" property (`dev/knowledge/backend/merge-recompute.md:27`). Gives the builder two reasons to change. |
| (b) Builder emits unresolved markers, submitter resolves them | Lowest: about 2 submitter tests | Rejected. The submitter's failure policy is "log and skip this submission". Putting a widen-on-failure policy in that class is how FR-008 gets implemented as a skip by accident. Also breaks the pure `plan()` static method. |
| **(c) Third collaborator between build and submit** | **0 builder tests, 0 submitter tests; 3 wiring sites plus 7 mechanical constructor edits** | **Chosen.** |

The resolver has the same type in and out (`CoalescedRecompute` → `CoalescedRecompute`), so everything downstream is untouched. FR-008 falls out naturally: on a failed or imprecise lookup it returns a whole-kind `ReaderLookup` with `precise=False`, which `CoalescedRecompute.fallback_used` already surfaces for the FR-013 logging. It is the one place with a logger and a policy.

**Refinement that prevents a silent bug**: `RecomputeChainSubmitter` runs the same build-then-submit pipeline as `MergeRecomputeCoordinator` (`recompute_coalescing.py:466-467` vs `:524-525`). If the resolver is injected into only one of them, a chained Python target ships with unresolved readers, which is exactly the under-recompute FR-006 forbids and the mechanism behind acceptance scenarios 4 and 5. Rather than injecting twice, **make `RecomputeChainSubmitter` hold the coordinator** and give `MergeRecomputeCoordinator.run` a `recompute_depth` parameter. The chain submitter keeps its real responsibilities, write-to-change translation and depth bounding. Feed the depth bound explicitly instead of reaching through `self.builder.schema_branch` (`:508`), which would otherwise become a two-hop Demeter violation.

**Wiring note**: the resolver needs an SDK client. The rebase flow (`core/branch/tasks.py:332`) and `build_bulk_recompute_dispatcher` (`core/recompute/dispatch.py:76`) can both resolve one in place. `post_merge.py:177` cannot: `PostMergeDispatcher.__init__` has neither a database handle nor a client, and it constructs the coordinator internally. Per the build-near-the-entry-point rule, construct the resolver in `core/merge/builder.py` (which already resolves the workflow, event service and cache) and inject it at the `PostMergeDispatcher` construction site.

---

## R3 — How to remove the double refresh on a schema-carrying merge

**Decision**: Subtract from the **coalesced** pass, not from the schema-driven pass. This reverses the direction the specification originally stated. The spec has been corrected.

**Why the original direction was wrong**: the two passes cover different node sets for the same attribute-and-kind pair. The coalesced pass visits only the merged node ids (`ReaderLookup.source_node_ids`). The schema-driven pass visits every node of the kind (`client.all(kind=...)`, `computed_attribute/tasks.py:284`). A schema change selects a pair precisely because the way the value is computed changed, which invalidates untouched destination-branch nodes too. Dropping the schema pass because a subset of its nodes was refreshed is a stale-value bug of the IFC-2937 class that the invariant forbids. The cheapest option to build was also the most wrong.

**Chosen mechanism**: a pure function beside the existing scoper, computing the pairs a schema change certainly covers, applied as a filter on `CoalescedRecompute.targets` inside the existing `if schema_diff is not None and schema_hash is not None:` guard in `post_merge.py:137`. The `ChangedElementsPayload` is already built there (`:144`), and the schema branch is already in scope (`:176`), so this needs no new dependency and no database handle on the merge critical path.

The function implements **only** scoper rules 2 and 4, the two decidable without transform read sets:
- the owner kind appears in the added or removed kinds (guaranteed to select, because every deriver forces the owner kind into the read set, `scoping.py:213,227`)
- the attribute's own name appears in the changed fields for its kind (`scoping.py:161`)

Rules 1 and 3 are deliberately omitted. Omitting them shrinks the drop set, which is the safe direction.

**Why this is the least plumbing that cannot under-recompute**: `computed_attribute/tasks.py` is not touched at all, so the automation-reconcile duty (a single unconditional statement at `tasks.py:617`, cleanly separable from the value submissions at `:558-615`) carries no regression risk. No event schema change, no new trigger parameter, no shared marker. Everything dropped is a provable subset of what the schema pass will do on the same branch, and the drop set is empty whenever there is no schema diff.

**It also fixes Jinja2 for free**, because the coalesced `computed_attribute` family is Jinja2-only today, so the same subtraction dedups against the Jinja2 schema setup immediately and picks up Python automatically once the family is added.

**Delivery risk, encoded as FR-015**: the `SchemaUpdatedEvent` send is wrapped in a guard that swallows failures (`post_merge.py:171-173`), and it is sent *before* the coalesced pass runs. Subtract only after a successful send, otherwise a failed notification plus a dropped target equals stale data.

**Also confirmed**:
- Rebase never emits `SchemaUpdatedEvent`. Only `post_merge.py:141` and the two direct schema-load paths do. So the subtraction is merge-only. Rebase does apply schema migrations without firing the setup flow, which is a pre-existing gap and out of scope here.
- The fingerprint-lifecycle path cannot double up. Its triggers are origin-gated to live edits (`computed_attribute/triggers.py:30-35`), and merged nodes carry the merge origin.
- Display labels and HFIDs have the same double-up, because their setup flows take no changed-elements argument and appear to run unconditionally all-of-kind. Same subtraction applies with a simpler rule. Noted, not in scope.

**Alternatives considered and rejected**:
- *Detect merge origin in the schema flow and skip the value recompute.* Cheapest to build. `context.parent_event.name` already distinguishes a merge-triggered schema update from a direct load, at no plumbing cost. Rejected because it is the wrong direction and under-recomputes.
- *Write a marker the schema flow reads.* Rejected: the event is sent before the coalesced pass runs, so the marker races.
- *Let the coalesced pass own the schema case entirely.* Rejected: it needs the transform read sets, which require a database query and per-transform query analysis, on the merge critical path.

---

## R4 — Can the success criteria be measured?

**Decision**: Not with what is in this repository. The timing harness must be restored first, and that becomes the first task of the plan.

**Findings**:
- The IFC-2761 timing harness **was never merged**. It exists only on `origin/merge-recompute-profile-ifc-2761` (`backend/tests/integration_docker/test_merge_recompute_timing.py`, plus `metrics.py` and `scales.py` helpers). Only `backend/tests/helpers/merge_recompute/dataset.py` survived into `develop`, carried over by the coalescing feature commit.
- The surviving dataset builder contains no Python transform. `test_merge_recompute.py:88` explicitly drops the transform-python attribute because "it needs a transform repo".
- The harness counts three deployments only: the Jinja2, display-label and HFID update-value flows. The three Python deployments are not counted.
- IFC-2746 has **no work in flight anywhere** — no branch, no spec directory, no changelog fragment. The only mention of it in the repository is the assumption line in this feature's own spec.
- No private dataset is needed. The harness seeds synthetic data at a chosen scale. The larger reference figures quoted by earlier work live in a separate private repository and are not reproducible here.

**Restoration cost**: four steps. Check the three files out of the unmerged branch and fix import drift against the current dataset builder; add the three Python deployment names to the counted set; add a Python-transform dataset variant, which is the only genuinely new piece because a Python computed attribute needs a real git repository rather than a schema load; extend the scales and raise the drain budgets, since per-node user code is far slower than a Jinja2 render.

**Reusable inputs already in the repository**: `backend/tests/integration_docker/test_files/computed_tshirt.yml` (a schema with a transform-python computed attribute) and the fixture repository `backend/tests/fixtures/repos/computed-attributes-functional/`.

**Cheaper complementary signal for SC-001 only**: extend the existing component test that asserts one coalesced submission per family, parametrised over the changed-node count. That gives a deterministic, docker-free count in CI. It counts submissions rather than executed runs, so it cannot satisfy SC-002.

**Known weaknesses in the restored harness, to fix while restoring**: the window loop polls at two-second granularity and conflates "count rose" with "queue drained", and the total-duration figure is assigned the window value rather than a sum of run durations. Absolute seconds are container-relative; only the ratio transfers, which is why SC-002 is a ratio.

**Also corrected**: restoring the harness is a conflict resolution against a long-diverged branch, not an import fix. The deterministic counting layer that produced the published tables also never landed and should be restored first, because it is docker-free and answers SC-001 on its own.

---

## Revision: what an adversarial review changed

Three independent reviewers examined the first draft of the spec and plan. The full report is in [critiques/critique-20260811.md](./critiques/critique-20260811.md). Ten findings were material. The ones that changed a decision:

### R5 — Both axes need the read-field filter (corrects R2)

Recorded above as an inline correction to R2. The owner-axis over-approximation was the worst decision in the first draft: it violated the spec's own requirement and would have made merges slower on the most common shape, while every success criterion still reported success, because they all counted jobs and none counted transform executions.

The knock-on is that the resolver now covers both axes, which collapses two designs into one. The read-field index it needs is derived from the stored query text once per pass. It is deliberately not cached: a stale cache silently widens or misses, and one derivation is cheap against the work it scopes.

### R6 — A widened target must be representable, or it silently vanishes

The first draft assumed the whole-kind fallback needed no type change. It does. The planner chunks a node id set, and an empty set yields zero chunks, therefore zero submissions. A widened target built on an empty set would disappear rather than widen — the fallback implemented as a skip. FR-010 and an explicit whole-kind marker exist to pin this.

### R7 — The resolver must never propagate an exception

The coalesced pass runs inside a guard that swallows everything. Today that is harmless, because the per-node triggers still run. After suppression, one escaping resolver error means **every** derived value on that merge is silently stale, across all four families, with one log line. The resolver must catch internally and widen.

### R8 — Point-in-time resolution applies to deleted nodes only

The first draft required every lookup to resolve at a pre-merge timestamp, to see through the closed membership records of deleted nodes. That would hide memberships the merge itself created, which is a different under-recompute. Resolve created and updated ids at current time, deleted ids at the earlier time, union the results.

### Smaller corrections, all folded into the spec and plan

- The self and cross choice becomes per family. The builder skips self-targets on update because the three existing families recompute inline on save; Python transforms do not, so the owner axis would be dropped on every update.
- `process_transform` has no depth parameter and ignores the target kind it is handed, so a coalesced submission would be a silent no-op.
- Whether a write is coalesced must be stated explicitly. Three callers pass id lists and only one is coalesced, so the inference used for the Jinja2 family is unsafe here.
- SC-001 was unreachable as written, because submissions are chunked. Restated in terms of the chunk limit.
- SC-004 (transform execution count) and SC-007 (a fail criterion with a number) were added. The first draft had no criterion that could fail and no rollback trigger.
- A feature switch was added. The first draft claimed reverting two trigger changes would restore today's behaviour; it would not, because the coalesced family would still run, giving a double refresh.
- The suppression test was placed at a tier that cannot observe trigger matching. It needs a flow-run count assertion at the full-stack tier.
- The subscriber query already exists in two copies; a third consumer in `core/merge/` would close an import loop. Extract it to a dependency-free module.

### What survived

The R3 reversal. A reviewer tasked specifically with refuting it confirmed the direction, with two wording corrections now applied: the schema-coverage set is *expected*, not *certain*, and FR-018 must cover the schema flow failing **after** a successful send, not just the send failing. Every code claim in R1 through R4 that was independently checked held up.

## R5 — What US2 actually needs (found while starting T045)

Three findings from reading the delete path. They change the shape of US2, so they are recorded before the work starts.

**The field filter does match a delete.** `Node.delete` builds a changelog and calls `add_attribute` for every attribute it removes, including the display label and the human-friendly id. `NodeMutatedEvent.get_related` therefore emits one `infrahub.node.attribute_update` entry per deleted attribute, each carrying `infrahub.field.name`. Adding `NodeDeletedEvent` to `ComputedAttrPythonQueryTriggerDefinition` is enough for the trigger itself to fire. This was the open question in T045.

**T045 is useless without T046, on the live path too.** The trigger firing only gets as far as `query_transform_targets`, which resolves subscribers at the current time. A deleted node's group edges are already closed, so the lookup finds nothing and the flow does nothing. The live delete leg therefore needs its own point-in-time resolution, not only the merge path that T046 covers. The timestamp has to reach the flow as a trigger parameter (the event's `occurred`), which makes T045 a change to the flow signature as well as to the trigger.

**A kind-level dependency cannot be reached at all today, in either direction.** When a transform reaches a kind but reads no field from it, `update_fields` is empty and the reader trigger still sets `match_related["infrahub.field.name"] = []`. Note the owner-axis builder guards this with `if update_fields:` and the reader-axis one does not. The two directions fail differently:

- *Creation*: unreachable by construction, not by a bug. A new node belongs to no query group until a transform runs for it, so no reverse lookup can find its readers. The coalesced pass has the same limit, which is why the builder keeps the Python reader axis off for a creation.
- *Deletion*: reachable in principle, since the node was a member, but only with the point-in-time lookup above.

Fixing the empty-filter case is not just deleting the guard: dropping the filter would make the trigger match every update of the kind, and an update on a kind with no read fields must not select (see `selects_change`). The correct shape is a separate trigger leg carrying the delete only, with no field filter. Size US2 with that in mind.
