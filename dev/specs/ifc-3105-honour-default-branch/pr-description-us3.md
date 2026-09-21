# Why

**Connecting a repository with the wrong default branch used to succeed, then fail later.** This PR
rejects it up front, with a message that says what to fix.

A `CoreRepository` carries a `default_branch` - the remote branch Infrahub maps onto its own default
branch. It defaults to `main`, and nothing checked that the branch actually existed on the remote.
So connecting a repository whose remote uses `master` (or anything else) went through: the
connectivity check only proved the remote was reachable. The repository was created and looked fine,
and the misconfiguration surfaced minutes later as a failed synchronization naming a branch the
operator had never heard of. Diagnosing it meant knowing that `default_branch` exists, that it
defaults to `main`, and that the remote disagrees.

**Goal:** reject the configuration at the cheapest point - while connecting, from the reference
listing the connectivity check already performs, with no clone - and leave no repository behind. The
operator sees both halves of the mismatch in one sentence:

> Branch 'main' does not exist on the remote repository demo; the remote's default branch is 'master'.

**Non-goals:** validating a `default_branch` edited after the repository is connected, and validating
a read-only repository's `ref`. Both are out of contract and are now documented as limitations on the
"connect a repository" page; the second needs its own design, because a `ref` may be a tag or a
commit hash that no branch listing can confirm.

