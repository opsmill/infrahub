# Selective post-merge regeneration: performance scenarios and activation

Scope: the regeneration that runs in the merge follow-up (`post_process_branch_merge`), for artifact
definitions and generator definitions. This document records which merges regenerate less work when the
feature is active, and the exact conditions that gate the selective path. The Test column cites the
node that verifies each row, across two suites. Dispatch-layer tests in
`backend/tests/integration/proposed_change/test_merge_selective_regen.py` are committed and run in CI;
they assert which generators and artifacts a merge dispatches. Rendered-content tests in
`backend/tests/integration_docker/test_merge_*` assert the artifact content a merge produces; they are
run locally rather than in CI because of their cost.

## Baseline vs selective

| Mode | Behavior on every merge |
|------|-------------------------|
| Legacy (feature off, or any fallback) | Regenerate every artifact of every definition and run every generator, for all members of each target group. Cost is proportional to the whole branch, independent of what the merge changed. |
| Selective (feature on, closure trusted) | Regenerate only the definitions the merge diff affects, narrowed to the impacted members reconciled against the live target group. Cost is proportional to what the merge changed. |

## Generator-to-artifact cascade

An `execute_after_merge` generator runs in the follow-up, after the merge diff was captured, so its
writes are absent from that diff. The artifacts that read the generator's output cannot be selected
from the merge diff alone; they are selected from the generator's own output, captured once every
generator has run.

| Aspect | Before | Now |
|--------|--------|-----|
| Artifacts after a generator runs | Every artifact of the branch is regenerated; the output is not in the merge diff, so nothing narrows it | Only the artifacts that read the generator's output are regenerated, alongside the merge-diff selection |
| Reading the generator output | Not read; the blanket regeneration stands in for it | A second diff over the window the generators ran, scoped to the tracking-group output nodes (`GeneratorTrackingGroupDiffCapturer`) |
| Output cannot be captured, or a tracking group does not resolve | Already blanket | Widen to every artifact of the branch, without re-running the generators; the merge-diff artifacts already dispatched are kept |

The cascade is gated on `execute_after_merge` and runs the same way for direct merges and
proposed-change merges; the follow-up is identical for both, and the before/now change above applies
to both. A generator flagged `execute_in_proposed_change` is a separate case: it runs during the
proposed change and writes its output on the source branch, so that output is in the merge diff and
its consuming artifacts are selected by the merge-diff narrowing, not the cascade. That path is
unchanged.

## Activation conditions

The follow-up uses the selective path only when all of the following hold. Any miss falls back to the
legacy full regeneration for the whole branch.

| Condition | Where |
|-----------|-------|
| `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE` (`config.SETTINGS.main.selective_execution_after_merge`) is true | dispatcher gate |
| A merge diff summary was captured and is loadable from the cache | dispatcher gate |
| The selection phase raises no exception | dispatcher gate (any error falls back) |

Per definition, the merge is narrowed only when the definition's dependency closure is trusted. The
per-definition fallbacks below regenerate that definition in full (or force its whole repository) while
other definitions can still be narrowed.

| Per-definition condition | Outcome |
|--------------------------|---------|
| `dependencies` is null (imported before the feature) | Regenerate the definition on any file change in its repository |
| `dependencies_complete` is not true (partial closure) | Regenerate the definition in full |
| A definition in the repository has no computed fingerprint | Force full regeneration of every definition in that repository |

## Repository setup conditions for a trusted closure

The dependency closure and the fingerprint are computed at import time by the closure builder, one per
transform, generator, or query declared in the repository `.infrahub.yml`. A definition qualifies for
the narrowed path only when its closure is complete and its fingerprint is fresh; the setup below is
what produces that state. The `.infrahub.yml` path is always part of every definition's closure, so a
manifest edit moves the fingerprint on its own.

| Setup condition | Effect if not met |
|-----------------|-------------------|
| The definition is declared in an imported, git-synced repository `.infrahub.yml`, with a resolvable entry file a closure builder supports | No closure or fingerprint is computed; the definition stays on the legacy fallback |
| Python transform or generator: the entry file sits in a git repository whose tracked files can be enumerated | The closure is the git-tracked files under the entry's directory; imports are not analyzed, so any file in that directory is a dependency. Enumeration failing (not a git repo, git error) leaves `dependencies_complete=false`, so the definition regenerates in full |
| Jinja2 transform: `{% include %}` targets and references are statically resolvable (no computed include paths) | Unresolved references leave `dependencies_complete=false`, so the definition regenerates in full |
| A `watch:` block in the manifest declares the dependency files auto-detection cannot infer | Without it an incomplete closure stays `complete=false`; declaring watch files forces `complete=true`, the author taking responsibility for the declared paths |
| The definition has been re-imported at the current commit | A definition imported before the feature carries `dependencies=null` and stays on the legacy fallback until re-imported; a stale import yields a stale fingerprint |
| Import of the transform hit no isolated failure (broken transform, git error, pathspec escaping the repository) | That transform's closure falls back to `complete=false`, without aborting import of the rest of the repository |

## Scenarios with reduced work

Members of the `people` target group and the section/cascade fixtures below refer to the integration
tests that assert the behavior on rendered content.

