# Research: Incremental generator & artifact execution on merge (IFC-2704)

**Date**: 2026-07-10 · **Spec**: [spec.md](./spec.md)

All findings below are verified against the working tree; file:line references are the
citations for the plan. Where the source epic's framing did not match the code, the
correction is called out inline.

## Current behavior (the thing being replaced)

`BranchMergeOrchestrator.merge` (`backend/infrahub/core/merge/orchestrator.py:68-177`)
performs the graph merge, then at `:95-101` loads the enriched diff for changelog
collection and, at `:146-153`, marks the diff root `is_merged=TRUE` and rewrites its
tracking id from `branch.{name}` to `frozen.{name}`. It then calls
`PostMergeDispatcher.run_follow_ups` at `:163`.

`PostMergeDispatcher.run_follow_ups` (`backend/infrahub/core/merge/post_merge.py:58-104`)
merges repositories first (`:68-71`), then submits several follow-up workflows, last of
which is `BRANCH_MERGE_POST_PROCESS` (`:100-104`) with parameters
`{source_branch, target_branch}`.

`post_process_branch_merge` (`backend/infrahub/core/branch/tasks.py:434-478`) — the target
of that workflow — unconditionally submits two workflows keyed only on the target branch:

- `TRIGGER_ARTIFACT_DEFINITION_GENERATE` → `generate_artifact_definition`
  (`backend/infrahub/git/tasks.py:495-508`) fetches **all** `CoreArtifactDefinition` and
  fans out `REQUEST_ARTIFACT_DEFINITION_GENERATE` per definition, no `limit`.
- `TRIGGER_GENERATOR_DEFINITION_RUN` (`source=MERGE`) → `run_generator_definition`
  (`backend/infrahub/generators/tasks.py:138-178`) fetches **all** generator definitions,
  filters only by `execute_after_merge` (`:150-153`), fans out
  `REQUEST_GENERATOR_DEFINITION_RUN` per definition, no `target_members`.

Both `TRIGGER_*` constants are submitted from **exactly one** production site
(`branch/tasks.py:450` and `:456`); `BRANCH_MERGE_POST_PROCESS` from exactly one
(`post_merge.py:102`). Replacing the merge path touches no other caller — confirmed by grep
(catalogue defs at `backend/infrahub/workflows/catalogue.py:78-91, 274-281`).

## Decision 1 — Capture the diff in the orchestrator, before the freeze; write the cache only after commit

**Decision**: Split capture into two steps inside `BranchMergeOrchestrator.merge`:

1. **Serialize before the freeze (in memory).** Reuse the `branch_diff` object already loaded
   at `orchestrator.py:96` (do not re-load). Convert `branch_diff.nodes` (action !=
   `UNCHANGED`) into the SDK `NodeDiff` summary shape into a local variable. Serialization reads
   the in-memory object only, so it is unaffected by `freeze_diffs_for_branch` (`:151`, which
   mutates DB rows, not the loaded object) and may run any time after `:96`.
2. **Write the cache only after the point of no return.** Perform the `InfrahubCache` write
   after the merge has definitively committed — after the `BranchStatus.MERGED` transition
   (`:155-157`) and write-block lift (`:161`), immediately before `run_follow_ups` (`:163`) —
   and thread the resulting key into `run_follow_ups`.

**Why the split**: the consumer (`run_follow_ups` → `post_process_branch_merge`) is only reached
after `:155`; a merge that fails anywhere in the try block (`:81-134`) hits `except
BaseException` (`:135-144`), rolls back, and re-raises **before** `:163`. Writing the cache only
past the point of no return means a **failed/rolled-back merge writes nothing** — no orphan
cache entry to expire, and no possibility of a selective regeneration being driven by a merge
that did not commit.

**Capture must never fail the merge (critique E7)**: the serialization sits logically in the
try block's reach; wrap the serialization (and the later cache write) in their own try/except
that logs and yields `merge_diff_cache_key = None` on any error, never re-raising. A capture
bug then degrades to the full-regeneration fallback (Decision 6) instead of rolling back an
otherwise-correct merge.