Jira: [IFC-3139](https://opsmill.atlassian.net/browse/IFC-3139)
Parent: [IFC-3105](https://opsmill.atlassian.net/browse/IFC-3105)
Epic: [INFP-670](https://opsmill.atlassian.net/browse/INFP-670)
Spec set: `dev/specs/ifc-3105-honour-default-branch/`, User Story 3

This is PR 3 of 4 in that spec's breakdown, and it **targets the feature branch
`pog-honour-default-branch-ifc-3105`**, not `develop`. PR 2 (#10664) is already on that branch, so
this diff is only User Story 3. Because the base is a feature branch rather than a GitHub-created
stack, CI runs the full huge-runner tier here.

## What changed

**Behavioural**

- Creating a `CoreRepository` whose `default_branch` is absent from the remote is rejected. The
  operator gets `Branch 'main' does not exist on the remote repository demo; the remote's default
  branch is 'master'.`, or `...; the remote is empty or has no default branch.` when the remote
  advertises no default, and no repository remains.
- A `default_branch` that exists but is **not** the remote's default is accepted, with no error,
  warning or log line. That is a supported configuration, not a near miss.
- Read-only repositories and the "Check connectivity" action are unchanged: both send no branch, so
  they stay pure reachability checks.
- An unreachable remote, bad credentials or a TLS failure report exactly what they reported before.
  The listing fails before anything is parsed and goes through the same error classifier.

**Implementation**

- `backend/infrahub/git/remote_refs.py` is new: a frozen `RemoteRefs`, `list_remote_refs` running
  one `git ls-remote --symref <url> HEAD refs/heads/*` from a neutral working directory, and a pure
  `ensure_branch_exists`. Three module-level symbols rather than methods, because none of them
  touches repository instance state and the flow that uses them holds no repository object.
  `ensure_branch_exists` takes its three strings keyword-only: transposing `repository_name` and
  `location` would type-check and put the remote URL, credentials included, into the operator's
  error.
- `InfrahubRepositoryBase.check_connectivity` is removed; `remote_refs.list_remote_refs` replaces it.
  The static error classifier it delegated to stays on the base, where the instance path still uses
  it.
- `GitRepositoryConnectivity` gains `default_branch: str | None = None`. `None` means "connectivity
  only", which is today's behaviour, so the field is inert for every sender that does not set it.
- `RepositoryFinalizer.post_create` sets it for the read-write kind only. `post_create` is otherwise
  unchanged in shape: on `success is False` it deletes the just-created node and raises
  `ValidationError`, exactly as it does for a connectivity failure today.
- The flow gates on `is not None`, not truthiness, so an empty `default_branch` is a branch that
  does not exist rather than "no branch configured". The attribute carries no minimum length, so an
  empty value is reachable and would otherwise skip the check and fail later at clone time.

**What stayed the same**

- No schema, migration, GraphQL or REST change. The only operator-facing surface is the error message
  the existing create mutation returns.
- No new dependency.
- No new mypy, `ty` or ruff suppression.

## How to review

Small: one new module, one message field, one flow branch, one docs page.

1. `backend/infrahub/git/remote_refs.py` - 75 lines, new. Start here; the parser and the two messages
   are the whole contract.
2. `backend/infrahub/message_bus/operations/git/repository.py::connectivity` - the flow. Note that
   `RepositoryInvalidBranchError` is a `RepositoryError`, so it falls through the existing status map
   to `ERROR`, which is what the contract asks for.
3. `backend/infrahub/repositories/create_repository.py` - the sender. `configured_default_branch`
   narrows the node's attribute with `isinstance` rather than a `cast`, per
   `.agents/rules/python-typing.md`; the read-only kind returns `None` before the attribute is read.
4. `backend/tests/integration/git/test_git_live_remote.py` - the outcome-level evidence, against a
   Gogs remote whose only branch is `master`, plus the read-only repository pinned to a tag that
   proves the kind guard.

**Skim**

- `docs/docs/reference/message-bus-events.mdx` - regenerated, one row.

**Where I would like extra scrutiny**

1. **The create-then-delete window.** FR-007 is worded as "no repository remains after a rejected
   request" rather than "no repository is created", because the node is created and then deleted -
   exactly as it is for a connectivity failure today. This PR does not change that window, but it
   does make it reachable for a new class of failure, so it is worth a second opinion on whether the
   pre-existing behaviour is acceptable for this case too.
2. **The parser is keyed on `ls-remote` output text.** `ref: refs/heads/<name>\tHEAD` sets the
   default and `<sha>\trefs/heads/<name>` adds a branch; everything else is ignored. An empty bare
   remote returns no output and exit 0 under protocol v0 and v2 alike, which is why there is no
   special case for it.
3. **A remote can advertise a default branch it then hides from the listing** (`uploadpack.hideRefs`),
   so `ensure_branch_exists` only names the remote's default when it is present in the listing.
   Without that, a repository configured for a hidden `main` would be told its remote's default
   branch is `main` - the branch it was just told does not exist.

## How to test

```bash
# The local gate for this PR
uv run invoke format
uv run invoke lint
uv run pytest backend/tests/unit/git
uv run pytest backend/tests/component/git/test_sync_repository.py \
               backend/tests/component/git/test_git_repository.py
uv run pytest backend/tests/functional/git

# The outcome-level evidence (Docker required; Gogs runs in testcontainers)
uv run pytest backend/tests/integration/git/test_git_live_remote.py
```

Results as of the last run: unit/git 266 passed; component 69 passed and 1 pre-existing xfail;
functional/git 6 passed; integration `test_git_live_remote.py` 9 passed; backend unit tier 2716
passed with one unrelated xdist-only flake in `backend/tests/unit/api/test_oidc.py`, which passes on
its own.

**Evidence the guards bite, not just pass:**

- `test_connecting_with_a_default_branch_absent_from_the_remote_is_rejected` cannot pass without
  this change: before it, the create mutation against a `master`-only remote **succeeded** - the old
  `ls-remote --tags` check proved only reachability - so there was no error to assert and a
  repository was left behind.
- `test_connecting_a_read_only_repository_pinned_to_a_tag_is_not_branch_checked` was run against a
  deliberately broken `configured_default_branch` that returns the read-only `ref`. It fails with
  `Branch 'v1.0.0' does not exist on the remote repository tag-pinned-repo; the remote's default
  branch is 'master'.`, which is the regression the kind guard exists to prevent.
- The neutral-working-directory regression is not lost in the move:
  `test_check_connectivity_ignores_cwd_git_pointer` was ported to
  `test_list_remote_refs_ignores_cwd_git_pointer` before `check_connectivity` was deleted, so the
  behaviour is never uncovered between commits.

## Impact & rollout

- **Backward compatibility:** `default_branch` is optional and defaults to `None`, so an older worker
  receiving the new field ignores it (the branch simply goes unvalidated) and a newer worker
  receiving a message without it behaves exactly as today. No coordinated API/worker upgrade is
  required for this PR.
- **Performance:** the connectivity check does one `ls-remote` as before. The pattern is wider
  (`HEAD refs/heads/*` instead of `--tags`), and the check runs once per repository connection.
- **Config/env changes:** none.
- **Deployment notes:** safe to deploy.

## Checklist

- [x] Tests added/updated
- [x] Changelog entry added (`changelog/+ifc-3105-connect-time-trunk-validation.added.md`)
- [x] External docs updated (`docs/docs/git-integration/connect-repository.mdx`)
- [ ] Internal .md docs updated - not applicable; `dev/knowledge/backend/git-sync.md` covers branch
      import, which this PR does not touch
- [x] I have reviewed AI generated content

<!--
Not included, so a reviewer does not have to ask:

No Playwright e2e test. Backend only change with no frontend work; the rejection rides on the
existing create-repository error path in the UI, so there is no new browser behaviour to pin
(plan Constitution Check, Principle IV).

The PRD asks for the skipped branch condition as persistent repository state. That is superseded by
an owner decision of 2026-09-04 that a dedicated status surface for it is overkill, not left undone.
It is US4 and not in this PR.
-->
