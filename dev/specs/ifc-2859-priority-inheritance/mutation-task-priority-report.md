# Report: Mutations That Trigger Tasks — User-Impact Classification

**Branch**: `priority-work-queues-ifc-2859` | **Date**: 2026-07-05 | **Follow-up of**: [plan.md](plan.md) (classification slice, INFP-635)

## Executive summary

The priority foundation (three lanes, catalogue `default_priority`, dispatch-time override, context inheritance) is in place. Today only `BRANCH_CREATE` runs `high` among user-triggered workflows; everything else a user waits on runs `medium`, competing in the same queue as bulk background fan-outs (artifact regeneration across a group, generator runs, computed-attribute sweeps).

This report inventories every GraphQL mutation (and user-facing REST route) that dispatches a workflow, classifies each by how directly a user is affected, and recommends which dispatch roots should be flagged `high`. The strongest candidates are the **synchronous mutations where the API response blocks on the task** — branch merge/rebase/delete/validate, proposed-change merge, schema load/check, and on-demand transform renders. Because inheritance re-roots the whole task tree, flagging these roots is sufficient: their sub-workflows (git merge, IPAM reconciliation, diff refresh, migrations) inherit `high` automatically wherever a context travels.

Two dispatch sites cannot inherit today because they pass no context (`DiffUpdate` at `graphql/mutations/diff.py:105`, profile refresh at `graphql/mutations/profile.py:98`); they are called out in [Gaps](#6-gaps-that-limit-inheritance).

## 1. Impact model

A task is classified by what the user experiences while it runs:

| Class | Definition | Consequence of queueing delay |
|-------|------------|-------------------------------|
| **P1 — request-blocking** | The mutation/route holds the HTTP response open on `execute_workflow` (or `wait_until_completion` defaults to true) | The user's UI action visibly hangs; timeouts possible |
| **P2 — actively watched** | Fire-and-forget, but the user immediately watches the result in the UI (proposed-change checks page, diff view, artifact detail, generator run they just clicked) | The page the user is staring at stays stale/pending |
| **P3 — value settling** | Derived values (computed attributes, HFID, display labels, profiles) converge shortly after an edit | Brief staleness on node views; deliberate `low` today |
| **P4 — background** | Housekeeping invisible to any waiting user (webhook config, trigger re-provisioning, telemetry, cron sync, query-group updates) | None perceived |

Recommendation in one line: **P1 roots → `high`; P2 roots → `high` when dispatched from an explicit user click, otherwise `medium`; P3/P4 unchanged.**

## 2. Inventory — GraphQL mutations that dispatch workflows

`sync` = `execute_workflow` (caller blocks); `async` = `submit_workflow`. Where a mutation supports both, the flag default is noted. Current priority is the workflow's catalogue `default_priority` (`backend/infrahub/workflows/catalogue.py`).

### 2.1 Branch lifecycle (`graphql/mutations/branch.py`)

| Mutation | Workflow root | Dispatch | Current | Class | Recommend |
|----------|--------------|----------|---------|-------|-----------|
| `BranchCreate` | `BRANCH_CREATE` (branch.py:95,103) | sync by default (`wait_until_completion=True`) | **high** | P1 | keep `high` ✅ (already done) |
| `BranchMerge` | `BRANCH_MERGE_MUTATION` → `BRANCH_MERGE` (branch.py:365,371; graphql/mutations/tasks.py:39) | sync by default | medium | P1 | **`high`** |
| `BranchRebase` | `BRANCH_REBASE` (branch.py:260,269) | sync by default | medium | P1 | **`high`** |
| `BranchDelete` | `BRANCH_DELETE` (branch.py:187,192) | sync by default | medium | P1 | **`high`** |
| `BranchValidate` | `BRANCH_VALIDATE` (branch.py:310,316) | sync by default | medium | P1 | **`high`** |

Inheritance payoff: `BRANCH_REBASE` submits `IPAM_RECONCILIATION` and `DIFF_REFRESH_ALL` (core/branch/tasks.py:235,242); `BRANCH_DELETE` submits `BRANCH_CANCEL_PROPOSED_CHANGES` and `GIT_REPOSITORIES_DELETE_BRANCH` (core/branch/tasks.py:344,353); `BRANCH_MERGE_MUTATION` executes `BRANCH_MERGE` inside. All of these carry the context, so flagging the root re-roots the visible part of the tree.

Note: the post-merge follow-ups are fan-out the user does *not* block on. Implemented 2026-07-05: `PostMergeDispatcher` (core/merge/post_merge.py) dispatches each follow-up from a context stamped with its own lane instead of letting it inherit the merge's `high` — `IPAM_RECONCILIATION` from a `medium` context, and `BRANCH_CANCEL_PROPOSED_CHANGES`, `BRANCH_DELETE` (auto-delete after merge), and `BRANCH_MERGE_POST_PROCESS` (artifact/generator regeneration, core/branch/tasks.py:441-468) from a `low` context; the stamped context trickles the lane down each follow-up's entire subtree.

### 2.2 Proposed changes (`graphql/mutations/proposed_change.py`)

| Mutation | Workflow root | Dispatch | Current | Class | Recommend |
|----------|--------------|----------|---------|-------|-----------|
| `CoreProposedChangeMerge` | `PROPOSED_CHANGE_MERGE` (proposed_change.py:486,495) | sync by default | medium | P1 | **`high`** |
| `CoreProposedChangeUpdate` (state→merged) | `PROPOSED_CHANGE_MERGE` (proposed_change.py:212) | always sync | medium | P1 | **`high`** |
| `CoreProposedChangeRunCheck` | `REQUEST_PROPOSED_CHANGE_PIPELINE` (proposed_change.py:268) | async | medium | P2 (user clicked "re-run", watching checks page) | **`high` via dispatch-site override** |
| `CoreProposedChangeCreate` | `REQUEST_PROPOSED_CHANGE_PIPELINE` (proposed_change.py:138) | async | medium | P2 (user lands on the PC page next) | `medium` acceptable; `high` defensible — decide with product |

The pipeline is the deepest tree in the system (`run_proposed_change_pipeline` fans out to 7 children, proposed_change/tasks.py:1600-1705, which fan out further to generator checks, repository checks, artifact checks). Inheritance carries the lane down the whole tree, so an explicit `high` here moves substantial load into the interactive lane — that is exactly the intent for a user-clicked re-run, but for the automatic run on every PC create it is a product judgment (see §5).

### 2.3 Repositories, generators, artifacts, computed attributes

| Mutation | Workflow root | Dispatch | Current | Class | Recommend |
|----------|--------------|----------|---------|-------|-----------|
| `InfrahubRepositoryProcess` | `GIT_REPOSITORIES_IMPORT_OBJECTS` (repository.py:216) | async | medium | P2 (user-initiated re-import) | `medium` |
| `InfrahubReadOnlyRepositoryImportLastCommit` | `GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT` (repository.py:269) | async | medium | P2 | `medium` |
| `CoreReadOnlyRepositoryUpdate` (commit/ref change) | `GIT_REPOSITORIES_PULL_READ_ONLY`, `GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT` (repository.py:159,164) | async | medium | P2 | `medium` |
| `CoreGeneratorDefinitionRun` | `REQUEST_GENERATOR_DEFINITION_RUN` (generator.py:89,96) | sync by default (`wait_until_completion=True`) | medium | **P1** | **`high`** |
| `CoreArtifactDefinitionCreate/Update` | `REQUEST_ARTIFACT_DEFINITION_GENERATE` (artifact_definition.py:66,93) | async | medium | P2/P4 (bulk regeneration over a group) | `medium` |
| `DiffUpdate` | `DIFF_UPDATE` (diff.py:105) | async by default (`wait_until_completion=False`; sync path runs inline, no workflow) | medium | P2 (diff page the user opens) | `medium`–`high`; **blocked: no context passed** (§6) |
| `Profile*Create/Update/Delete` | `PROFILE_REFRESH_MULTIPLE` (profile.py:98) | async | **low** (since 2026-07-05) | P3 | done ✅; no context passed (§6) |
| `InfrahubRecomputeComputedAttribute` | `COMPUTED_ATTRIBUTE_PROCESS_{JINJA2,TRANSFORM}` or `TRIGGER_UPDATE_*` (computed_attribute.py:201,214) | async | low / medium | P3 (explicit admin-triggered recompute) | keep as-is |

### 2.4 User-facing REST routes that dispatch workflows

| Route | Workflow | Dispatch | Current | Class | Recommend |
|-------|----------|----------|---------|-------|-----------|
| `POST /api/schema/load` | `SCHEMA_VALIDATE_MIGRATION` (api/schema.py:312), then `SCHEMA_APPLY_MIGRATION` (core/schema/update_coordinator.py:330) | sync (both) | medium | P1 — schema load blocks on both | **`high`** (both) |
| `POST /api/schema/check` | `SCHEMA_VALIDATE_MIGRATION` (api/schema.py:464) | sync | medium | P1 | **`high`** (same workflow as above) |
| `GET /api/transform/python/{id}` | `TRANSFORM_PYTHON_RENDER` (api/transformation.py:94) | sync — response *is* the rendered output | medium | P1 | **`high`** |
| `GET /api/transform/jinja2/{id}` | `TRANSFORM_JINJA2_RENDER` (api/transformation.py:158) | sync | medium | P1 | **`high`** |
| `POST /api/artifact/generate/{definition_id}` | `REQUEST_ARTIFACT_DEFINITION_GENERATE` (api/artifact.py:115) | async | medium | P2 (explicit user request) | `high` via dispatch-site override, or `medium` |
| `POST/GET /api/query/{id}` with `update_group` | `GRAPHQL_QUERY_GROUP_UPDATE` (api/query.py:129) | async | **low** | P4 | keep `low` ✅ |

## 3. Mutations that trigger tasks only indirectly (events → automations)

Generic node create/update/delete mutations (`graphql/mutations/main.py:80`) and relationship mutations emit events; Prefect automations then run workflows. These are *new tree roots* — events deliberately carry no priority (`to_event_context()` boundary), so they are priced by their own catalogue defaults:

| User action | Event-triggered workflow(s) | Current | Class | Recommend |
|-------------|----------------------------|---------|-------|-----------|
| Node edits feeding computed attributes / HFID / display labels | `COMPUTED_ATTRIBUTE_PROCESS_*`, `HFID_PROCESS`, `DISPLAY_LABELS_PROCESS_JINJA2` | low | P3 | keep `low` ✅ (deliberate: value settling must not crowd the interactive lane) |
| Profile node edits | `PROFILE_REFRESH_PROCESS` | **low** (since 2026-07-05) | P3 | done ✅ — note its child `PROFILE_REFRESH` still defaults `medium` because the parent forwards only an `EventContext` (profiles/tasks.py:113), which carries no priority; see §7 |
| Node events subscribed by a webhook | `WEBHOOK_PROCESS` | medium | P4 (external observer, not a waiting user) | `medium` |
| Webhook/action-rule/schema config changes | `WEBHOOK_CONFIGURE`, `CONFIGURE_ACTION_RULES`, `*_SETUP` re-provisioning | medium | P4 | `medium` |
| Branch merged event | `BRANCH_MERGED` | medium | P4 | `medium` |
| Group membership changes matching action rules | `ACTION_RUN_GENERATOR[_GROUP_EVENT]` → `REQUEST_GENERATOR_RUN` | medium | P2/P4 | `medium` |

Cron roots (`GIT_REPOSITORIES_SYNC` every minute, `WEBHOOK_CONFIGURE` daily, `ANONYMOUS_TELEMETRY_SEND` low, `CLEAN_UP_DEADLOCKS` already high for operational reasons) are outside user-impact scope.

## 4. Recommended `high`-priority set

> **Implementation status (2026-07-05)** — the policy landed as: **a mutation dispatches `high` only on the path where the caller blocks** (`wait_until_completion=True` or an always-synchronous path); fire-and-forget paths of the same mutations keep the catalogue default. REST routes that block on the result always dispatch `high`.
>
> Done, all as dispatch-site overrides (except one catalogue change called out below):
>
> - `graphql/mutations/branch.py` — `BranchCreate`, `BranchDelete`, `BranchRebase`, `BranchValidate`, `BranchMerge` pass `priority=WorkflowPriority.HIGH` on their blocking `execute_workflow` path only.
> - `graphql/mutations/proposed_change.py` — `CoreProposedChangeMerge` (blocking path) and the always-blocking `CoreProposedChangeUpdate` state→merged path pass `high`.
> - `graphql/mutations/generator.py` — `CoreGeneratorDefinitionRun` passes `high` on its blocking path; the bulk post-merge dispatch of the same workflow is untouched.
> - `api/schema.py` — both `SCHEMA_VALIDATE_MIGRATION` dispatches pass `high`; the `SchemaUpdateCoordinator` receives a context stamped `high` so the shared component stays priority-agnostic and its other callers (merge orchestrator, CLI) are unaffected.
> - `api/transformation.py`, `api/artifact.py` — transform renders and on-demand artifact generation pass `high`.
> - `workflows/catalogue.py` — `PROFILE_REFRESH_PROCESS`, `PROFILE_REFRESH`, and `PROFILE_REFRESH_MULTIPLE` catalogue defaults lowered to `low` (P3 settling flows, consistent with computed attributes/HFID/display labels).
> - `core/merge/post_merge.py` — `PostMergeDispatcher` follow-ups no longer inherit the merge's `high`: each is dispatched from a context stamped with its own lane (`medium` for `IPAM_RECONCILIATION`; `low` for `BRANCH_CANCEL_PROPOSED_CHANGES`, `BRANCH_DELETE`, and `BRANCH_MERGE_POST_PROCESS`), which trickles down each follow-up's subtree.

### Tier A — flag now (request-blocking, unambiguous)

Every one of these holds the user's HTTP request open while the task sits in queue:

| Workflow | Where to set | Mechanism |
|----------|--------------|-----------|
| `BRANCH_MERGE_MUTATION` (+ inner `BRANCH_MERGE` inherits) | catalogue `default_priority` | root only ever dispatched by the mutation |
| `BRANCH_REBASE` | catalogue | mutation-only root |
| `BRANCH_DELETE` | catalogue | mutation-only root |
| `BRANCH_VALIDATE` | catalogue | mutation-only root |
| `PROPOSED_CHANGE_MERGE` | catalogue | dispatched from the two merge mutations only |
| `SCHEMA_VALIDATE_MIGRATION` | catalogue | dispatched only from blocking schema load/check |
| `SCHEMA_APPLY_MIGRATION` | catalogue | dispatched only from blocking schema load path |
| `TRANSFORM_PYTHON_RENDER`, `TRANSFORM_JINJA2_RENDER` | catalogue | response body is the render result |
| `REQUEST_GENERATOR_DEFINITION_RUN` | **dispatch-site override** at generator.py:89,96 | the same workflow is also a child of `TRIGGER_GENERATOR_DEFINITION_RUN` (generators/tasks.py:176) in post-merge bulk fan-out — a catalogue change would drag bulk regeneration into the interactive lane |

### Tier B — flag with a product decision (actively watched, deep fan-out)

| Workflow | Trigger | Consideration |
|----------|---------|---------------|
| `REQUEST_PROPOSED_CHANGE_PIPELINE` | `CoreProposedChangeRunCheck` (explicit re-run): **override `high` at proposed_change.py:268** | User clicked a button and is watching the checks page; tree is deep, so this moves real load into `high` |
| same | `CoreProposedChangeCreate` (automatic on create): keep `medium` initially | Every PC create would otherwise run its whole pipeline `high`; revisit with queue metrics |
| `REQUEST_ARTIFACT_DEFINITION_GENERATE` | `POST /api/artifact/generate` only: override at api/artifact.py:115 | Explicit user request vs. the same workflow's bulk post-merge role |
| `DIFF_UPDATE` | `DiffUpdate` mutation | Blocked on the context gap below; fix first |

### Deliberately not `high`

- All P3 settling flows (computed attributes, HFID, display labels, profiles) — the existing `low` classification is correct and load-bearing: these are the highest-volume trees in the system.
- Repository import/pull mutations — user-initiated but conventionally minutes-long git work; `high` would let one repo import starve genuinely interactive tasks.
- `BRANCH_MERGE_POST_PROCESS` and its artifact/generator fan-out — the user's merge already returned; regeneration is P4.
- Everything event-triggered — events are a deliberate priority boundary; their workflows are roots priced by their own defaults.

## 5. How to flag: catalogue default vs. dispatch-site override

The foundation gives two levers, and picking the right one per workflow matters:

1. **Catalogue `default_priority=HIGH`** — right when the workflow is *only ever* a user-blocking root (all Tier A rows marked "catalogue"). Simple, visible in one file, and the deployment's queue moves with it.
2. **Explicit `priority=WorkflowPriority.HIGH` at the dispatch site** — right when the same workflow serves both an interactive path and a bulk path (`REQUEST_GENERATOR_DEFINITION_RUN`, `REQUEST_PROPOSED_CHANGE_PIPELINE` re-run, artifact generate route). The override is stamped into the context and re-roots the subtree, while the bulk path keeps the catalogue default.

Either way, inheritance does the rest: every sub-dispatch that carries an `InfrahubContext` lands in the same lane (exact inheritance — a `high` root runs its catalogue-`low` children `high`, which is intended for these short interactive trees).

## 6. Gaps that limit inheritance

1. **`DiffUpdate` passes no context** (`graphql/mutations/diff.py:105`, a documented root exemption in [research.md](research.md) D5). Before `DIFF_UPDATE` can be prioritized as a user-watched task, the mutation should pass `context=graphql_context.get_context()` like every other mutation dispatch.
2. **Profile refresh passes no context** (`graphql/mutations/profile.py:98`) and `objects_profiles_refresh_multiple` has no context parameter (profiles/tasks.py:51) — acceptable while profiles remain P3, but worth fixing if that changes.
3. **Flows without an `InfrahubContext` parameter** stop the chain (research.md D5 exemptions: `repository_merge_dispatcher.py:65,92`, `branch_differ.py:159`). For Tier A trees this matters for `BRANCH_MERGE`'s repository merge sub-dispatches — the child run itself is routed correctly at its dispatch site only if a stamped context or explicit priority reaches that site. Worth a depth audit when implementing Tier A for merge specifically.

## 7. Remaining work and open discussion points

Implemented so far (see the status note in §4): blocking-path `high` overrides on all branch mutations, proposed-change merge, generator-definition run, schema load/check, transform renders, on-demand artifact generation; `PROFILE_REFRESH_PROCESS` lowered to `low`.

Still open — needs a decision or further work:

1. **Async paths of blocking mutations stay `medium` (decided policy — record and revisit if needed).** When a caller passes `wait_until_completion=false`, the same mutation dispatches with no priority signal and lands on the catalogue default. This is deliberate: no one is blocked on the result. If SDK users complain that async branch merges queue behind bulk work, the per-path split is one line to change.
2. **`REQUEST_PROPOSED_CHANGE_PIPELINE` lane** — two sub-decisions:
   - Explicit re-run (`CoreProposedChangeRunCheck`, proposed_change.py:268): the user clicked a button and is watching the checks page, but the dispatch is async. Under the current "high only when blocking" policy it stays `medium`. If check latency on re-run becomes a complaint, this is the first candidate for an exception to the policy.
   - Automatic run on `CoreProposedChangeCreate`: keep `medium` until queue-contention metrics exist; the pipeline is the deepest tree in the system and would move substantial load into the interactive lane.
3. **`DiffUpdate` cannot participate** — the dispatch at diff.py:105 passes no context (documented root exemption, research.md D5). Fix the context first, then decide whether the diff page qualifies as watched-enough for `high`.
4. ~~Profile refresh lane is split mid-tree~~ — resolved 2026-07-05: `PROFILE_REFRESH` and `PROFILE_REFRESH_MULTIPLE` catalogue defaults lowered to `low`, so the whole profile-refresh family (`PROFILE_REFRESH_PROCESS`, `PROFILE_REFRESH_MULTIPLE`, `PROFILE_REFRESH`) now runs in the settling lane regardless of the `EventContext` inheritance boundary at profiles/tasks.py:113.
5. **Integration coverage for the new overrides** — extend `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py` with an assertion that a blocking `BranchMerge` root lands its tree in `high` while a post-merge `TRIGGER_GENERATOR_DEFINITION_RUN` tree still lands `medium`, pinning the interactive/bulk split of the shared generator workflow.

## Appendix — current non-default catalogue priorities

- **high**: `BRANCH_CREATE`, `CLEAN_UP_DEADLOCKS`
- **low**: `ANONYMOUS_TELEMETRY_SEND`, `GRAPHQL_QUERY_GROUP_UPDATE`, `COMPUTED_ATTRIBUTE_PROCESS_JINJA2`, `COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE`, `DISPLAY_LABELS_PROCESS_JINJA2`, `DISPLAY_LABEL_JINJA2_UPDATE_VALUE`, `HFID_PROCESS`, `HFID_SETUP`, `HFID_UPDATE_VALUE`, `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM`, `PROFILE_REFRESH_PROCESS`, `PROFILE_REFRESH`, `PROFILE_REFRESH_MULTIPLE` (added 2026-07-05)
- **medium**: all remaining (~70) definitions, via the model default (`workflows/models.py:50`)