**Rationale**: Post-merge retrieval is impossible. `get_node_field_summaries`
(`core/diff/repository/repository.py:588-595`) and its query
(`core/diff/query/field_summary.py:37-61`) exclude `is_merged=TRUE`; `get_one`
(`repository.py:224-250`) keyed on `BranchTrackingId` can no longer match after the freeze
rewrites the tracking id to `frozen.{name}`. The clean source is the live `branch_diff`
(`EnrichedDiffRoot`, `core/diff/model/path.py:497`) already in hand at merge time.

**Do not source from the changelog collector**: `DiffChangelogCollector.collect_changelogs`
(`core/changelog/diff.py:231-238`) drops `UNCHANGED` nodes **and** nodes whose only change
was a conflict resolved to the base branch (`_keep_branch_update`, `diff.py:241-244`, via
`has_changes`, `core/changelog/models.py:250-251`). Those are real changes for regeneration.
Source from `branch_diff.nodes` with `action != DiffAction.UNCHANGED` directly.

**Alternatives rejected**: recomputing the diff after merge (returns empty set →
under-execution, the forbidden failure mode); reusing the changelog node set (narrowed too
far, same problem).

## Decision 2 — Reuse the proposed-change `NodeDiff` cache shape, merge-scoped key

**Decision**: Store the serialized summary as `list[NodeDiff]` JSON in `InfrahubCache`,
mirroring `set_diff_summary_cache` (`backend/infrahub/proposed_change/branch_diff.py:133-151`)
but under a merge-scoped key derived from the **diff-root uuid**
(`EnrichedDiffRootMetadata.uuid`, `path.py:463`), which is stable across the freeze. Thread
only that key string through the follow-up chain.

**Rationale**: The whole selection pipeline (`get_modified_kinds`, the predicates,
`get_field_level_impacted_subscribers`) already consumes exactly this shape. Reusing it means
the selection logic works unmodified. A direct merge has no proposed change and no pipeline
id, so the pipeline-id key cannot be reused; the diff-root uuid is stable and unique. Passing
only the key (not the payload) through Prefect parameters avoids the parameter-size problem.
TTL mirrors the PC cache (`KVTTL.TWO_HOURS`).

**`NodeDiff` shape** (SDK `python_sdk/infrahub_sdk/diff.py:11-36`):
`{branch, kind, id, action, display_label, elements[]}`; each element
`{name, element_type ∈ {ATTRIBUTE, RELATIONSHIP_ONE, RELATIONSHIP_MANY}, action, summary{added,updated,removed}, peers?}`.

**Serialization mapping** (no existing converter — must be written):

| `NodeDiff` field | Source on `EnrichedDiffNode` (`path.py:342-454`) |
|---|---|
| `id` | `node.uuid` |
| `kind` | `node.kind` |
| `branch` | the **target (destination) branch name** (see below), *not* `diff_branch_name` |
| `display_label` | `node.label` |
| `action` | `node.action` (`DiffAction`) → **uppercase name** (`"ADDED"/"UPDATED"/"REMOVED"`) |
| `elements[]` | `node.attributes` (`element_type="ATTRIBUTE"`) + `node.relationships` (`element_type` from `cardinality`) |
| `elements[].summary` | `BaseSummary` counts (`num_added/updated/removed`) |
| `elements[].peers` | `EnrichedDiffRelationship.relationships` (per-peer `EnrichedDiffSingleRelationship`) |

**Uppercase-action trap**: `get_diff_summary` serializes `action` as the GraphQL enum
**name** (uppercase), while `DiffAction.*.value` is lowercase. Consumers already normalize via
`_is_triggering_action` → `.lower()` (`proposed_change/tasks.py:1354-1365`). The converter
MUST emit uppercase names so a fingerprint/definition change reads identically to the PC path.

**Branch-tag decision (resolves critique E3, branch coupling)**: the enriched diff's
`diff_branch_name` is the *source* branch, but post-merge the changed data lives on the
**target (destination) branch** — the branch the merge lands on, which the orchestrator already
uses for its own post-merge schema/IPAM work (`self.destination_branch`) and which
`post_process_branch_merge` receives as its `target_branch` parameter. That is also where the
selection must run its live lookups (schema, GraphQL params, subscriber and group queries). Tag
every `NodeDiff.branch` with the **target-branch name** so the summary's branch tag and the
live-query branch are one and the same. `get_modified_kinds` (`branch_diff.py:122-130`, filters
`entry["branch"] == branch`) and `_relevant_node_changes` (`tasks.py:779`) then work against the
target branch with no special casing, and the source branch can be deleted
(`delete_branch_after_merge`) without affecting selection — only its now-merged data, on the
target branch, is needed.

