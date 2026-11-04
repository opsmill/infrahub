# Contract: What an operator observes in the task manager

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)

This change adds no API, GraphQL field, REST endpoint, CLI option or event. It changes the observable output of three existing flows. That output is listed below so that tests and reviewers can check it.

## Task runs per flow run

| Flow run | Before | After |
|----------|--------|-------|
| `computed-attribute-setup-python`, branch deletion | 4 + 2 per branch that is not global | 4 |
| `computed-attribute-setup-python`, schema update | 4 + 2 per branch, plus one per recompute the run submits | 4, plus one per recompute the run submits |
| `computed-attribute-process-transform-lifecycle`, delete | 3 + 1 per branch that is not global | 3 |
| `computed-attribute-process-transform-lifecycle`, create or update | 3 + 1 per branch, plus one per recompute the run submits | 3, plus one per recompute the run submits |
| `trigger-configure-all` (`infrahub upgrade`) | the other gathers + 2 + 1 per branch | the other gathers + 2 |

The figures come from reading the code (research R2). In production, each submitted recompute adds one task run through `run_deployment`, and their number depends on the attributes selected, not on the number of branches. The tests check only that the count does not change with the number of branches.

## Task-run names that no longer appear

- `Gather Python transform attributes for <branch>`. The task name was `gather-python-transform-attributes`.

## Log messages

| Condition | Level | Message after the change |
|-----------|-------|--------------------------|
| A Python computed attribute on branch `<branch>` names a transform that the query on `<branch>`, which filters by name, does not return | WARNING | `No Python transform named '<transform>' was found on branch '<branch>', but a computed attribute is assigned to it.` |
| Gathering fails on branch `<branch>` | ERROR, and the run fails | The original exception is unchanged. Its note is printed at the end of the traceback in the run's error log line: `Gathering the Python computed attributes failed on branch '<branch>'` |

- The missing-transform warning used to read `The transform <transform> is assigned to a computed attribute but the transform could not be found in the database.`, and it appeared under the per-branch task run.
- An attribute wired to its transform by UUID still triggers the warning, because the query filters by name. This change does not alter that.
- The run's state message keeps the original error text, for example `LookupError: Unable to find the peer`. It does not include the note.

## Unchanged

- The parameters of every flow listed above.
- The names, triggers, actions and branch filters of the node-input automations.
- The lock name and namespace of the reconcile (`configure-action-rules-computed-attr-python`, `trigger-rules`).
- The type of any exception that a failed gather raises.
