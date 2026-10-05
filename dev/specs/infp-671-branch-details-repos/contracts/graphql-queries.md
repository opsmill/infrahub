# Contract: GraphQL reads

No new backend field. Every document below runs against the existing schema (`schema/schema.graphql`) and is written with `gql.tada` in an entity `api/` file. The `branch` is always the **page's** branch (`/branches/:branchName`), passed as the request's branch context (`graphqlClient.query({ context: { branch } })`) or as the `branch` argument, never the branch selector's current branch. No api file imports `@urql/core`; errors are left to the use cases.

> **2026-10-02, restructure.** Q1 used to fetch up to 500 repositories for client ranking, slicing and polling; it is now a server page (Q1) plus a server-filtered health query (Q1b). Q2 used to take the newest task with up to 10,000 log lines on every poll; it now asks for the newest *failed* task (Q2) and fetches its log once (Q2b). Q5 is new.

## Q1 — One page of the branch's repositories

File: `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`

```graphql
# Two static documents, one per list kind (CoreGenericRepository when Sync with Git is on,
# CoreReadOnlyRepository when off), so gql.tada types both; same selection.
query GET_BRANCH_REPOSITORIES($limit: Int!, $offset: Int!) {
  CoreGenericRepository(
    limit: $limit
    offset: $offset
    order: { by: [{ field: "name__value", direction: ASC }] }
  ) {
    count
    edges {
      node {
        id
        __typename
        display_label
        name { value }
        commit { value }
        sync_status { value label color description }
        operational_status { value label color }
      }
    }
  }
}
```

- Context: `{ branch: branchName }`. Variables: `{ limit: PAGE_SIZE, offset: getOffset(page, PAGE_SIZE) }`.
- `order` is `OrderInput { by: [OrderByItem { field, direction }] }` (checked in `schema/schema.graphql`).
- Errors: a `PERMISSION_DENIED` catalogue code → `BranchRepositoriesError("PERMISSION_DENIED")` (the no-access state); anything else → `"UNKNOWN"` (the failed state).
- Query key: `repositoryQueryKeys.branchRepositories({ branchName, syncWithGit, limit, offset })`. `refetchInterval`: 10s while `isAnyRepositorySyncing(health)` (Q1b), else off. `placeholderData`: the previous page while the same branch and list load the next one.

## Q1b — Failing and syncing repositories on the branch

File: `frontend/app/src/entities/repository/api/get-branch-repository-health-from-api.ts`

```graphql
# GraphQL can't OR two attribute filters, so failed imports and unreachable repositories are two
# aliased lists in one request; the rule getFailingRepositories deduplicates them.
query GET_BRANCH_REPOSITORY_HEALTH(
  $importErrorStatuses: [String]!
  $unreachableStatuses: [String]!
  $syncingStatuses: [String]!
) {
  importErrors: CoreGenericRepository(
    sync_status__values: $importErrorStatuses
    order: { by: [{ field: "name__value", direction: ASC }] }
  ) { count edges { node { …same selection as Q1… } } }
  unreachable: CoreGenericRepository(
    operational_status__values: $unreachableStatuses
    order: { by: [{ field: "name__value", direction: ASC }] }
  ) { count edges { node { …same selection as Q1… } } }
  syncing: CoreGenericRepository(sync_status__values: $syncingStatuses) { count }
}
```

- Same two-kind split as Q1. Variables: `{ importErrorStatuses: ["error-import"], unreachableStatuses: REPOSITORY_OPERATIONAL_ERRORS, syncingStatuses: ["syncing"] }`. `__values` is an exact-match list filter (checked on a live stack).
- `limit: REPOSITORY_HEALTH_LIST_LIMIT` (50) on each list, with its `count`. Failures past the limit have no band; the summary line counts them from the server's `count` ("and N more"), without double-counting a repository that fails both ways.
- Independent of the table page: feeds the bands and decides polling for Q1, Q1b and Q2.
- Query key: `repositoryQueryKeys.branchHealth({ branchName, syncWithGit })`. `refetchInterval`: 10s while `syncing.count > 0`.

## Q2 — The newest failed import of one repository

File: `frontend/app/src/entities/repository/api/get-repository-import-task-from-api.ts`