Use the threaded `target_branch` value (i.e. `self.destination_branch` in the orchestrator),
**not** a fresh `registry.default_branch` lookup. In Infrahub today a branch is always merged
into the default branch (`branch/tasks.py:298` forces `destination = registry.default_branch`),
so target == default in practice; keying off the `target_branch` parameter keeps the design
correct if that ever changes.

**Capture safety (resolves critique E7)**: serialization and the cache write are split across
the point of no return (see Decision 1) and both are wrapped in their own try/except that, on
any failure, logs and sets `merge_diff_cache_key = None` (→ full-regen fallback) and never
re-raises — a serialization bug must never roll back a committed merge, and a failed merge must
never leave an orphan cache entry.

**Alternatives rejected**: a bespoke merge-only summary model (would fork the predicates);
keying on a fresh UUID (works, but the diff-root uuid is already unique, stable, and
meaningful).

## Decision 3 — Thread the cache key through the follow-up chain

**Decision**: `orchestrator.merge` → `run_follow_ups(..., merge_diff_cache_key: str | None)`
→ `BRANCH_MERGE_POST_PROCESS` parameters `{source_branch, target_branch, merge_diff_cache_key}`
→ `post_process_branch_merge(..., merge_diff_cache_key: str | None = None)`.

**Rationale**: Only a string crosses the Prefect boundary. `None` (older submissions,
capture failure) routes to the full-regeneration fallback (Decision 6).

## Decision 4 — Port the PC selection logic into the merge path

**Framing correction**: The PC tasks `run_generators` (`proposed_change/tasks.py:400-505`)
and `refresh_artifacts` (`:1720-1793`) dispatch `*_CHECK` workflows, and member-level
narrowing happens **inside** the CHECK flows (`validate_artifacts_generation` `:914-1047`,
`request_generator_definition_check` `:1251-1351`). The `limit` / `target_members` knobs live
on the **merge/manual** `*_RUN` / `*_GENERATE` workflows, which the CHECK flows do not use.
Reuse therefore means: replicate the definition-level gate logic **and** the member-level
`get_field_level_impacted_subscribers` analysis in the merge path, then translate the result
into `target_members` (generators) and a new member filter (artifacts).

**Decision**: Add a merge selection routine (new module
`backend/infrahub/core/merge/selective_regen.py`) that, given the cached `list[NodeDiff]`:

1. **Definition level** — reuse `RegenerationDefinition` (Protocol, `tasks.py:1383-1404`),
   `DefinitionSelect` (`:1550-1581`), `PredicateOutcome` (`:1368-1380`), and the predicates
   `_query_changed` (`:1407`), `_definition_changed` (`:1439`), plus the `MODIFIED_KINDS`
   intersection with `query_models` (generator `:471-476`; artifact `:1764-1776`, with the
   `Profile`-strip variant). Keep the `execute_after_merge` filter for generators
   (`generators/tasks.py:150-153`).
2. **Repo-code signal replaces `_transform_changed`** — `_transform_changed`
   (`tasks.py:1480-1540`) reads a `ProposedChangeRepository` **file** diff, which does not
   exist post-merge. It is replaced by the fingerprint-in-diff signal: a transform/query
   change recomputes the definition's own `fingerprint` at import (IFC-2844 layered
   composition), so the definition node appears as `UPDATED` in the merge diff and
   `_definition_changed` already fires — no new predicate needed for the populated-fingerprint
   case. Plus the null-fingerprint fallback (Decision 6).
3. **Member level** — reuse `get_field_level_impacted_subscribers` (`tasks.py:790-847`) and
   `ImpactScope` (`:753-764`) for the *impact signal only*, then reconcile against the **live
   group** exactly as the proposed-change CHECK flow does. See Decision 4a — this is the
   load-bearing safety mechanism, not an optimization.

