# Branches

Location: `frontend/app/src/entities/branches/`

How the frontend identifies the current and default branch, and the assumptions that break when a
deployment renames its default branch.

## The default branch name is not `main`

`main` is a default, not an invariant. A deployment sets the name once at initialization through
`INFRAHUB_INITIAL_DEFAULT_BRANCH`, and the backend resolves it from configuration everywhere. The
frontend cannot know the name ahead of the API response.

Identify the default branch by the `is_default` flag on the branch, never by comparing its name to
`main` or to a constant holding `main`:

```ts
// ✅ Works on any deployment
const defaultBranch = branches.find((branch) => branch.is_default);

// ❌ Silently wrong wherever the default branch was renamed
const defaultBranch = branches.find((branch) => branch.name === "main");
```

The same applies to "am I on the default branch" checks: read `currentBranch.is_default` rather than
comparing the name.

## The branch query string parameter

The current branch lives in the URL, and the default branch is represented by the *absence* of the
branch parameter — so its pages keep clean, shareable URLs. Writing the branch means writing that
parameter; there is no separate client-side store to keep in step.
