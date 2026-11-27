# Contract: new keys of the daily telemetry report

**Date**: 2026-11-26 | **Plan**: [../plan.md](../plan.md) | **Data model**: [../data-model.md](../data-model.md)

The report is the JSON body that a deployment stores every day and sends to the telemetry endpoint unless it opted out. The data warehouse reads it. This contract lists the keys that the change adds. It is the only interface that the change exposes: no GraphQL field, REST route or command changes.

## What stays the same

- `payload_format` is `20260628`.
- No existing key is renamed, removed, or changes type or meaning.
- `infrahub_version` tells which reports contain the new keys.
- The report contains no name that a customer defined.

## New keys

Existing keys are left out of this example. The values are made up.

```json
{
  "activity_24h": {
    "validators_started": {
      "CoreArtifactValidator": 4,
      "CoreDataValidator": 6,
      "CoreGeneratorValidator": 2,
      "CoreRepositoryValidator": 6,
      "CoreSchemaValidator": 6,
      "CoreUserValidator": 3
    },
    "workflow_runs": [
      {"workflow": "generator-run", "state": "COMPLETED", "runs": 120, "run_seconds": 840},
      {"workflow": "generator-run", "state": "FAILED", "runs": 2, "run_seconds": 31},
      {"workflow": "artifact-generate", "state": null, "runs": null, "run_seconds": null}
    ]
  },
  "features": {
    "CoreArtifactDefinition": 3,
    "CoreCheckDefinition": 1,
    "CoreGeneratorDefinition": 2
  },
  "database": {
    "node_count": {
      "artifact_target": 3668,
      "with_artifact": 3,
      "with_generated_artifact": 3,
      "generated_artifact": 5,
      "with_generator_instance": 12
    }
  }
}
```

## `activity_24h.workflow_runs`

A list of rows `{workflow, state, runs, run_seconds}` for the previous full UTC day, the same day as the other values of `activity_24h`.

- `workflow` is one of 8 names: `generator-run`, `run-generator-as-check`, `artifact-generate`, `git-repository-check-artifact-create`, `git-repository-run-user-check`, `transform_render_python`, `transform_render_jinja2_template`, `proposed-changed-pipeline`.
- `state` is one of `COMPLETED`, `FAILED`, `CRASHED`, `CANCELLED`.
- `runs` is the number of runs that ended in the state. `run_seconds` is the time those runs spent running, in whole seconds.
- A run belongs to the UTC day it was expected to start.
- A run that has not ended when the report is produced is in no row, in that report or a later one.
- The ended runs of a branch that is deleted before the report is produced are in no row either: Infrahub deletes them with the branch. Seven of the 8 workflows are affected; `proposed-changed-pipeline` is not. The rows of the three workflows that run inside a proposed change are therefore a lower bound when branches are deleted after the merge.
- An empty list means that no named workflow had a run in an end state.
- A row with `state`, `runs` and `run_seconds` all `null` means that the read for that workflow failed.
- A `null` list means that the report could not read the activity of the day at all.
- A later Infrahub release can add a workflow name. It adds rows and changes no existing row.

What the end state means:

- `state` is the state of the workflow run.
- For `generator-run`, `artifact-generate`, `transform_render_python` and `transform_render_jinja2_template`, a run whose work failed ends in `FAILED`.
- For the three workflows that run inside a proposed change (`run-generator-as-check`, `git-repository-check-artifact-create` and `git-repository-run-user-check`), a failed generator, a failed artifact generation or a failed check is recorded as a check with the conclusion `failure`, and the run ends in `COMPLETED`. Their `FAILED` and `CRASHED` rows count only the runs in which the workflow itself stopped.
- The report does not count the failed generators, artifact generations or checks inside a proposed change.

Which rows make one figure:

- Generator runs: `generator-run` plus `run-generator-as-check`
- Artifact generations: `artifact-generate` plus `git-repository-check-artifact-create`
- Checks that the customer wrote, one per check definition and target: `git-repository-run-user-check`
- Transformations rendered on demand through the REST API: `transform_render_python` plus `transform_render_jinja2_template`
- Pipeline runs of proposed changes: `proposed-changed-pipeline`. Its run seconds do not include the workflows that the pipeline starts.

Figures that the reader computes:

- Average run time: `run_seconds` divided by `runs`.
- The largest possible number of artifact generations that left the content unchanged: the `COMPLETED` runs of the two artifact generation workflows, minus `activity_24h.artifacts_created`, minus `activity_24h.artifacts_updated`. The result also contains the artifact generations that failed inside a proposed change, because those runs end in `COMPLETED` and send no event. A run that crosses midnight UTC can move one count to the next day, and the result can be below zero when a branch was deleted, because the events are kept and the runs are not.

The deliveries of webhooks are not in the list. `activity_24h.webhooks_fired_success` and `activity_24h.webhooks_fired_failure` stay as they are.

## `activity_24h.validators_started`

A map from validator kind to the number of validators of that kind that started in the previous full UTC day.

- The keys are the kinds that inherit from `CoreValidator`. Today these are `CoreArtifactValidator`, `CoreDataValidator`, `CoreGeneratorValidator`, `CoreRepositoryValidator`, `CoreSchemaValidator` and `CoreUserValidator`.
- A later Infrahub release can add a key.
- `0` means that no validator of the kind started. `null` for one key means that its count failed. A `null` map means that the kinds could not be read.
- One started `CoreUserValidator` is one check definition in one pipeline run. A re-run counts again.
- `activity_24h.checks_started` still counts every started validator of all kinds.

## `features`

Three new keys: `CoreArtifactDefinition`, `CoreCheckDefinition` and `CoreGeneratorDefinition`.

- Each counts the nodes of the kind that exist on the default branch. A deleted node is not counted.
- The three keys can be `null`, together, when their read failed.
- The existing keys count graph vertices on every branch, deleted nodes included, and are never `null`.

## `database.node_count`

Five new keys, all for the default branch:

- `artifact_target`: the nodes whose kind inherits from `CoreArtifactTarget`
- `with_artifact`: the nodes with at least one artifact node
- `with_generated_artifact`: the nodes with at least one artifact that has stored content
- `generated_artifact`: the artifacts that have stored content
- `with_generator_instance`: the nodes with at least one generator instance. A node whose only generator run failed in the generator's code or has not finished is counted; a run that fails earlier, while the repository is prepared, creates no instance. Generator instances stay on the branch where the run created them, so a node is counted only after a generator has run for it on the default branch. A generator definition with `execute_after_merge: false` does not run after a merge, so its nodes are counted only after the generator has run for them on the default branch, which a user or a trigger rule with a generator action can start.

Each key is `0` when there is nothing to count and `null` when its read failed. `with_artifact`, `with_generated_artifact` and `generated_artifact` are `null` together.

## What the report does not contain

- A row per kind, a kind name that a customer defined, or a count of devices
- API reads per day
- A median or an average run time
- The number of failed generators, failed artifact generations and failed checks inside a proposed change
- A day earlier than the previous full UTC day

## What the data warehouse needs

- A table for the rows of `activity_24h.workflow_runs`, one row per report, workflow and end state, that accepts `null` in `state`, `runs` and `run_seconds`.
- Columns for the keys of `activity_24h.validators_started`, for the three new `features` keys and for the five new `database.node_count` keys.
- No change to the check on the payload format version.
