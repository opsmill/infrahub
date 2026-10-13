# Repository Commits tab

> Part of: `dev/knowledge/frontend/` | Related: [Entities Structure](entities-structure.md), [Date Rendering](date-rendering.md), [Repository Git-State Read](../backend/repository-git-state.md)

How the Commits tab of a repository's detail page reads the commit log, waits for a worker that has
no clone yet, and shows how fresh the log is. Source: `frontend/app/src/entities/repository/`. The
backend side, including where each value comes from, is in
[Repository Git-State Read](../backend/repository-git-state.md).

## The `api/ -> domain/ -> ui/` chain

Each layer follows [Entities Structure](entities-structure.md):

- `api/get-repository-commits-from-api.ts`: the `REPOSITORY_COMMITS` GraphQL query on
  `InfrahubRepositoryCommits`. It asks for `pending_count` on the first page only
  (`@include(if: $isFirstPage)`), which is the page the tab label reads it from. It turns off the
  global error toast, because failures render inside the tab and the same request also runs on
  pages that do not show commits.
- `api/repository-commits.mappers.ts`: `mapToRepositoryCommitLog` turns the wire answer into the
  domain `RepositoryCommitLog` and checks that every `DateTime` value is a string.
- `domain/use-cases/get-repository-commits.ts`: `getRepositoryCommits` throws an `Error` that joins
  the GraphQL error messages, and throws `RepositoryGitUnavailableError`
  (`domain/model/repository-git-unavailable-error.ts`) when the answer's condition is `UNAVAILABLE`.
  The typed error carries the reason and the whole log, so the UI can still render the header from
  it.
- `domain/rules/should-retry-git-unavailable.ts` decides which unavailable reasons are worth a retry,
  and `domain/rules/get-pending-import-count.ts` derives the number on the tab label.
- `ui/queries/get-repository-commits.query.ts`: the infinite query and its retry policy.
- `ui/repository-commits.view.ts`: pure functions that turn query state into what the tab shows. Put
  new display decisions here, where they can be unit-tested without rendering.
- `ui/repository-commits-manager.tsx` renders the tab body, and `ui/repository-commits-header.tsx`
  renders the refresh button, the freshness line, the condition notice and, for a read-only
  repository, the **Check remote now** button.
- `ui/repository-commits-tab.tsx` renders the tab label. It uses the same query with `select` on the
  first page, so the label count and the list share one request and one retry loop.

The route component `pages/objects/object-details/repository-commits.tsx` mounts the manager, and
`entities/nodes/object/ui/object-details/object-details-tabs.tsx` mounts the tab label.

The query key `repositoriesQueryKeys.commits` is built on `repositoriesQueryKeys.repository` for the
repository and the current branch. The refresh button invalidates that repository key, and so does
the poll of a remote check task when the task ends, which reloads the log with the new `checked_at`.

## Waiting for a worker: the capped retry

A worker that holds no clone yet answers `UNAVAILABLE` with the reason `NOT_CLONED` and starts a
warm-up. The tab waits for the clone with the query's `retry` option, not with `refetchInterval`:

- `retry` retries while the error is a `RepositoryGitUnavailableError` whose reason is not
  `NOT_IMPLEMENTED`, up to `REPOSITORY_COMMITS_MAX_RETRIES` retries, `REPOSITORY_COMMITS_RETRY_DELAY_MS`
  apart (`ui/queries/repository-commits.constants.ts`), so the tab waits at most the product of the
  two.
- The retries are capped because a clone that keeps failing keeps answering `NOT_CLONED`.
- A worker timeout reaches the tab as a GraphQL error, not as an unavailable answer, so it is not
  retried and the tab shows the error screen with a refresh button.
- While TanStack Query retries, `error` stays null and the last failure is in `failureReason`. The
  view functions read both. `getEmptyState` changes its message once retrying stops, and asks the
  user to refresh.

`refetchOnWindowFocus` is off and `staleTime` is set, because every loaded page is a worker round trip
and a refetch replays all of them.

## A failed refresh keeps the loaded rows

Each refresh can be answered by a different worker. A worker that has no clone answers `UNAVAILABLE`,
which the use case throws like any other failure. Without this rule, one such answer would replace a
populated list with an empty state.

- When a refetch fails, TanStack Query keeps the loaded pages and sets `isRefetchError`. The manager
  renders the rows whenever a first page exists, and `isShowingStaleCommits` adds a notice that the
  rows are the last loaded ones. The same notice shows while a refetch is being retried.
- `canLoadOlderCommits` stops infinite scroll while a refresh runs or after it failed. Older pages are
  read by offset into the current history, so appending them to an out-of-date first page would mix
  two histories.
- `getLoadedCommits` removes duplicate commits by hash, because offset paging over a log that moved
  can return the same commit at a page boundary.
- A failed older page shows a **Retry** notice under the table. `getNextPageState` shows the button
  as pending while the query still retries on its own, because pressing it would cancel that retry.

## Where the two freshness values render

Both values render in one place: the freshness line in the Commits tab header, `FreshnessLine` in
`ui/repository-commits-header.tsx`. `getFreshness` in `ui/repository-commits.view.ts` decides what it
shows:

- **Tracking**: the git ref the branch reads.
- **Checked**: `checked_at`, the time the last read-only refs check ended, whether it succeeded or
  failed (see [Repository Git-State Read](../backend/repository-git-state.md)). The backend
  returns null for a read-write repository, so the label does not appear there.
- **Updated**: `fetched_at`, the time the answering worker's clone last fetched. `getFreshness` hides
  it when the string is exactly equal to `checked_at`. The backend takes the two times at different
  moments (the `FETCH_HEAD` modification time, and the check's end), so in practice both show.

Each time renders through `DateDisplay` with `fullTimestamp` (see [Date Rendering](date-rendering.md)).
The header also renders above the empty states: above the unavailable state from the log that the
typed error carries, and above the "no commit log" state from the first loaded page's log. No frontend code reads `InfrahubRepositoryBranchDrift`, so neither value renders
anywhere else.
