Internal background flows are now visible in the web UI. Previously the Tasks list could only ever
show `core` and `user` workflows, because its Prefect filter always required the `infrahub.app` tag,
which internal workflows never carry — so a scheduled job such as `git_repositories_sync` or
`clean-up-deadlocks` gave no signal in the product when it stalled.

Two things are new:

* **Tasks → View scheduled flows** (`/tasks/scheduled`) lists every workflow that runs on a schedule
  with its cadence, a health verdict (`Healthy`, `Failed`, `Cancelled`, `Overdue`, `Never run`,
  `No recent runs` or `Paused`), the outcome of its most recent run, and a breakdown of every run
  outcome over the last 24 hours. Each row links to that workflow's runs, with no state filter
  applied so failed and cancelled runs are included. Verdicts are shown as an icon and a word, never
  colour alone, and the list puts the flows needing attention first. Data is cached for up to a
  minute and refreshed on demand rather than polled.
* Opening an individual run now works for internal runs too. The task detail page looked runs up
  under the same namespace-tag scope as the list, so an internal run reported "Task with ID … not
  found"; a run addressed by its own id is now resolved whatever its type.
* A **Type** filter on the Tasks list, with internal workflows labelled "System". Over GraphQL this
  is the new `workflow_type: [WorkflowTypeEnum]` argument on `InfrahubTask`, alongside a new
  `workflow_type` field on each returned run and a new `InfrahubScheduledFlows` query. With no type
  requested the list, the count and the branch-status query are all exactly what they were before.
