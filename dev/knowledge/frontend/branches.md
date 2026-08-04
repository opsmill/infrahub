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

## Why name comparisons survive review

Every development stack, test fixture and both end-to-end suites run with the default configuration,
so a name comparison behaves identically to the flag in every environment a change is normally
exercised in. The failure only appears on a renamed deployment, where it can be severe — a
name-comparison guard in a provider once left the whole application on its loading screen.

A component test is the cheapest place to catch this class of bug: give the fixture a default branch
named something other than `main` and assert the behaviour. See
[Writing component tests](../../guides/frontend/writing-component-tests.md).

## The branch query string parameter

The current branch lives in the URL, and the default branch is represented by the *absence* of the
branch parameter — so its pages keep clean, shareable URLs. Writing the branch means writing that
parameter; there is no separate client-side store to keep in step.

Clearing the parameter is therefore how code returns to the default branch, and reading it is how
code learns the branch was chosen explicitly. See
[URL construction](../../guidelines/frontend/url-construction.md) for building links that carry it.

## First ask whether you want the default branch at all

Code that reaches for the default branch usually wants a more specific branch that happens to be
the default one in the common case. Check for a nearer source before resolving it:

- A proposed change compares against its own destination branch, which is not necessarily the
  default one.
- A branch is diffed against the branch it was created from, which its detail view exposes as the
  origin branch.
- A request to the GraphQL endpoint needs no branch name at all when it is branch-agnostic: the
  server serves `/graphql` without a branch segment as well as `/graphql/{branch_name}`, and
  applies its own default when the segment is absent. Substituting a guessed name is worse than
  omitting the segment — a name that does not exist on the deployment is rejected outright.

When the default branch really is what you want and you need its name rather than the flag, read it
off the branch list entry carrying `is_default`. The list is already fetched and cached by the time
any page renders.
