# Contract: What an operator observes in the task manager

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)

This change adds no API, GraphQL field, REST endpoint, CLI option or event. It changes the observable output of three existing flows. That output is listed below so that tests and reviewers can check it.

## Task runs per flow run

| Flow run | Before | After |
|----------|--------|-------|
| `computed-attribute-setup-python`, any event | 4 + 2 per branch that is not global | 4 |
| `computed-attribute-process-transform-lifecycle`, delete | 3 + 1 per branch that is not global | 3 |
| `computed-attribute-process-transform-lifecycle`, create or update | 3 + 1 per branch, plus the recompute submission's tasks | 3, plus the recompute submission's tasks |
| `trigger-configure-all` (`infrahub upgrade`) | the other gathers + 2 + 1 per branch | the other gathers + 2 |

The figures come from reading the code (research R2). The tests check only that the count does not change with the number of branches.

## Task-run names that no longer appear

- `Gather Python transform attributes for <branch>`. The task name was `gather-python-transform-attributes`.

## Log messages

| Condition | Level | Message after the change |
|-----------|-------|--------------------------|
| A Python computed attribute on branch `<branch>` names a transform that the query on `<branch>` does not return | WARNING | `The transform <transform> is assigned to a computed attribute on branch '<branch>' but the transform could not be found on that branch.` |
| Gathering fails on branch `<branch>` | The run fails. The original exception is unchanged, and its note is printed with the traceback in the run's log | Note: `Gathering the Python computed attributes failed on branch '<branch>'` |

The missing-transform warning used to read `The transform <transform> is assigned to a computed attribute but the transform could not be found in the database.`, and it appeared under the per-branch task run.

## Unchanged

- The parameters of every flow listed above.
- The names, triggers, actions and branch filters of the node-input automations.
- The lock name and namespace of the reconcile (`configure-action-rules-computed-attr-python`, `trigger-rules`).
- The type of any exception that a failed gather raises.
