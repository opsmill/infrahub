# Spec review — round 2 (approved)

**Feature**: internal & scheduled background flows in the Tasks view (`infp-68`)
**Artifact**: [spec.md](../spec.md) at commit `227f1062a`
**Outcome**: approved

## Round-1 required changes — all applied and re-verified

Each claim was checked against the worktree, not taken from the author's summary.

1. **Tagging premise corrected.** `add_tags()` defaults `namespace: bool = True`
   (`backend/infrahub/workflows/utils.py:27`, docstring at `:38`). Resolving all
   19 `INTERNAL` catalogue entries to their flow functions confirms exactly the
   eight the spec lists call it with that default, and `graphql-query-group-update`
   (`backend/infrahub/groups/tasks.py:22`) is the only `namespace=False` opt-out.
   The new **Two different tags, doing two different jobs** section states this
   correctly, and FR-003 now defines the default by observed result and forbids
   the "no internal runs are returned" phrasing that would have encoded the
   regression into SC-005.

   The spec also adds a consequence round 1 did not name: because the tag is
   written from inside the running flow, even those eight are invisible when a
   run crashes on start, is cancelled by a `CANCEL_NEW` collision, or never
   leaves `Scheduled`. That is correct and strengthens the case for the facet.

2. **Decision recorded.** Assumption 18 keeps the eight in the default list;
   FR-029 pins it by forbidding any change to an `add_tags()` call site or its
   `namespace` argument. Reconciling the two tagging mechanisms is an explicit
   Out of Scope entry.

3. **FR-004 rewritten and now satisfiable.** Confirmed on the installed Prefect
   3.8.6 that `FlowRunFilterTags` exposes only `all_`, `any_`, `is_null_`,
   `operator` — no negation. FR-002 makes the namespace requirement conditional
   rather than removed, which is expressible; FR-004 now pins the asymmetry
   between the default and an explicit all-types selection.

   Additionally verified that FR-002 composes with FR-005: `all_` and `any_` are
   independent fields on the same filter and are ANDed server-side, so
   "any of these type tags" AND "this branch tag" is expressible. Multi-type
   selection alongside branch/node narrowing is not a repeat of the FR-004 trap.

All four non-blocking round-1 items were also applied (delivery-independence
subsection, SC-006 scoped to client→backend requests with SC-007 split out,
"never run" vs "history purged" separated by deployment creation time against
the 30-day retention default, success criteria renumbered).

## Re-verified inventory

- 19 `INTERNAL` workflows of 86 total.
- 5 scheduled: `git_repositories_sync`, `clean-up-deadlocks`, `merge-watcher`
  (all `* * * * *`, concurrency 1, `CANCEL_NEW`), `anonymous_telemetry_send`
  (`{random.randint(0,59)} 2 * * *`), `webhook-configure`
  (`{random.randint(0,59)} 3 * * *`, `ENQUEUE`).
- None of the five calls a tagging helper in its own flow body.

## Non-blocking notes for the planning phase

- **A nested flow already surfaces some git-sync failures.**
  `sync-git-repo-with-origin` (`backend/infrahub/git/tasks.py:213`) is a nested
  `@flow`, not a catalogue deployment, reached from `git_repositories_sync` via
  `sync_repository_from_origin`. On `RepositoryError`/`CommitNotFoundError` it
  calls `add_tags(**params)` with the default namespace (`:243`), so that child
  run appears in the default Tasks list. It does not change any requirement —
  the tag lands on the child run, not on the `git_repositories_sync` run, and
  the `CANCEL_NEW` stall this feature targets produces no child run at all — but
  the planner should expect an existing "Sync git repo with origin" task in the
  list and not treat it as the parent's visibility.
- **Both randomised crons are evaluated at module import** (`random.randint`,
  `catalogue.py:57` and `:552`), so the deployment's stored schedule, not the
  catalogue expression, is the source of truth for what to render. The spec's
  edge case already requires the configured schedule; worth making explicit in
  the plan.
- FR-009's "count of recent runs broken down by outcome" should reuse
  `FlowRunCounter` (`backend/infrahub/task_manager/flow_run/count.py`) rather
  than a new aggregation path, per Assumption 14.

## Assessment against the ticket's acceptance criteria

| Ticket criterion | Covered by |
|---|---|
| Internal/scheduled flows viewable via Type filter and/or System tab | FR-014, FR-020 |
| Name, type, schedule, latest run state + timestamp, link to logs | FR-015, FR-017, FR-018 |
| Recurring flows show schedule + recent outcomes incl. failed/cancelled | FR-009, FR-011, FR-016 |
| Default Tasks list unchanged | FR-003, FR-021, SC-005, FR-029 |
| Filter driven by the workflow-type tag, not a hardcoded namespace requirement | FR-002, Assumption 19 |

No `[NEEDS CLARIFICATION]` markers. 34 functional requirements, 11 success
criteria, 19 assumptions, all traceable. Ready for planning.
