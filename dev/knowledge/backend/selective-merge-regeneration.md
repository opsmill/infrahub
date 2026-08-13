# Selective Post-Merge Regeneration

> Part of: `dev/knowledge/backend/` | Related: [merge-recompute.md](merge-recompute.md), [code-generation.md](code-generation.md), [events.md](events.md)

When a branch merges, the follow-up re-runs generators and regenerates artifacts. The blanket behavior ran every Generator and regenerated every artifact for every member regardless of what the merge changed, which on a real dataset spawned thousands of tasks. This path narrows that work to the definitions and members the merge actually affected. The guiding rule is that over-execution is acceptable but under-execution is not: whenever the affected set cannot be determined with confidence, the path regenerates everything for that merge.

This covers generator definitions and artifact definitions. Jinja2 computed attributes, display labels, and human-friendly ids take the separate coalesced path in [merge-recompute.md](merge-recompute.md); Python-transform computed attributes and profile refresh are not part of either.

The behavior is gated by `selective_execution_after_merge` (env `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`), enabled by default. Disabling it restores the blanket path exactly.

## The flow

```text
merge (BranchMergeOrchestrator.merge)
  -> serialize the in-memory enriched branch_diff -> list[NodeDiff]  (before the diff is frozen)
  -> after the MERGED transition + write-block lift: cache the summary under the merge key
  -> run_follow_ups threads merge_diff_cache_key + proposed_change_id to post_process_branch_merge
       -> PostMergeRegenerationDispatcher.dispatch(target_branch, merge_diff_cache_key)
            -> flag off / no key / summary unavailable -> full regeneration (blanket triggers)
            -> RegenerationSelector.build_plan(diff_summary, target_branch)  -> generator runs + artifact generates
            -> _dispatch_plan(plan)
```

Every uncertain signal short-circuits to `submit_full_regeneration` (the two `TRIGGER_*` workflows), which is the byte-for-byte blanket behavior. The dispatcher builds nothing that can leave an affected definition unselected without falling back.

## Selection

`RegenerationSelector` (`selective_regen/orchestrator.py`, `MergeSelectiveRegeneration`) turns a `list[NodeDiff]` summary into a plan of generator runs and artifact generations. It loads the generator and artifact definitions on the **target (destination) branch**, then runs each through a definition selector.

The selectors live in `selective_regen/definition_selector/`. The shared loop in `base.py` applies, per definition:

- The **gate** (`gate.py`): the definition is selected when the diff changed its query, the definition node itself (including its `fingerprint` element), a data kind its query reads, or its target group membership.
- The **member reconciliation** (`impacted.py`, `core/regeneration/members.py`): live group members are fetched on the target branch, impacted subscriber ids are mapped to member ids, new members without a subscriber are force-rendered, and the result is emitted as a member-id filter.
  - Narrowing to specific subscribers requires the query to target unique nodes **and** no relevant change to land on a kind the query reaches through a relationship (`QueryImpactClassifier`, `core/regeneration/impact_classifier.py`). Unique targeting is a guarantee about the root only, and a node read through a relationship is never tracked as a query-group member, so it cannot be mapped back to a subscriber by membership lookup. Those changes widen to every member rather than narrowing to none.
  - A kind read **both** at a root and through a relationship counts as traversed. The requested-read map keys by kind alone, so the two read paths collapse into one entry and a change of that kind cannot be attributed to either; treating it as mappable would narrow away the members reached only by the relationship. This is why the decision keys on `traversed_kinds` rather than on the query's root kinds.
  - Only entries marked `unchanged` are skipped, at the node and the element level: a diff carries nodes purely as hierarchical context, and hangs an unchanged parent relationship off nodes that did change. A `removed` node stays selected — whatever read it is now stale, so dropping it would under-execute.
  - The outcome is a single `TargetSelection` whose `ids` are always complete; `widened` records only whether narrowing was abandoned, for the diagnostic line. The caller supplies the set to fall back to, so an empty `ids` unambiguously means *nothing to process* and can never stand for *everything*.
- The **untrusted-closure fallback** (`fallbacks.py`): a definition with a null or incomplete dependency closure is selected for all its members rather than narrowed. A repository holding any definition with no computed fingerprint is escalated so every definition of that repository regenerates (`repositories_forcing_full_regeneration`).

The predicates and member helpers in `core/regeneration/` are shared with the proposed-change pipeline; the merge path passes a resolved summary and an explicit query branch so both callers run one implementation.

### Narrowed passes must not draw conclusions from absence

Artifact generation also deletes artifacts whose target has left the target group. That conclusion is drawn from a member's *absence*, so it only holds for a pass that examined every member. `RequestArtifactDefinitionGenerate.evaluates_every_member` (`git/models.py`) is the gate: it is true only when neither filter is set. Reading `limit` alone would call a `members`-scoped pass complete, because such a pass leaves `limit` empty — and the cleanup would then delete artifacts it never re-evaluated.

The two filters are a conjunction and key on different things: `members` on the member node id, so a member with no artifact yet is still selected; `limit` on the existing artifact id, so it can only narrow to members that already have one. No caller sets both, and consolidation clears either filter as soon as one side of a merge left it empty.