**Refactor**: `get_field_level_impacted_subscribers` and the predicate functions currently
resolve the summary internally via `get_diff_summary_cache(pipeline_id=...)`. Generalize them
to accept a resolved `diff_summary: list[NodeDiff]` **and an explicit query branch** (the
merge's `target_branch`) so both the PC path and the merge path can call them. This is a
two-caller extraction, satisfying the "serve ≥2 callers" bar in constitution VII.

## Decision 4a — Member selection reconciles against the live group (resolves E1, E2, X1)

**The hole**: `get_field_level_impacted_subscribers` returns **subscriber ids** (existing
artifact / generator-instance node ids, `tasks.py:836`), while the dispatch filters
`target_members` (`generators/tasks.py:227`) and the new `members` (`git/tasks.py:594-598`)
key on **member node ids**. Passing subscriber ids into a member filter makes
`member.id not in members` true for every real member → the whole definition is skipped
(silent, total under-execution). And a diff-derived member list cannot enumerate a newly added
member (its subscriber query returns `[]`) nor an existing-object membership-only change
(surfaces as a relationship element the query never reads).

**Decision**: The merge path MUST NOT derive the member filter from the diff alone. Per
selected definition it reproduces the proven CHECK-flow reconciliation on the **target branch**:

1. Fetch the definition's **live group members** on the target (destination) branch (the CHECK flow
   uses `fetch_artifact_definition_targets` / `group.members`) and build the
   `member.id → existing subscriber_id` map (`artifacts_by_member`, `git/tasks.py:565-568`).
2. Compute `managed_branch` for the definition = query changed OR definition/fingerprint
   changed OR repo-code change — i.e. the definition-level gates from step 2 above.
3. Compute the impacted subscriber ids via `get_field_level_impacted_subscribers` against the
   merge summary, querying the **target branch**.
4. For each live member decide render with the existing predicate logic
   (`_should_render_artifact` `:1030-1047`, `_run_generator` `:1338-1351`):
   render iff `managed_branch` **or** the member has **no** existing subscriber (new member)
   **or** its subscriber id ∈ impacted ids **or** `ImpactScope.ALL`.
5. Translate the rendered members back to **member ids** for the dispatch filter
   (`target_members` / `members`). If every live member renders, send an empty filter (= all).

This closes E1 (impacted subscriber ids are mapped to member ids through the live-group map,
never passed raw), E2 (new members and membership-only additions are covered by live-group
iteration + the no-subscriber short-circuit, not by the diff), and X1 (the reconciliation is
the spine, not an add-on).

**Group-membership definition gate**: because a membership-only change may not fire the
data/query/definition gates, a definition is **also** selected when its target group appears in
the merge summary (as a changed group node or a group `members` relationship change). Combined
with step 4's new-member short-circuit, this guarantees a member added to a targeted group
regenerates even when nothing the query reads changed.

**Cost note**: steps 1/3 perform bounded per-selected-definition group and subscriber fetches —
the same fetches the PC CHECK flow already runs. The "diff already loaded, no new hot-path
Cypher" claim applies to the *definition-level* gate, not the member level; correct new-member
coverage requires these fetches (constitution V note in plan.md updated accordingly).

**Alternatives rejected**: deriving members purely from the diff (the original draft — under-
executes on new members and SPECIFIC scope); comparing in artifact-id space like the PC CHECK
flow and dispatching per-member check workflows (would require porting the whole CHECK-flow
fan-out; the merge `*_RUN`/`*_GENERATE` workflows already iterate members, so a member-id
filter is the smaller, correct surface).

**Note on `ImpactScope` provenance**: `get_field_level_impacted_subscribers` / `ImpactScope`
came from commit `efda963be` (field-level data-change scoping), not INFP-409. The invariant
("over-execution acceptable, under-execution not") is the INFP-409 contribution.

## Decision 5 — Fix the artifact `limit` trap with a member-id filter

**Decision**: Add a `members: list[str]` field (member **node ids**) to
`RequestArtifactDefinitionGenerate` (`backend/infrahub/git/models.py:19-28`) and consume it in
`generate_request_artifact_definition` (`backend/infrahub/git/tasks.py:594-598`) mirroring the
generator's `target_members` semantics (filter on `member.id`). The merge path uses `members`,
never `limit`.