```graphql
query GET_REPOSITORY_FAILED_IMPORT_TASK(
  $branch: String!
  $repositoryId: String!
  $workflows: [String]!
  $states: [StateType]!
) {
  InfrahubTask(
    branch: $branch
    related_node__ids: [$repositoryId]
    workflow: $workflows
    state: $states
    limit: 1
  ) {
    edges { node { id } }
  }
}
```

- Variables: `{ branch, repositoryId, workflows: IMPORT_WORKFLOWS, states: ["FAILED", "CRASHED"] }`. The task manager returns runs newest first, so this is the newest *failed* import, not the newest import.
- Issued only for rendered bands (≤ 3 until "Show all": hidden bands aren't mounted).
- Query key: `repositoryQueryKeys.importTask({ branchName, repositoryId })`. `refetchInterval`: 10s while a repository is syncing.
- Known gaps (follow-ups.md): a failure before the run is tagged with the repository, and the worker-bootstrap import, aren't findable. A miss yields `not-found`, never an error state.

## Q2b — That task's log

Same file.

```graphql
query GET_IMPORT_TASK_LOGS($taskId: String!, $logLimit: Int!) {
  InfrahubTask(ids: [$taskId], log_limit: $logLimit) {
    edges { node { logs { edges { node { message severity } } } } }
  }
}
```

- Variables: `{ taskId, logLimit: IMPORT_LOG_LIMIT }`. Logs come back oldest first with no tail option, so the limit stays at the backend cap.
- Query key: `repositoryQueryKeys.importLog(taskId)`, `staleTime: Infinity`, no `refetchInterval`, enabled only once Q2 found a task. A finished task's log doesn't change: it is fetched once per task, and again only when Q2 returns another task id.

## Q3 — Tasks page on a branch

Reuses `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts::GET_TASK_LIST` unchanged:

- Variables: `{ branchName, offset: getOffset(page, PAGE_SIZE), limit: PAGE_SIZE }`.
- Use case `getBranchTasks` returns `{ tasks, count }` from `InfrahubTask.count` and `edges`.
- Query key: `tasksQueryKeys.branchList({ branchName, offset, limit })`. `refetchInterval: offset === 0 ? 10_000 : false` (later pages don't shift under the reader); `placeholderData`: the previous page within the same branch.

## Q4 — Failed tasks on a branch

Reuses `frontend/app/src/entities/tasks/api/get-task-count-from-api.ts::TASK_COUNT` via `getTaskCount`:

- Variables: `{ branchName, state: ["FAILED"] }`. FAILED only: the Tasks page filters on a single state, so the count matches what its link opens.
- Query key: `tasksQueryKeys.count({ branchName, state })`. `refetchInterval: 10_000`.

## Q5 — Names of the repositories on the tasks page shown

File: `frontend/app/src/entities/repository/api/get-repository-names-from-api.ts`

```graphql
query GET_REPOSITORY_NAMES($ids: [ID]!) {
  CoreGenericRepository(ids: $ids) {
    edges { node { id display_label name { value } } }
  }
}
```

- Context: `{ branch: branchName }`. Variables: the sorted, unique related node ids of the Q3 page (`getRelatedNodeIds`). Ids of other kinds simply don't come back; those cells keep the kind label.
- Query key: `repositoryQueryKeys.names({ branchName, ids })`; disabled when the page has no related node.
- Replaces the Tasks card's second read of the whole repository list.

## Query keys

`repositoryQueryKeys.all` is `["repository"]`, the root IFC-3130 (`branchStatus`) and IFC-3199 (`syncHealth`) use. This PR's `repository.query-keys.ts` keeps IFC-3199's `syncHealth` verbatim and adds `branchRepositories`, `branchHealth`, `importTask`, `importLog` and `names`.

## Refresh

Header `RefreshButton queryKeys={[branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all]}` invalidates every query above and every branch query; its "Last data refresh" time reads only those keys' active queries.

## Request budget per page view

1 (branch details, existing) + 1 (Q1) + 1 (Q1b) + ≤ 3 (Q2) + ≤ 3 (Q2b, once per task) + 1 (Q3) + 1 (Q4) + ≤ 1 (Q5). Constant in the number of repositories and tasks. A page past the end costs one more Q1 or Q3 request (the clamp).
