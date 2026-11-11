# Proposed Change Artifact Reruns

> Part of: `dev/knowledge/backend/` | Related: [selective-merge-regeneration.md](selective-merge-regeneration.md), [async-tasks.md](async-tasks.md)

A run of the artifact checks of a proposed change validates only what changed since the last successful validation of each artifact definition. The rule of [selective regeneration](selective-merge-regeneration.md) applies: selecting too much is acceptable, selecting too little is not. Whenever the earlier validation cannot be relied on, the run selects from the whole branch diff, as the first run of a proposed change does.

## What each run stores

- `run_proposed_change_pipeline` keeps the `from_time` and `to_time` of the branch diff that `DiffCoordinator.update_branch_diff` returns, as a `BranchDiffWindow` (`proposed_change/branch_changes.py`), in the cache under its pipeline id.
- It stores the window only when the `to_time` of the diff is at or after the start of the pipeline flow. A diff that the run did not refresh can describe the branch as it was before a rebase, so the run then stores no window and selects from the whole diff.
- `validate_artifacts_generation` stores one `ArtifactValidationRecord` per proposed change and artifact definition in the cache, for `ARTIFACT_VALIDATION_RECORD_TTL_SECONDS` (`proposed_change/artifact_validation.py`). The record holds the pipeline id, the `from_time` and `to_time` of the diff the validation read, and the source and destination commits of the repository of the definition.
- A validation writes its record before it restarts the validator. When the validator ends with the `success` conclusion, it writes a completion mark whose key holds its own pipeline id. A record counts as completed only when the mark of the pipeline id it carries exists. A failed, cancelled or unfinished validation leaves no mark, and the mark of a validation that another validation overtook names a pipeline id the stored record no longer carries. Writing a mark needs no read, so two validations of one definition cannot overwrite each other's state.

The recorded time is the `to_time` of the diff, not the start time of the validator. A change made between the diff read and the validator start is absent from the summary that validation selected from, and the generator checks of the same pipeline run write to the branch in that interval.

## When a record is relied on

`changes_validated_until` returns the recorded `to_time` when every condition holds, and `None` otherwise:

- the record is marked as completed;
- the run stored a diff window;
- the `from_time` of the diff equals the recorded one: it is the time the branch was created or last rebased;
- the source and destination commits of the repository equal the recorded ones, so the file diff of the transformation is the one already validated;
- the recorded `to_time` is not later than the current one.

Both flows also require the artifact validator of the definition to be `completed` with the `success` conclusion: a validator can fail outside the pipeline, and the record does not show it. Both flows also require the `members` relationship of the target group to be branch-aware (`diff_tracks_members`): the diff holds no member change of a group that is local to its branch, such as a `CoreGeneratorGroup`.

## What a run selects

- The changes made since the recorded time come from a diff of that time window alone: `BranchChangesReader` calls `DiffCoordinator.calculate_arbitrary_timeframe_diff` from the recorded `to_time` to the current one, with the destination branch as base. It keeps the result in the cache under the pipeline id and the window, so the flows of one run calculate each window once. A cached entry that cannot be read is calculated again.
- The window diff is calculated with its unchanged entries (`include_unchanged=True`), and `DiffSummarySerializer` reports them as updated (`unchanged_as_updated=True`). A value changed back to the value of the destination branch is unchanged against that branch, yet the artifact rendered in between is stale. Every calculated entry of a window diff changed in that window. The parent nodes and parent relationships that the diff adds to place a changed node in its hierarchy have no change time, so the serializer leaves them out: otherwise a changed interface would count its device as changed.
- `BranchChanges.changed_peers` holds the peers of each relationship in the window diff, which the diff summary leaves out. The member changes of a target group are read from it.
- A window diff with the source branch as both base and diff branch returns no change for a branch other than the default branch, so the destination branch is the base.
- `refresh_artifacts` first selects the definitions as before, from the whole diff. It then skips a selected definition when `changes_reach_definition` is false for the changes since its record: neither the query nor the definition changed, no kind the query reads changed, and the target group gained or lost no member.
- `validate_artifacts_generation` selects its targets from the changes since the record (`ArtifactValidationRun.changes_to_validate`). It selects from the whole diff when a member that has an artifact joined the target group since: the artifact was not checked while the member was out of the group. It does not evaluate the file changes of the transformation, because the commits are the ones already validated.
- A target without an artifact is always rendered, as before.

## What a user views after a run

- A definition that the run skips keeps its validator as it was: `completed`, `success`, with the start and completion times of the earlier run. Its checks keep their results.
- A definition that the run validates gets its validator restarted. Only the targets that the new changes reach get a new check result. The other checks keep their earlier result and time.

## Known limitations

- An artifact deleted on the branch is not rendered again by a run with no other change. `CoreArtifact` is local to its branch and absent from the branch diff, so the deletion selects nothing. `test_run_after_an_artifact_is_deleted_renders_its_target` (`backend/tests/component/proposed_change/test_artifact_revalidation_pipeline.py`) holds the intended behavior as an expected failure.
- An artifact that depends on something the diff cannot show is rendered again only when a new change selects it. This covers [content composition](selective-merge-regeneration.md#known-limitation-content-composition) and data that a Python transformation reads outside its query.

## Key Files

| File | What |
|------|------|
| `proposed_change/tasks.py` | `run_proposed_change_pipeline`, `refresh_artifacts`, `validate_artifacts_generation` |
| `proposed_change/branch_diff.py` | The diff window cache: `set_diff_window_cache`, `get_diff_window_cache` |
| `proposed_change/branch_changes.py` | `BranchDiffWindow`, `BranchChanges`, `BranchChangesReader` |
| `proposed_change/artifact_validation.py` | `ArtifactValidationRecord`, `ArtifactValidationRecords`, `ArtifactValidationRun`, `changes_validated_until`, `changes_reach_definition`, `diff_tracks_members` |
| `core/diff/coordinator.py` | `calculate_arbitrary_timeframe_diff`, shared with the merge |
