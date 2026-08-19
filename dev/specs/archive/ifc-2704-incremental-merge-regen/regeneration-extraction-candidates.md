# `core/regeneration` extraction — candidates beyond the Phase-1 cluster

**Branch**: `pmi-20260717-refactoring-pc-merge-selective` · **Parent**: IFC-2908 · **Companion**: [followup-core-regeneration.md](./followup-core-regeneration.md)

The Phase-1 plan moves a defined shared cluster out of `proposed_change/tasks.py`. Surveying the
whole `proposed_change` package surfaced more regeneration-related code that could belong in the new
leaf package. This lists those candidates so scope can be chosen deliberately rather than by the
doc's original list alone.

**Status**: Phase 1 (section A) plus B1/B2 shipped on this branch. B3–B6 remain open.

## A. Phase-1 defined cluster (moved)

Per followup-core-regeneration.md: `DefinitionSelect`, `ImpactScope`, `ImpactedSubscribers`,
`PredicateOutcome`, `RegenerationDefinition`, `_query_changed`, `_definition_changed`,
`_relevant_node_changes`, `_is_triggering_action`, `_TRIGGERING_DIFF_ACTIONS`,
`_should_render_artifact`, `_run_generator`, `_map_subscriber_ids_by_member`,
`_parse_artifact_definitions`, `get_field_level_impacted_subscribers`, `_get_subscribers_for_nodes`,
`GATHER_GRAPHQL_QUERY_SUBSCRIBERS`, `GATHER_ARTIFACT_DEFINITIONS`.

## B. Additional candidates (to choose/discuss)

| # | Item | Location | What it is | Why it may belong | Suggested |
|---|---|---|---|---|---|
| B1 | `transform_changed` | `core/regeneration/predicates.py` | Selection predicate, sibling of `query_changed` / `definition_changed` | Same predicate family; splitting it from its siblings would leave the predicate logic straddling two modules | **Moved** — folded into Phase 1 (`predicates.py`) |
| B2 | `repo_diff_or_none` | `core/regeneration/predicates.py` | Helper: find a repository's file diff in the branch diff | Consumed by the file-change predicate path | **Moved** — folded into Phase 1 (`predicates.py`) |
| B3 | `_define_instance` | `proposed_change/tasks.py:1157` | Resolves/creates the generator instance for a check | Generator-regeneration mechanics; parallels merge-side member handling | Discuss — currently only the PC check flow uses it |
| B4 | PC selection **flows**: `run_generators`, `refresh_artifacts`, `validate_artifacts_generation`, `request_generator_definition_check`, `run_generator_as_check` | `proposed_change/tasks.py:400/1724/855/1198/1054` | The PC-side flows that select + dispatch regeneration | Their **selection cores** duplicate what `core/merge/selective_regen/` now does; the real convergence prize | Defer to a **Phase 3 convergence** (out of Phase 1); big blast radius |
| B5 | Diff-summary helpers: `has_data_changes`, `has_node_changes`, `RepositoryFileDiffer` / `GitRepositoryFileDiffer`, `set_diff_summary_cache`, `get_diff_summary_cache` | `proposed_change/branch_diff.py` | Diff-summary construction + cache both paths read | `get_modified_kinds` (same file) is already shared cross-package; these are the same layer | Discuss — could form a shared `regeneration/diff.py` or stay |
| B6 | Regeneration request models: `RequestArtifactDefinitionCheck`, `RunGeneratorAsCheckModel`, `RequestGeneratorDefinitionCheck`, `RequestProposedChangeRunGenerators`, `RequestProposedChangeRefreshArtifacts` | `proposed_change/models.py` | Message-bus request payloads for regeneration | Consumed by both the checks and the selection flows | Discuss — message-bus-shaped; lower priority |

## C. Stays in `proposed_change` (not regeneration)

PC-pipeline orchestration and repository/merge machinery: `merge_proposed_change`,
`_merge_branch_for_proposed_change`, `run_proposed_change_pipeline`, the schema/data-integrity
checks, `cancel_*`, `repository_checks`, `run_proposed_change_user_tests`, and the repository parsers
/ queries (`Repository`, `_parse_proposed_change_repositories`, `_parse_repositories`,
`_get_proposed_change_repositories`, `_validate_repository_merge_conflicts`,
`DESTINATION_ALLREPOSITORIES`, `SOURCE_REPOSITORIES`, `SOURCE_READONLY_REPOSITORIES`).

## Recommendation

- **Phase 1 as-planned + B1/B2** (predicates are incomplete without `transform_changed`).
- **Discuss** B3, B5, B6 before this branch grows.
- **B4 is the actual convergence** (one selection engine for PC + merge) — its own increment, not
  folded into the cycle-break.