**Rationale (confirmed trap)**: `limit` is matched against `artifacts_by_member.get(member.id)`
— the **existing** artifact id, or `None` for a member that has no artifact yet
(`git/tasks.py:565-568, 594-598`). A non-empty `limit` therefore silently skips brand-new
members (`None not in limit` → skip) → under-execution. `target_members`
(`generators/models.py:31-38`, consumed `generators/tasks.py:224-228`) already filters on
`member.id` and is safe. `members` defaults to empty, so existing `limit`-based callers are
unaffected.

**Alternatives rejected**: re-keying `limit` on member ids (breaks existing callers);
force-including new members into `limit` as fake ids (fragile).

## Decision 6 — Fallbacks all point at over-execution

**Decision**: For a given merge, fall back to the current blanket behavior (submit the two
`TRIGGER_*` workflows) when any of: the flag is off; `merge_diff_cache_key` is `None`; the
cached summary is missing/unloadable (`ResourceNotFoundError`); or the diff capture failed.
Additionally, per definition: if a definition's `fingerprint` is null (pre-IFC-2844 data) and
the merge diff contains a repository code signal for that definition's repository, run **all**
definitions of that repository. If `dependencies_complete` is not `True`, the definition is
selected (over-execution), matching the PC predicate's safety fallback.

**Repo signal verification (resolves E6)**: the null-fingerprint fallback assumed a
`CoreRepository.commit` change is present in `branch_diff.nodes` at capture. But repositories
are re-imported on the **default branch during the follow-up** (Decision 8), *after* capture,
so the commit bump may not be in the pre-freeze diff. A task MUST verify whether a source-branch
code change yields a `CoreRepository`/`CoreGenericRepository` node with a triggering `commit`
attribute element in `branch_diff.nodes` at capture time. If the signal is present → use it. If
it is **absent or unreliable**, escalate: any null-fingerprint definition present in the merge
triggers **full regeneration of that repository's definitions** (coarsest safe fallback). The
null-fingerprint state is transient (self-heals on the next re-import), so coarse
over-execution here is acceptable.

**Rationale**: Direct restatement of the INFP-409 invariant. Every uncertain path regenerates.

## Decision 7 — Generator-output cascade on direct merges (resolves Open Question 1)

**Finding**: For a merge **via a proposed change**, generators ran as checks and their output
is already committed to the branch, so it appears in `branch_diff` → artifact selection is
correct. For a **direct merge**, `execute_after_merge` generators run in the follow-up and
mutate default-branch data **after** the diff was captured; artifacts depending on that output
are not in the captured diff.

**Decision**: On a **direct merge** (no proposed change) where the selective step dispatches
**≥1 generator run**, fall back to **full artifact regeneration** for that merge (submit
`TRIGGER_ARTIFACT_DEFINITION_GENERATE` with no filter). Selective generator dispatch is still
applied. Proposed-change merges keep full selective artifact behavior.

**Sequencing hazard (resolves E4)**: the current `TRIGGER_*` submissions are fire-and-forget,
so a full-artifact-regen fallback submitted *alongside* the generator run can execute **before**
the generators mutate default-branch data → artifacts render against pre-generator state and
stay stale. A concurrent fallback therefore does **not** close FR-011.

**The spike is a blocking prerequisite, not optional.** Before this fallback is finalized, a
task MUST determine whether the existing event-driven machinery already regenerates artifacts
on generator-produced data mutations:

- **If yes** → rely on it; drop the full-artifact fallback entirely (it would be redundant).
- **If no** → the fallback MUST **await** generator completion before triggering artifact
  regeneration (sequenced, not concurrent). This is the only ordering that closes FR-011.

**Rationale**: Honors the no-under-execution invariant. Precise per-artifact sequencing
(capture generator output, fold into artifact selection) remains a future optimization.

**Alternatives rejected**: concurrent full-artifact fallback (races generator mutation — the
E4 hole); assuming event machinery covers it without running the spike (risks under-execution).

## Decision 8 — Repo merge ordering / double-trigger (resolves Open Question 2)

