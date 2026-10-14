# Selective Post-Merge Regeneration

> Part of: `dev/knowledge/backend/` | Related: [merge-recompute.md](merge-recompute.md), [code-generation.md](code-generation.md), [events.md](events.md), [git-push-queue.md](git-push-queue.md)

When a branch merges, the follow-up re-runs generators and regenerates artifacts. The blanket behavior ran every Generator and regenerated every artifact for every member regardless of what the merge changed, which on a real dataset spawned thousands of tasks. This path narrows that work to the definitions and members the merge actually affected. The guiding rule is that over-execution is acceptable but under-execution is not: whenever the affected set cannot be determined with confidence, the path regenerates everything for that merge.

This covers generator definitions and artifact definitions. Jinja2 computed attributes, display labels, human-friendly ids and Python-transform computed attributes take the separate coalesced path in [merge-recompute.md](merge-recompute.md); profile refresh is not part of either.

The behavior is gated by `selective_execution_after_merge` (env `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`), enabled by default. Disabling it restores the blanket path. The barrier of [Held regeneration](#held-regeneration) still applies on that path: the regeneration of a repository whose merges wait for their push is held.

## The flow

```text
merge (BranchMergeOrchestrator.merge)
  -> serialize the in-memory enriched branch_diff -> list[NodeDiff]  (before the diff is frozen)
  -> after the MERGED transition + write-block lift: cache the summary under the merge key
  -> run_follow_ups threads merge_diff_cache_key + proposed_change_id to post_process_branch_merge
       -> PostMergeRegenerationDispatcher.dispatch(target_branch, merge_diff_cache_key)
            -> flag off / no key / summary unavailable -> blanket regeneration (blanket triggers)
                 -> RegenerationBarrier.hold_widen: a marker under each pending repository, which the triggers exclude
            -> RegenerationPlanner.build_plan(diff_summary, target_branch)  -> generator runs + artifact generates
            -> _dispatch_plan(plan)
                 -> RegenerationBarrier.admit: hold the requests of pending repositories, dispatch the rest
```

Every uncertain signal short-circuits to `submit_blanket_regeneration`, which submits the two `TRIGGER_*` workflows. With no repository waiting for a push, they get the parameters of the blanket behavior. Each repository with pending pushes gets a `widen` marker instead and is passed in `exclude_repository_ids`. The dispatcher builds nothing that can leave an affected definition unselected without falling back.

## Selection

`RegenerationPlanner` (`selective_regen/orchestrator.py`, `MergeSelectiveRegeneration`) turns a `list[NodeDiff]` summary into a plan of generator runs and artifact generations. It loads the generator and artifact definitions on the **target (destination) branch**, then runs each through a definition selector.

The selectors live in `selective_regen/definition_selector/`. The shared loop in `base.py` applies, per definition:

- The **gate** (`gate.py`): the definition is selected when the diff changed its query, the definition node itself (including its `fingerprint` element), a data kind its query reads, or its target group membership.
- The **member reconciliation** (`impacted.py`, `core/regeneration/members.py`): live group members are fetched on the target branch, impacted subscriber ids are mapped to member ids, new members without a subscriber are force-rendered, and the result is emitted as a member-id filter.
  - Narrowing to specific subscribers requires the query to target unique nodes (`QueryImpactClassifier`, `core/regeneration/impact_classifier.py`). A change on a root kind maps straight to its members. A change on a kind read through a relationship is mapped back to the owning members by walking the relationship chains that reach it: the query's read surface reconstructs those chains (`relationship_reached_paths_by_kind` / `ReachedPathResolver`, `graphql/analyzer.py`), and each hop is resolved to the owners referencing the changed nodes until the chain ends at the root members (`ReachedMemberResolver`, `core/regeneration/impact.py`). Every hop returns a superset of the truly-related nodes, so the resolved member set is a superset — over-execution, never under.
  - For uniquely-targeted queries without an unscopable derived read, a relationship-reached change widens to every member when its chain cannot be pinned: a hop along it is an inline/named-fragment refinement rather than a relationship on its owner, or the kind is read **both** at a root and through a relationship. In the both-read case the two read paths are indistinguishable once a change is in hand, so narrowing would drop the members reached only by the relationship; the decision keys on `traversed_kinds` for this reason.
  - A read of a `display_label` or `human_friendly_id` is imprecise: the value can be composed from a peer's attribute the read set never names, so a change to that peer moves the value without touching any kind the query reads. Each such read's declared paths are followed to the kind that owns the backing attribute, and the relationship chain from that peer back to the reading member is reported (`DerivedFieldDependencyResolver` / `DerivedPathResolver`, `core/regeneration/derived_dependencies.py` / `core/schema/derived_path.py`). `QueryClassifierBuilder` (`classifier_builder.py`) folds each resolved peer into the classifier as a traversed kind carrying that chain, so a peer change narrows like any relationship-reached change; when the reading kind is itself relationship-reached, the peer chain is extended through that kind's own chains to the root. A cross-kind derived read that cannot be resolved to a peer chain — no declared path, a peer already read at a root, or an unresolvable segment — sets `depends_on_everything`, and any real change on the query branch then widens; a path scoped to the reading kind's own attributes is already covered by that kind's read set and does not widen.
  - A field the query filters on counts as a read field (`filtered_fields_by_kind`, `graphql/analyzer.py`, folded in by `QueryClassifierBuilder`): an argument such as `owner__name__value` selects on the `owner` relationship, and a change to it moves which objects answer the query even though the query never reads it back. `any__value` matches every attribute of the kind, `display_label__value` selects on `display_label` and `hfid` on `human_friendly_id`, so the last two are handled like reads of those derived fields. Arguments that select on no field (`ids`, pagination) are left out.
  - Only entries marked `unchanged` are skipped, at the node and the element level: a diff carries nodes purely as hierarchical context, and hangs an unchanged parent relationship off nodes that did change. A `removed` node stays selected — whatever read it is now stale, so dropping it would under-execute.
  - The outcome is a single `TargetSelection` whose `ids` are always complete; `widening` records only why narrowing was abandoned (target uniqueness not guaranteed, a change on a kind reached through a relationship, or an unscopable `human_friendly_id`/`display_label` read), for the diagnostic line. The caller supplies the set to fall back to, so an empty `ids` unambiguously means *nothing to process* and can never stand for *everything*.
- The **untrusted-closure fallback** (`fallbacks.py`): a definition with a null or incomplete dependency closure is selected for all its members rather than narrowed. A repository holding any definition with no computed fingerprint is escalated so every definition of that repository regenerates (`repositories_forcing_full_regeneration`).

The predicates and member helpers in `core/regeneration/` are shared with the proposed-change pipeline; the merge path passes a resolved summary and an explicit query branch so both callers run one implementation.

### Narrowed passes must not draw conclusions from absence

Artifact generation also deletes artifacts whose target has left the target group. That conclusion is drawn from a member's *absence*, so it only holds for a pass that examined every member. `RequestArtifactDefinitionGenerate.evaluates_every_member` (`git/models.py`) is the gate: it is true only when neither filter is set. Reading `limit` alone would call a `members`-scoped pass complete, because such a pass leaves `limit` empty — and the cleanup would then delete artifacts it never re-evaluated.

The two filters are a conjunction and key on different things: `members` on the member node id, so a member with no artifact yet is still selected; `limit` on the existing artifact id, so it can only narrow to members that already have one. No caller sets both, and consolidation clears either filter as soon as one side of a merge left it empty.

The dependency closure and `fingerprint` are computed at repository import. The closure is trusted (`dependencies_complete = true`) or not; see [code-generation.md](code-generation.md) and the [proposed changes overview](../../../docs/docs/proposed-changes/overview.mdx) for how a closure is built (Python: the entry file alone, since imports are not analyzed; Jinja2: the static include/import/extends graph) and how `watch.files` restores a trusted closure. Note that `PythonClosure` reads nothing off disk and never reports `complete = false` itself, so a correctly configured Python definition lands on `complete = true` and the commit-id fold in the fingerprint is its only safety net. `complete = false` is reachable for Python only through the aggregator's failure isolation, from an unusable `file_path` or a `watch.files` entry git cannot enumerate (a pathspec escaping the repository raises `GitCommandError`). Both are misconfiguration, so the untrusted-closure fallback does not fire for a Python definition in normal operation. This asymmetry is the reason the user-facing docs describe the undeclared-`watch` case as a fallback without attributing it to `dependencies_complete`.

## The generator-to-artifact cascade

Generators dispatched by the follow-up write their output after the merge diff was captured, so those writes are absent from that diff. On a merge that runs at least one generator, `_dispatch_plan` (`regeneration_dispatcher.py`):

1. Awaits each generator run so its writes have landed, isolating failures per generator (one failure does not abort the others or discard the narrowing already computed).
2. Captures the nodes those generators wrote, scoped to the members each generator tracks, through `GeneratorTrackingGroupDiffCapturer` (`generator_output.py`). The capturer reads each generator's per-member tracking group rather than the whole branch timeframe.
3. Selects only the artifacts that read the captured output (`RegenerationPlanner.reselect_from_cascade_output`), and dispatches those alongside the merge-diff artifacts. Requests selected by both are consolidated into one request per artifact definition (member and limit filters unioned; an empty filter, meaning all members, subsumes a specific one).

The capture widens to regenerating every artifact when any generator's tracked set is unresolved or the output cannot be captured. A generator run failure regenerates every artifact without re-running the generators (which would fail the same way). The merge-diff artifacts are dispatched only after the generator-output capture, so the capture never selects on their own writes.

A proposed-change merge already reflects generator output in its branch diff, so it keeps the plain selective artifact path; the cascade is the direct-merge case, distinguished by `proposed_change_id`.

## Held regeneration

The regeneration of a repository whose merges wait for their push to the remote would read the commit recorded before the merge, and nothing would run it again after the push. So on the default branch every dispatch of a merge passes the barrier first (`core/merge/regeneration_barrier.py`): a selective dispatch through `RegenerationBarrier.admit`, a full regeneration through `RegenerationBarrier.hold_widen`. [Git Push Queue](git-push-queue.md#the-regeneration-barrier-and-the-release) describes when the barrier holds and how it fails open.

- A generator run or an artifact generation whose definition a repository with pending pushes owns is held in the push state of that repository, under the next hold sequence. The rest is dispatched at once. A repeated hold of one definition joins the two narrowings, with the `consolidate` rule of the selector of its kind.
- The barrier keeps the narrowed request of each hold in the cache (`NarrowedHoldCache`) for `NARROWED_HOLD_TTL_SECONDS`, which covers a whole automatic retry chain at its time limits plus ten minutes. A request above `NARROWED_HOLD_MAX_BYTES` is not kept.
- A blanket regeneration holds a `widen` marker of scope `all` under each pending repository, with the reason of the fallback, and excludes those repositories from the blanket runs. A failed generator run of the cascade, or a failed targeting of the terminals, holds a marker of scope `terminals` the same way.
- In the cascade, only the artifacts reselected from the generator output pass the barrier after the generators ran: the terminals of the plan passed it already.

The two trigger flows, `generate_artifact_definition` and `run_generator_definition`, take `exclude_repository_ids` and `include_repository_ids`, and skip a definition whose repository the lists do not allow. An empty or missing list allows every repository, and the dispatcher does not send an empty list, so a run with no filter keeps the parameters of a blanket run.

The release (`core/merge/regeneration_release.py::HeldRegenerationReleaser`) runs after a delivery or an abandonment, under a release lease that each step and a 5-minute timer renew, and dispatches the held items once:

- Each held item gets its request from its definition as it is now, because the import of the delivery can change the definition. Only the narrowing (`members` and `limit` for an artifact, `target_members` for a generator) comes from the cache. A cache miss regenerates every member.
- It dispatches the requests as a merge plan (`dispatch_requests`), so the generator cascade runs and each dispatch passes the barrier with the released repository admitted. An artifact of another repository that reads the released generator output is reselected and regenerated too, unless that repository has pending pushes itself: then it is held.
- A marker of scope `all` regenerates every definition of the repository (`include_repository_ids`), and the release logs the reason that the marker stores. A marker of scope `terminals` regenerates every artifact definition of the repository.
- A held definition that no longer exists widens the release to every definition of the repository (`HELD_SET_UNRESOLVED`). A held generator that exists but no longer runs after a merge counts as resolved: the release logs it and runs nothing for it.
- A generator run that fails during a release falls back to the terminals of the released repository only. A run that the orchestrator cannot start or follow raises, so the items stay held for the next release.

The push state stores the reason of a marker by its member name, so never rename a member of `FullRegenerationReason`.

## Known limitation: content composition

A composite artifact that inlines another artifact's content is **not** refreshed when a merge changes the upstream artifact. The composite keeps the stale inlined section until something else regenerates it.

The selection reads the merge diff and the generators' tracked output; neither carries the fact that one artifact's rendered content is embedded in another, so the composite is never selected. Blanket regeneration did refresh it, which makes this a behaviour change for content composition users now that `selective_execution_after_merge` defaults to on. Setting the flag to `false` restores the refresh along with the rest of the blanket path.

Confirmed live on the demo stack. See [performance-scenarios.md](../../specs/archive/ifc-2704-incremental-merge-regen/performance-scenarios.md) for the full scenario matrix, and [content composition](../../../docs/docs/artifacts/content-composition.mdx) for the user-facing feature.

## Fallback reasons

`FullRegenerationReason` (`core/constants/__init__.py`) names why a regeneration covers every definition, or every definition of one repository:

| Reason | Trigger |
|--------|---------|
| `FEATURE_DISABLED` | `selective_execution_after_merge` is off |
| `NO_SUMMARY_CAPTURED` | no merge-diff cache key threaded (capture failed or rolled back) |
| `SUMMARY_UNAVAILABLE` | the cached summary is missing or unreadable |
| `SELECTION_FAILED` | building or dispatching the plan raised |
| `TERMINAL_SELECTION_FAILED` | a generator run of the cascade failed, or the terminals could not be targeted from its output, so every terminal regenerates; the reason of a `terminals` marker |
| `UNHELD_FOLLOW_UP` | the merge flow queued a merge that the dispatcher could not queue, so the follow-ups ran with no hold, and the release regenerates every definition of the repository |
| `HELD_SET_UNRESOLVED` | a held definition no longer exists at the release |

`RegenerationReason` (`core/regeneration/models.py`) names why a definition was selected. These members name the widening of one definition or one repository inside a selective plan:

| Reason | Trigger |
|--------|---------|
| `MISSING_FINGERPRINT` | a repository has a definition with no computed fingerprint (whole-repository escalation) |
| `DEPENDENCIES_NULL` / `DEPENDENCIES_INCOMPLETE` | a definition's closure is untrusted (per-definition widening) |

A per-merge line records the path taken (selective, with generator/artifact counts and whether the cascade engaged, or the named fallback reason) at debug level.

## Key Files

| File | What |
|------|------|
| `core/merge/orchestrator.py` | Serialize the enriched diff and cache it after the point of no return |
| `core/diff/summary_serializer.py` | `DiffSummarySerializer` — the `EnrichedDiffRoot -> list[NodeDiff]` converter |
| `core/diff/summary_cache.py` | `DiffSummaryCache` — the merge-scoped cache |
| `core/merge/regeneration_dispatcher.py` | `PostMergeRegenerationDispatcher`, the cascade, `submit_full_regeneration` |
| `core/constants/__init__.py` | `FullRegenerationReason`, the reasons of a fallback to a full regeneration |
| `core/merge/regeneration_barrier.py` | `RegenerationBarrier`, `NarrowedHoldCache`, `OwnedRegeneration` |
| `core/merge/regeneration_release.py` | `HeldRegenerationReleaser`, `HeldDefinitionResolver` |
| `core/merge/selective_regen/orchestrator.py` | `RegenerationPlanner` / `MergeSelectiveRegeneration`, `build_merge_selective_regeneration` |
| `core/merge/selective_regen/definition_selector/` | Shared select loop (`base.py`) and the artifact / generator selectors |
| `core/merge/selective_regen/gate.py`, `impacted.py`, `fallbacks.py` | Definition gate, member impact, untrusted-closure widening |
| `core/merge/selective_regen/generator_output.py` | `GeneratorTrackingGroupDiffCapturer` (group-scoped output capture) |
| `core/regeneration/` | Predicates, member mapping, definition models shared with the proposed-change pipeline |
| `core/regeneration/derived_dependencies.py`, `classifier_builder.py`, `core/schema/derived_path.py` | Resolve a `display_label` / `human_friendly_id` read's backing peers and fold them into the classifier as traversed kinds |
| `graphql/analyzer.py` | `ReachedPathResolver` / `relationship_reached_paths_by_kind` — reconstructs the relationship chains reaching each related kind |
| `core/merge/builder.py` | `build_post_merge_regeneration_dispatcher`, `build_regeneration_barrier`, `build_held_regeneration_releaser`, `build_default_branch_barrier` |
| `core/branch/tasks.py` | `post_process_branch_merge` wiring |
| `config.py` | `selective_execution_after_merge` |

## See Also

- [Coalesced Recompute on Merge and Rebase](merge-recompute.md) - the sibling merge-followup path for computed attributes, display labels, and human-friendly ids
- [Code Generation](code-generation.md) - fingerprints and dependency closures computed at repository import
- [Events System](events.md) - node mutation events consumed by the non-coalesced regeneration paths
- Feature spec: `dev/specs/archive/ifc-2704-incremental-merge-regen/`
