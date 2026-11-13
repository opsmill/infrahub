# Proposed Change Artifact Reruns

> Part of: `dev/knowledge/backend/` | Related: [selective-merge-regeneration.md](selective-merge-regeneration.md), [async-tasks.md](async-tasks.md)

A run of the artifact checks of a proposed change validates only what changed since the last successful validation of each artifact definition. The rule of [selective regeneration](selective-merge-regeneration.md) applies: selecting too much is acceptable, selecting too little is not. Whenever the earlier validation cannot be relied on, the run selects from the whole branch diff, as the first run of a proposed change does.

## What each run stores

- `run_proposed_change_pipeline` reads the diff summary and the change times of the stored branch diff in one `DiffTree` query (`proposed_change/branch_diff.py::read_diff_summary`). The change times (`core/regeneration/changes_since.py::DiffChangeTimes`) hold the `from_time` and `to_time` of the diff and the last change time of each node, field and relationship peer.
- The pipeline stores the change times in the cache under its pipeline id only when the `to_time` of the diff is at or after the start of the pipeline flow. A diff that the run did not refresh can describe the branch as it was before a rebase, so the run then stores no change times and selects from the whole diff.
- `validate_artifacts_generation` stores one `ArtifactValidationRecord` per proposed change and artifact definition in the cache, for `ARTIFACT_VALIDATION_RECORD_TTL_SECONDS` (`proposed_change/artifact_validation.py`). The record holds the pipeline id, the `from_time` and `to_time` of the diff the validation read, and the source and destination commits of the repository of the definition.
- A validation writes its record as not completed before it restarts the validator. It marks the record as completed only when the validator ends with the `success` conclusion and the stored record still carries its own pipeline id. A failed, cancelled or unfinished validation, or one that another validation overtook, leaves no completed record.

The recorded time is the `to_time` of the diff, not the start time of the validator. A change made between the diff read and the validator start is absent from the summary that validation selected from, and the generator checks of the same pipeline run write to the branch in that interval.

## When a record is relied on

`changes_validated_until` returns the recorded `to_time` when every condition holds, and `None` otherwise:

- the record is marked as completed;
- the run stored change times;
- the `from_time` of the diff equals the recorded one: it is the time the branch was created or last rebased;
- the source and destination commits of the repository equal the recorded ones, so the file diff of the transformation is the one already validated;
- the recorded `to_time` is not later than the current one.

`validate_artifacts_generation` also requires the previous validator to be `completed` with the `success` conclusion. Both flows also require the `members` relationship of the target group to be branch-aware (`diff_tracks_members`): the diff holds no member change of a group that is local to its branch, such as a `CoreGeneratorGroup`.

## What a run selects

- `changes_since` keeps the entries of the diff summary that changed at or after the recorded time. A field that the diff marks as unchanged but that changed in that time counts as updated: a value changed back to the value of the destination branch is unchanged against that branch, and the artifact rendered in between is stale.
- The change time of an attribute is the latest among the attribute and its properties (`parse_diff_change_times`). The `last_changed_at` of the attribute alone is the time the attribute was added or removed, not the time its value changed. The change time of a relationship is the latest among its peers.
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
| `proposed_change/branch_diff.py` | `read_diff_summary`, `parse_diff_change_times`, the change-times cache |
| `proposed_change/artifact_validation.py` | `ArtifactValidationRecord`, `ArtifactValidationRecords`, `ArtifactValidationRun`, `changes_validated_until`, `changes_reach_definition`, `diff_tracks_members` |
| `core/regeneration/changes_since.py` | `DiffChangeTimes`, `changes_since`, `peers_changed_since` |