**Finding**: `run_follow_ups` merges repositories and re-imports code on the default branch
**before** submitting `BRANCH_MERGE_POST_PROCESS` (`post_merge.py:68-104`). The re-import
recomputes fingerprints from content hashes to **identical** values, so it produces no net
fingerprint change on the default branch and cannot add a second signal. The branch's
fingerprint change is already captured in `branch_diff` (Decision 1).

**Decision**: No design change. Add an explicit regression test asserting a
transform-file-change merge triggers regeneration exactly once (no double-trigger from the
default-branch re-import).

## Decision 9 — Config gate

**Decision**: Add `selective_execution_after_merge: bool = True` to `MainSettings`
(`backend/infrahub/config.py:183`, mirroring `delete_branch_after_merge` at `:215`). Env var
`INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`. Read via `config.SETTINGS.main.selective_execution_after_merge`
inside `post_process_branch_merge`. When `False`, the current blanket path runs unchanged
(baseline for scale tests, reversible rollout).

**Default rationale**: The fallbacks (Decision 6/7) preserve no-under-execution even when
enabled, and the originating bug is severe; shipping disabled would leave it unfixed. Default-
True is safe as a mechanism (the `None` key and every fallback route to byte-for-byte current
behavior) and is acceptable now that E1–E3 are closed.

**Observability (resolves E8)**: every merge follow-up MUST log/emit a metric recording whether
it took the **selective** or a **fallback** path, and the dispatched generator/artifact counts.
Silent under-execution is the failure mode with no natural alarm; this makes selective-vs-
fallback ratio and dispatch volume observable in production so a regression is caught.

**Generated-file impact**: Adding an `INFRAHUB_` setting requires regenerating
`docker-compose.yml` (`uv run invoke release.gen-config-env --update-docker-file`; CI job
`validate-docker-compose-env-vars`) and `docs/docs/reference/configuration.mdx`
(`uv run invoke docs.generate`; CI job `validate-generated-documentation`). Both must be
committed or CI fails.

## Reused components (no reimplementation)

| Component | Location | Reused for |
|---|---|---|
| `RegenerationDefinition` protocol | `proposed_change/tasks.py:1383-1404` | definition-level gate inputs |
| `DefinitionSelect` / `PredicateOutcome` | `tasks.py:1550-1581`, `:1368-1380` | gate accumulation + logging |
| `_query_changed` / `_definition_changed` | `tasks.py:1407-1477` | query & definition (+fingerprint) change |
| `get_modified_kinds` | `proposed_change/branch_diff.py:122-130` | `MODIFIED_KINDS` intersection |
| `get_field_level_impacted_subscribers` / `ImpactScope` | `tasks.py:790-847`, `:753-764` | member-level narrowing |
| `only_has_unique_targets` | `graphql/analyzer.py:385-388` | SPECIFIC vs ALL member scope |
| `set/get_diff_summary_cache` shape | `proposed_change/branch_diff.py:133-151` | cache format |
| `fingerprint` attribute (branch-aware) | IFC-2844, on the 4 definition kinds | repo-code signal in diff |
| `dependencies` / `dependencies_complete` | IFC-2738/INFP-409, on transform & generator | over-execution fallback |
| `execute_after_merge` | `core/schema/definitions/core/generator.py:50-56` | generator merge filter |
| `RequestGeneratorDefinitionRun.target_members` | `generators/models.py:31-38` | member dispatch (safe) |

## Open items carried to tasks

- **Blocking spike (D7/E4)**: determine whether the event-driven machinery covers
  generator→artifact staleness on direct merges. Outcome decides whether the fallback is
  dropped or must await generator completion. Resolve before finalizing direct-merge dispatch.
- **Verification (D6/E6)**: confirm a source-branch code change produces a `CoreRepository`
  node with a triggering `commit` element in `branch_diff.nodes` at capture; else escalate the
  null-fingerprint case to repository-wide full regeneration.
- Confirm no other caller of the artifact `GENERATE` workflow regresses when `members` is
  added (default-empty preserves behavior; verify by grep + test).
- Member reconciliation (D4a) must be covered by a functional test for each of: new object
  added to a targeted group, existing object added to a targeted group (membership-only), and
  SPECIFIC-scope field change — each asserting the correct member(s) regenerate and no member
  is dropped.
