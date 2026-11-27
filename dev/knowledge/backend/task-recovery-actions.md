# Task Recovery Actions

> Part of: `dev/knowledge/backend/` | Related: [Async Tasks](async-tasks.md), [Webhooks](webhooks.md), [ADR-0014](../../adr/0014-generic-per-task-recovery-actions.md)

Which task runs expose Retry and Cancel in the task history, and how each task type carries out a
retry.

## Availability

A task run exposes recovery actions through the `available_actions` field of the GraphQL `Task`
type. `TaskActionGenerator` (`graphql/queries/task_actions.py`) derives the action set from the
run's workflow name and current state, with one rule per task type. `InfrahubTaskRetry` and
`InfrahubTaskCancel` carry the actions out and apply the same rule again, so an action that no
longer applies is refused.

| Task type | Workflows | Retry | Cancel |
|-----------|-----------|-------|--------|
| Webhook delivery | `WEBHOOK_SEND` | Once the delivery has settled, or is being cancelled | While the delivery is in flight |
| Artifact check | `GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE`, `REQUEST_ARTIFACT_DEFINITION_CHECK` | Once the run has finished | Not offered |

Any other task type exposes no action. The delivery-specific behavior is in
[Webhooks](webhooks.md#delivery-operability).

## Retry dispatch

`InfrahubTaskRetry` checks that retry applies to the run, then hands the run to the first
`TaskRetryHandler` whose `supports()` accepts it (`graphql/mutations/task.py::TaskRetryDispatcher`).
The handler owns the authorization and the resubmission of its task type. It returns the run that
the task history lists for the retry, or none, and the mutation returns that run as `task`. To make
a task type retryable, add its availability rule to `TaskActionGenerator` and its handler to
`build_task_retry_dispatcher`.

## Artifact check retry

Do not retry an artifact check task by replaying the parameters stored with its run. They hold the
repository commit of the earlier run, a run of one target does not update the conclusion of the
validator, and a replay skips the lock of the artifact definition and the check that the proposed
change is open. The handler submits the request that `CoreProposedChangeRunCheck` submits for a
failed-only retry. Both build it with `proposed_change/check_run.py::CheckRunRequestBuilder`, which
validates the selection of checks, the state of the proposed change, and that the validator and the
checks belong to it. The retry requires the permissions that `CoreProposedChangeRunCheck` requires.

- A `git-repository-check-artifact-create` task retries the check of its target. That is the check
  the run names in `check_id`. When the run names none, it is the validator's check of the same
  artifact, else the validator's checks named like the target.
- An `artifacts-generation-validation` task retries every failed or unfinished check of the
  validator of its artifact definition.

Retry is offered on every finished artifact check task, not only on a failed one. The task history
reads the result of a task from the state of its run, and the flow that checks a target records a
failed render in the check and ends in a completed state. The mutation therefore reads the check and
its validator (`proposed_change/artifact_task_retry.py`), and returns an error without submitting
anything in these cases:

- The validator or the check is not found.
- The check passed, or the validator passed.
- The checks of the validator are not complete. The flow refuses a failed-only retry of such a
  validator after the mutation has returned, so the mutation refuses it first. This also refuses a
  retry while the checks of the validator are still running.
- The proposed change is not open.

The mutation returns no `task` for an artifact check retry. The request goes to a run of
`REQUEST_PROPOSED_CHANGE_PIPELINE`, an internal workflow that the task history does not list.
