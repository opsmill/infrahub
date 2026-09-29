# Contract: GraphQL reads

No new backend field. Every document below runs against the existing schema (`schema/schema.graphql`) and is written with `gql.tada` in an entity `api/` file. The `branch` is always the **page's** branch (`/branches/:branchName`), passed as the request's branch context (`graphqlClient.query({ context: { branch } })`) or as the `branch` argument, never the branch selector's current branch.

## Q1 — Repositories on a branch

File: `frontend/app/src/entities/repository/api/get-branch-repositories-from-api.ts`

```graphql
# $kind resolves to CoreGenericRepository (Sync with Git on) or CoreReadOnlyRepository (off).
# Two static documents, one per kind, so gql.tada types both; same selection.
query GetBranchRepositories($limit: Int!) {
  CoreGenericRepository(limit: $limit) {
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

- Context: `{ branch: branchName }`. Variables: `{ limit: REPOSITORY_FETCH_LIMIT }` (500).
- `CoreGenericRepository` declares `commit`, `name`, `sync_status` and `operational_status` itself (checked in `schema/schema.graphql`), so no inline fragments are needed.
- Errors: `PERMISSION_DENIED` → `{ status: "denied" }`; anything else throws.
- Query key: `repositoryQueryKeys.branch({ branchName, kind })`. `refetchInterval: 10_000`.

## Q2 — Latest import task of one repository, with logs

File: `frontend/app/src/entities/repository/api/get-repository-import-task-from-api.ts` (lives in `repository` because the answer is about a repository; it doesn't import from `tasks/api`).

```graphql
query GetRepositoryImportTask(
  $branch: String!
  $repositoryId: String!
  $workflows: [String]!
  $logLimit: Int!
) {
  InfrahubTask(
    branch: $branch
    related_node__ids: [$repositoryId]
    workflow: $workflows
    limit: 1
    log_limit: $logLimit
  ) {
    count
    edges {
      node {
        id
        state
        updated_at
        logs { edges { node { message severity timestamp } } }
      }
    }
  }
}
```

- Variables: `{ branch, repositoryId, workflows: IMPORT_WORKFLOWS, logLimit: IMPORT_LOG_LIMIT }`.
- Issued only for rendered bands (≤ 3 until "Show all").
- Query key: `repositoryQueryKeys.importError({ branchName, repositoryId })`. `refetchInterval: 10_000`.
- Known gap: see research R2 (import-object and periodic sync tagging). A miss yields `not-found`, never an error state.

## Q3 — Tasks page on a branch

Reuses `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts::GET_TASK_LIST` unchanged:

- Variables: `{ branchName, offset: (page - 1) × 10, limit: 10 }`.
- New use case `getBranchTasks` returns `{ tasks, count }` from `InfrahubTask.count` and `edges`.
- Query key: `tasksQueryKeys.branchList({ branchName, offset, limit })`. `refetchInterval: 10_000`, `placeholderData: keepPreviousData` (the table doesn't flash to loading between pages).

## Q4 — Failed tasks on a branch

Reuses `frontend/app/src/entities/tasks/api/get-task-count-from-api.ts::TASK_COUNT` via `getTaskCount`:

- Variables: `{ branchName, state: ["FAILED", "CRASHED"] }`.
- Query key: `tasksQueryKeys.count({ branchName, state })`. `refetchInterval: 10_000`.

## Refresh

Header `RefreshButton queryKeys={[branchesQueryKeys.details({ branchName }), repositoryQueryKeys.all, tasksQueryKeys.all]}` invalidates Q1–Q4 and the branch details.

## Request budget per page view

1 (branch details, existing) + 1 (Q1) + ≤ 3 (Q2, lazily more) + 1 (Q3) + 1 (Q4). Constant in the number of repositories and tasks.
