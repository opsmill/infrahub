# Why

A repository can be configured with a default branch that is not `main` - the remote branch Infrahub
maps onto its own default branch. That value was read from the graph **only when a worker cloned the
repository for the first time**. Every later construction of the repository object on that worker
left it unset and silently fell back to Infrahub's own default branch.

The result is an intermittent, per-worker bug: artifact generation, transforms, generators, computed
attributes and proposed change checks run against the wrong branch whenever the worker's clone
happens to be warm. Depending on the remote you either get output built from the wrong branch's
files, or a failure naming a branch the operator never configured.

**Goal:** resolve the configured default branch once, at every construction, on the Infrahub branch
the operation runs on, and make the broken state impossible to construct.

**Non-goals:** rejecting a misconfigured default branch when a repository is connected (US3), and
surfacing skipped colliding branches in the task log (US4). Both are specced and land as separate
PRs on top of this one.

Jira: [IFC-3105](https://opsmill.atlassian.net/browse/IFC-3105)
Epic: [INFP-670](https://opsmill.atlassian.net/browse/INFP-670)
Spec set: `dev/specs/ifc-3105-honour-default-branch/`

This is PR 2 of 4 in that spec's breakdown. It targets the feature branch, not `stable`.

## What changed

**Behavioural**

- A repository's configured default branch is now correct on every operation, whether or not the
  worker already had a clone. This is the fix.
- `operational_status` is written on the branch the operation ran on, instead of always on the
  platform default branch. It is branch scoped, so this is visible to operators.
- The repository's location is now known on every construction. When it differs from the URL the
  clone was made with, the object re-points `origin` and fetches. That self healing path previously
  ran only where a location was passed explicitly.
- User checks resolve the repository by its real kind. `run_user_check` hard coded the read-write
  kind while also running for read-only repositories.

**Implementation**

- `InfrahubRepository` declares `default_branch` and `internal_status` as required pydantic fields.
  Omitting either raises at construction, so there is no bypass.
- `git/graph_settings.py` is the single resolution point: one SDK read, performed by
  `InfrahubRepository.init` / `.new` and nowhere else. It is a module rather than a method on the
  model because the model is a pydantic data holder (`.agents/rules/backend-component-design.md`).
- `get_initialized_repo` and both factories take a required `infrahub_branch_name`, which also joins
  the factory's 30 second cache key because `internal_status` is branch scoped.
- The base class lost the optional field and the fallback property, and answers its three former
  uses through abstract hooks. With the property gone, mypy's `attr-defined` check enforces that no
  base class code reads a default branch the read-only kind does not have.

**What stayed the same**

- No schema, migration, GraphQL or REST change.
- No new dependency.
- Read-only repositories behave exactly as before: their hooks are the identity, which is what the
  removed fallback computed for them anyway.
- No new mypy or `ty` suppressions. `ty` reports 116 diagnostics, unchanged from the base commit.

### Suggested review order

The diff is 69 files, but roughly 1,200 of the ~2,100 added lines are mechanical test migration. The
commits are ordered so you can take them one at a time:

| # | Commit | What to look for |
|---|---|---|
| 1 | `30b7377` resolver | Small, self contained. Nothing calls it yet. |
| 2 | `143607d` reproduction | **Fails at this commit.** Read this to understand the bug. |
| 3 | `6bd8a87` object contract | **The heart of the change.** Worth the most attention. |
| 4 | `a2ac532` call sites | 30 sites, one added argument each. Two real corrections hide here (webhook, user-check kind). |
| 5 | `1b6d54d` test migration | Mechanical, the bulk of the line count. Skim. |
| 6 | `8520f3f` added coverage | Test only. |
| 7 | `1dfd1a0` docs | Changelog, knowledge page, regenerated reference. |
| 8-11 | review fixes | Responses to cubic and to CI. |

## How to review

**Focus here**

- `backend/infrahub/git/repository.py` and `git/base.py` - the contract change (commit 3).
- `backend/infrahub/git/graph_settings.py` - 60 lines, the single resolution point.
- The five call sites that name a branch explicitly rather than taking one from a model. Each
  carries a one line why. A missing branch is a loud `TypeError`; the wrong branch is silent, so
  these are the ones worth checking:
  `git_branch_create`, `git_branch_delete`, `branch_deleted`, `merge_git_repository`, and the
  webhook.

**Skim**

- `backend/tests/` outside `unit/git` - 36 files, almost all one line changes adopting the new
  signature.
- `docs/docs/reference/message-bus-events.mdx` - regenerated, not hand edited.

**Where I would like extra scrutiny**

1. **`internal_status` now comes from the node, whose schema default is `inactive`.** The object
   used to default to `active` on its own. A repository node created without an explicit status
   therefore syncs nothing now. Production sets it explicitly in `RepositoryFinalizer.post_create`,
   so I believe there is no live exposure, but that is a judgement worth a second opinion. It did
   break several test fixtures that relied on the old implicit default.
2. **The cost.** Every read-write construction performs one SDK read. The 16 `get_initialized_repo`
   callers are amortised by the existing 30 second cache, but the periodic sync pays two per
   repository per cycle, and `merge_git_repository`, the two branch lifecycle fan-outs and the
   transform webhook each pay one per event.

**Alternative considered**

Carrying the default branch in the message payloads instead of reading it. Rejected: the Infrahub
branch has to be threaded to all 30 sites regardless (the status is branch scoped), so this would
thread two values instead of one; a carried value is a snapshot that can go stale between enqueue and
execution in exactly the shape of this bug; and most producers do not hold it either, so the read
moves upstream rather than disappearing. The follow up that removes the redundant reads without
reintroducing a carrier is filed under T072 and noted against `infp-546`.

## How to test

```bash
# The reproduction. Passes here; fails on the base commit.
uv run pytest backend/tests/functional/git/test_repository_default_branch.py

# The local gate for this PR
uv run invoke format lint
uv run pytest backend/tests/unit/git
uv run pytest backend/tests/component/git/test_sync_repository.py \
               backend/tests/component/git/test_git_repository.py
uv run pytest backend/tests/functional/git
```

Results as of the last run: unit/git 218 passed; component 69 passed and 1 pre-existing xfail;
functional/git 6 passed; full functional tier 241 passed.

**Evidence the guards bite, not just pass:**

- The reproduction was written first and **fails on the base commit** `0a9cf432a` with
  `assert 'content' == 'trunk content'`: the warm construction pulls the platform default branch, so
  the configured branch's new commit never arrives. The remote carries both branches, so a wrong
  resolution reads the wrong tree rather than erroring.
- Reverting `InfrahubRepository.push`'s refspec to the bare branch name makes
  `pytest backend/tests/component/git/test_git_repository.py -k non_main_default_branch` fail, and
  restoring it makes it pass.

## Impact & rollout

- **Backward compatibility:** `GitFileGet` and `GitDiffNamesOnly` gain required fields, so API and
  task workers must be upgraded together. No in flight message compatibility across versions is
  required. No schema or API change.
- **Performance:** one extra SDK read per read-write repository construction, detailed above.
- **Config/env changes:** none.
- **Deployment notes:** safe to deploy; no coordinated release beyond the usual API and worker
  upgrade.

## Checklist

- [x] Tests added/updated
- [x] Changelog entry added (`changelog/+ifc-3105-warm-clone-default-branch.fixed.md`)
- [ ] External docs updated - not applicable, no user facing surface changes in this PR
- [x] Internal .md docs updated (`dev/knowledge/backend/git-sync.md`)
- [x] I have reviewed AI generated content

<!--
Not included, so a reviewer does not have to ask:

No Playwright e2e test. Backend only change with no frontend work; every operator visible effect
rides on UI that already exists, so there is no new browser behaviour to pin (plan Constitution
Check, Principle IV).

The PRD asks for the skipped branch condition as persistent repository state. That is superseded by
an owner decision of 2026-09-04 that a dedicated status surface for it is overkill, not left undone.
It is US4 and not in this PR.
-->