The dependency closure and `fingerprint` are computed at repository import. The closure is trusted (`dependencies_complete = true`) or not; see [code-generation.md](code-generation.md) and the [proposed changes overview](../../../docs/docs/proposed-changes/overview.mdx) for how a closure is built (Python: the entry file alone, since imports are not analyzed; Jinja2: the static include/import/extends graph) and how `watch.files` restores a trusted closure. Note that naming a Python entry file reads nothing off disk, so a Python source that declares no `watch` always lands on `complete = true` and the commit-id fold in the fingerprint is its only safety net. Two things can still isolate a Python definition to `complete = false`, both through the aggregator's failure isolation: an unusable `file_path`, and a `watch.files` entry git cannot enumerate (a pathspec escaping the repository raises `GitCommandError`). The untrusted-closure fallback is therefore unreachable for an undeclared Python source and reachable only through a broken declaration.

## The generator-to-artifact cascade

Generators dispatched by the follow-up write their output after the merge diff was captured, so those writes are absent from that diff. On a merge that runs at least one generator, `_dispatch_plan` (`regeneration_dispatcher.py`):

1. Awaits each generator run so its writes have landed, isolating failures per generator (one failure does not abort the others or discard the narrowing already computed).
2. Captures the nodes those generators wrote, scoped to the members each generator tracks, through `GeneratorTrackingGroupDiffCapturer` (`generator_diff_capturer.py`). The capturer reads each generator's per-member tracking group rather than the whole branch timeframe.
3. Selects only the artifacts that read the captured output (`RegenerationSelector.select_artifacts`), and dispatches those alongside the merge-diff artifacts. Requests selected by both are consolidated into one request per artifact definition (member and limit filters unioned; an empty filter, meaning all members, subsumes a specific one).

The capture widens to regenerating every artifact when any generator's tracked set is unresolved or the output cannot be captured. A generator run failure regenerates every artifact without re-running the generators (which would fail the same way). The merge-diff artifacts are dispatched only after the generator-output capture, so the capture never selects on their own writes.

A proposed-change merge already reflects generator output in its branch diff, so it keeps the plain selective artifact path; the cascade is the direct-merge case, distinguished by `proposed_change_id`.

## Known limitation: content composition

A composite artifact that inlines another artifact's content is **not** refreshed when a merge changes the upstream artifact. The composite keeps the stale inlined section until something else regenerates it.

The selection reads the merge diff and the generators' tracked output; neither carries the fact that one artifact's rendered content is embedded in another, so the composite is never selected. Blanket regeneration did refresh it, which makes this a behaviour change for content composition users now that `selective_execution_after_merge` defaults to on. Setting the flag to `false` restores the refresh along with the rest of the blanket path.

Confirmed live on the demo stack. See [performance-scenarios.md](../../specs/archive/ifc-2704-incremental-merge-regen/performance-scenarios.md) for the full scenario matrix, and [content composition](../../../docs/docs/artifacts/content-composition.mdx) for the user-facing feature.

## Fallback reasons

| Reason | Trigger |
|--------|---------|
| `FEATURE_DISABLED` | `selective_execution_after_merge` is off |
| `NO_SUMMARY_CAPTURED` | no merge-diff cache key threaded (capture failed or rolled back) |
| `SUMMARY_UNAVAILABLE` | the cached summary is missing or unreadable |
| `SELECTION_FAILED` | building or dispatching the plan raised |
| `MISSING_FINGERPRINT` | a repository has a definition with no computed fingerprint (whole-repository escalation) |
| `DEPENDENCIES_NULL` / `DEPENDENCIES_INCOMPLETE` | a definition's closure is untrusted (per-definition widening) |

A per-merge line records the path taken (selective, with generator/artifact counts and whether the cascade engaged, or the named fallback reason) at debug level.

## Key Files

| File | What |
|------|------|
| `core/merge/orchestrator.py` | Serialize the enriched diff and cache it after the point of no return |
| `core/diff/summary_serializer.py` | `DiffSummarySerializer` — the `EnrichedDiffRoot -> list[NodeDiff]` converter |
| `core/diff/summary_cache.py` | `DiffSummaryCache` — the merge-scoped cache |
| `core/merge/regeneration_dispatcher.py` | `PostMergeRegenerationDispatcher`, the cascade, `submit_full_regeneration`, `FullRegenerationReason` |
| `core/merge/selective_regen/orchestrator.py` | `RegenerationSelector` / `MergeSelectiveRegeneration`, `build_merge_selective_regeneration` |
| `core/merge/selective_regen/definition_selector/` | Shared select loop (`base.py`) and the artifact / generator selectors |
| `core/merge/selective_regen/gate.py`, `impacted.py`, `fallbacks.py` | Definition gate, member impact, untrusted-closure widening |
| `core/merge/selective_regen/generator_diff_capturer.py` | `GeneratorTrackingGroupDiffCapturer` (group-scoped output capture) |
| `core/regeneration/` | Predicates, member mapping, definition models shared with the proposed-change pipeline |
| `core/branch/tasks.py` | `_build_post_merge_regeneration_dispatcher`, `post_process_branch_merge` wiring |
| `config.py` | `selective_execution_after_merge` |

## See Also

- [Coalesced Recompute on Merge and Rebase](merge-recompute.md) - the sibling merge-followup path for computed attributes, display labels, and human-friendly ids
- [Code Generation](code-generation.md) - fingerprints and dependency closures computed at repository import
- [Events System](events.md) - node mutation events consumed by the non-coalesced regeneration paths
- Feature spec: `dev/specs/archive/ifc-2704-incremental-merge-regen/`
