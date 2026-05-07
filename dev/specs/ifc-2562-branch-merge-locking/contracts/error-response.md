# Contract — `BRANCH_LOCKED` Error Response (externally visible)

A new error surfaces on existing GraphQL and REST write endpoints when a caller attempts a write against a branch held by an in-progress merge. This is the only externally-visible contract change introduced by this feature.

## GraphQL

When `BranchLockedError` is raised inside a mutation resolver, the framework converts it to a standard GraphQL error in the response.

**Sample response body**:

```json
{
  "errors": [
    {
      "message": "Branch 'feature-billing' is currently being merged; retry once the merge completes.",
      "extensions": {
        "code": "BRANCH_LOCKED_FOR_MERGE",
        "branch": "feature-billing"
      }
    }
  ],
  "data": null
}
```

**Fields**:
- `extensions.code`: `BRANCH_LOCKED_FOR_MERGE` — stable string clients can match on.
- `extensions.branch`: the affected branch name. Clients use this to scope retries.
- `message`: user-facing English. Format may evolve; do not parse.

## REST

When `BranchLockedError` is raised inside a REST handler, the response is HTTP 409 Conflict.

**Sample response**:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "detail": "Branch 'feature-billing' is currently being merged; retry once the merge completes.",
  "code": "BRANCH_LOCKED_FOR_MERGE",
  "branch": "feature-billing"
}
```

## `MergeWriteDrainTimeoutError`

This error is raised inside the merge flow itself, not in response to a user write. It surfaces in the response of the merge mutation (`BranchMerge`) or in the Prefect flow run UI when the merge is submitted asynchronously.

**Sample GraphQL response**:

```json
{
  "errors": [
    {
      "message": "Merge could not start: writes on ['feature-billing', 'main'] did not complete within 30s. Branches have been released; retry the merge.",
      "extensions": {
        "code": "MERGE_WRITE_DRAIN_TIMEOUT",
        "branches": ["feature-billing", "main"],
        "timeout_seconds": 30
      }
    }
  ],
  "data": null
}
```

**HTTP status when surfaced via REST**: 503 Service Unavailable (the merge could not run; retry is appropriate).

## Client guidance

Clients receiving `BRANCH_LOCKED_FOR_MERGE`:
- The merge will complete or fail on a bounded timescale (drain timeout default 30 s; merge body itself bounded by deployment-specific factors).
- Retry the original mutation/REST call after a short backoff (suggested: 1–5 seconds, with jitter).
- Do not loop indefinitely; surface the error to the originating user after a reasonable retry budget.

Clients receiving `MERGE_WRITE_DRAIN_TIMEOUT`:
- The merge did not start; no partial state was applied.
- The branch is back in `OPEN` status and is writable.
- Investigate which writer was holding the branch (typically a long-running background flow); retry the merge once that writer completes or is cancelled.

## Backwards compatibility

- New error code; not previously used. Clients that don't recognize `extensions.code` see the human-readable `message` (already standard GraphQL behavior).
- HTTP 409 was previously unused on the affected endpoints. Generic HTTP clients that retry on 5xx but not 4xx will *not* automatically retry; this is intentional — clients should observe the error and decide.