| Scenario | Legacy work | Selective work | Test |
|----------|-------------|----------------|------|
| Merge changes only a kind no definition reads | All definitions, all members | None | `integration/proposed_change/test_merge_selective_regen.py::TestIrrelevantKindChange::test_irrelevant_kind_change_dispatches_nothing` |
| Merge changes one member of one definition | All definitions, all members | Only the changed member's artifact of the affected definition; other members untouched (identical `storage_id`) | `integration/proposed_change/test_merge_selective_regen.py::TestMemberNarrowing::test_change_to_one_member_narrows_the_filter` |
| Merge changes data of a given kind | All definitions | Only definitions whose query reads that kind, narrowed to impacted members | `integration/proposed_change/test_merge_selective_regen.py::TestRelevantChange::test_relevant_change_dispatches_matching_definitions` |
| Transform or query code changed on the destination (fingerprint moved) | All definitions | Only the affected definition, rendered against the destination's current code | `integration_docker/test_merge_main_code_changed.py::TestMergeMainCodeChanged::test_merge_renders_against_mains_updated_transform` |
| A definition added to the destination after the branch was cut | Included by full regen | Included, because the selection loads definitions from the destination's live state | No dedicated test; follows from loading definitions on the destination branch |
| Destination gained a member while the branch existed | All definitions, all members | The branch-impacted member regenerates; the extra live member does not break selection | `integration_docker/test_merge_diverged_main.py::TestDivergedMainComposition::test_merge_after_main_gained_a_member_refreshes_the_branch_member`; `integration/proposed_change/test_merge_selective_regen.py::TestConcurrentlyAddedMember::test_concurrently_added_member_does_not_misroute_selection` |
| Merge runs an `execute_after_merge` generator | All artifacts, all members | Only the artifacts the generator's output affects, selected from a post-generator diff | `integration_docker/test_merge_generator_artifact_cascade.py::TestMergeGeneratorArtifactCascade::test_direct_merge_cascades_generator_output_into_artifacts` |

## Live validation (manual battery)

Validated over the API against a demo stack with `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=true`,
asserting rendered artifact content and the selection log. Confirms the narrowing is precise both by
member and by the fields a definition's query reads.

| Merge | Observed selection |
|-------|--------------------|
| One member of the `people` group renamed | Merge diff one node; one of three members rendered; the other two unchanged |
| Two members renamed | Two members rendered; the third unchanged |
| `execute_after_merge` generator cascade (description written post-merge) | Only the affected member's artifact re-rendered, selected from the generator's output |
| The generator's GraphQL query node changed | Wide signal: every member of the definition rendered |
| Interface `mtu` changed (demo dataset) | `startup-config` regenerated with the new value (all edge members, an interface change is not uniquely attributed to one device); `openconfig-interfaces` excluded because its query does not read `mtu` |
| Destination gained a member while the branch existed | The branch-impacted member refreshed; the extra destination member did not break selection |
| Empty merge diff | No generator run and no artifact generation dispatched |

## Cases that still regenerate in full (by design)

These are activation misses or deliberate over-execution. They do not benefit from narrowing; the
choice is correctness over precision.

| Case | Behavior |
|------|----------|
| Feature off, missing or unloadable diff summary, or selection error | Full regeneration of the whole branch |
| A cascade generator fails to run, or its output cannot be captured or selected | Regenerate every artifact of the branch without re-running the generators; the affected artifacts cannot be selected, and the merge-diff artifacts already dispatched are kept |
| A generator declared `execute_after_merge: false` | Does not run in the follow-up; its output is not produced. `integration/proposed_change/test_merge_selective_regen.py::TestGeneratorExecuteAfterMergeFalse::test_generator_with_execute_after_merge_false_is_excluded` |
| Query changed, definition node changed, or fingerprint moved on a definition | Regenerate all members of that definition (a code change can alter any output) |

## Known limitations

| Limitation | Evidence |
|------------|----------|
| A composite artifact that inlines an upstream artifact's content (content composition) is not refreshed after a direct merge that changes the upstream. The composite keeps stale inlined content. | `integration_docker/test_merge_composition_cascade.py::TestMergeCompositionCascade::test_direct_merge_refreshes_inlined_section` (asserts the fresh content, so it fails while the gap is unfixed; local-only, so it does not gate CI); confirmed live on the demo stack |
| Narrowing reduces to the impacted members only when the changed field is a root attribute of the query's target object, or a group-membership change. When the changed data is reached through a relationship (a traversed kind in the query), or the query does not resolve to a single object per root, the resolver cannot map the change back to a member and widens to the whole target group. The behavior is safe (over-execution only), but it negates the per-member benefit for the common case, since most artifacts and generators read relationship data (a device's interfaces, IP addresses, BGP sessions). | [IFC-2946](https://opsmill.atlassian.net/browse/IFC-2946); `QueryImpactClassifier._must_widen` (`backend/infrahub/core/regeneration/impact_classifier.py`) widens on a non-unique-target query or a change on a `traversed_kinds` kind; validated live on release-1.11 |
| The merge diff summary is serialized into a single cached value with no size ceiling. A large merge can produce a summary that exceeds the cache backend's per-value limit (NATS JetStream rejects above ~1 MB; Redis accepts up to 512 MB with memory and latency pressure), so an oversized write fails on NATS and falls back to full regeneration, while on Redis it succeeds under pressure. | [IFC-2943](https://opsmill.atlassian.net/browse/IFC-2943); measured on the live serializer at ~803 bytes per changed node, so ~1,245 changed nodes reach 1 MB, with serialization staying cheap (~3.5 ms at 1 MB), so the binding constraint is the backend value-size limit, not CPU |
| Every merge that runs selective regeneration persists a diff root to capture the post-generator output, then reads it once and discards it without removing it, so each such merge leaves one orphaned diff root in the graph; the rebase path leaks the same way. | [IFC-2941](https://opsmill.atlassian.net/browse/IFC-2941); `GeneratorTrackingGroupDiffCapturer` (`backend/infrahub/core/merge/selective_regen/generator_diff_capturer.py`) saves via `create_or_update_arbitrary_timeframe_diff` under a bare UUID name, so the root carries no tracking id to supersede or wipe |
