# Selective post-merge regeneration: performance scenarios and activation

Scope: the regeneration that runs in the merge follow-up (`post_process_branch_merge`), for artifact
definitions and generator definitions. This document records which merges regenerate less work when the
feature is active, and the exact conditions that gate the selective path. Behaviors below are the ones
verified by `backend/tests/integration_docker/test_merge_*` on the rendered artifact content.

## Baseline vs selective

| Mode | Behavior on every merge |
|------|-------------------------|
| Legacy (feature off, or any fallback) | Regenerate every artifact of every definition and run every generator, for all members of each target group. Cost is proportional to the whole branch, independent of what the merge changed. |
| Selective (feature on, closure trusted) | Regenerate only the definitions the merge diff affects, narrowed to the impacted members reconciled against the live target group. Cost is proportional to what the merge changed. |

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
| Python transform or generator: the import graph is statically resolvable (no dynamic or unresolvable imports) | Unresolved imports leave `dependencies_complete=false`, so the definition regenerates in full |
| Jinja2 transform: `{% include %}` targets and references are statically resolvable (no computed include paths) | Unresolved references leave `dependencies_complete=false`, so the definition regenerates in full |
| A `watch:` block in the manifest declares the dependency files auto-detection cannot infer | Without it an incomplete closure stays `complete=false`; declaring watch files forces `complete=true`, the author taking responsibility for the declared paths |
| The definition has been re-imported at the current commit | A definition imported before the feature carries `dependencies=null` and stays on the legacy fallback until re-imported; a stale import yields a stale fingerprint |
| Import of the transform hit no isolated failure (broken transform, git error, pathspec escaping the repository) | That transform's closure falls back to `complete=false`, without aborting import of the rest of the repository |

## Scenarios with reduced work

Members of the `people` target group and the section/cascade fixtures below refer to the integration
tests that assert the behavior on rendered content.

| Scenario | Legacy work | Selective work | Test |
|----------|-------------|----------------|------|
| Merge changes only a kind no definition reads | All definitions, all members | None | `test_irrelevant_kind_change_regenerates_nothing` |
| Merge changes one member of one definition | All definitions, all members | Only the changed member's artifact of the affected definition; other members untouched (identical `storage_id`) | `test_change_to_one_member_leaves_the_other_untouched` |
| Merge changes data of a given kind | All definitions | Only definitions whose query reads that kind, narrowed to impacted members | narrowing + `reads_kind` gate |
| Transform or query code changed on the destination (fingerprint moved) | All definitions | Only the affected definition, rendered against the destination's current code | `test_merge_main_code_changed` |
| A definition added to the destination after the branch was cut | Included by full regen | Included, because the selection loads definitions from the destination's live state | `test_merge_new_definition_on_main` |
| Destination gained a member while the branch existed | All definitions, all members | The branch-impacted member regenerates; the extra live member does not break selection | `test_merge_*_diverged` (cascade), diverged-main |
| Merge runs an `execute_after_merge` generator | All artifacts, all members | Only the artifacts the generator's output affects, selected from a post-generator diff | `test_merge_generator_artifact_cascade` |

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
| A generator declared `execute_after_merge: false` | Does not run in the follow-up; its output is not produced. `test_merge_generator_after_merge_false` |
| Query changed, definition node changed, or fingerprint moved on a definition | Regenerate all members of that definition (a code change can alter any output) |

## Known limitations

| Limitation | Evidence |
|------------|----------|
| A composite artifact that inlines an upstream artifact's content (content composition) is not refreshed after a direct merge that changes the upstream. The composite keeps stale inlined content. | `test_merge_composition_cascade` (failing, documents the gap); confirmed live on the demo stack |
