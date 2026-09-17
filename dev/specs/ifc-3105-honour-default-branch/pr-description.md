# Resolve the configured repository default branch once, at every construction [IFC-3105]

## What was wrong

A read-write repository's configured default branch was read from the graph only when a worker cloned
the repository for the first time. Every later construction of the per-flow repository object on that
worker omitted it and inherited a silent fallback to Infrahub's own default branch. Artifact
generation, transforms, generators, computed attributes and proposed-change checks therefore ran
against the wrong branch whenever the worker's clone was already warm — intermittently, and
differently per worker.

## What changed

- `InfrahubRepository` declares `default_branch` and `internal_status` as **required** fields with no
  defaults. The optional field and the fallback property are gone from the shared base, so no
  base-class code can read a default branch that a read-only repository does not have.
- `git/graph_settings.py` holds the single resolution point: one SDK read of the repository node,
  performed by `InfrahubRepository.init` / `.new` and nowhere else.
- `get_initialized_repo` and both factories take a required `infrahub_branch_name`, which is also part
  of the factory's 30-second cache key. All 16 factory call sites and the 14 direct construction sites
  pass it.
- The models and flow parameters that used to carry the default branch no longer do:
  `GitRepositoryAdd.default_branch_name`, `GitRepositoryMerge.default_branch`, and the
  `default_branch_name` / `internal_status` parameters of the sync child flow.
- The base class answers its three former uses of the default branch through abstract hooks, with
  identity implementations on the read-only kind.

## Two operator-visible changes riding along

1. **`operational_status` now writes on the branch the operation ran on.** The factories set
   `infrahub_branch_name` on the object, and `_update_operational_status` reads it. Every
   `get_initialized_repo` caller previously left it unset and wrote the status on the platform default
   branch regardless of where it ran. `operational_status` is branch-scoped, so this moves a value
   operators can see. It is the intended shape — one branch, one meaning — and is pinned by a unit
   test asserting which branch the mutation names.

2. **User checks now resolve the repository by its real kind.** `run_user_check` hard-coded
   `repository_kind=InfrahubKind.REPOSITORY` while also running for read-only repositories. That was
   invisible while construction read nothing from the graph. The kind is now threaded from the
   proposed change's repository list through `TriggerRepositoryUserChecks`, `UserCheckDefinitionData`
   and `UserCheckData`. Two existing functional tests in `test_convert_repositories.py` caught this.

## Cost, and the follow-up that removes it

Every read-write construction now performs one SDK read. The 16 `get_initialized_repo` callers are
amortised by the existing 30-second cache, but some paths are not: the periodic sync pays two per
repository per cycle, and `merge_git_repository`, the two branch-lifecycle fan-outs and the transform
webhook each pay one per event.

`git_branch_create` and `git_branch_delete` are the sharpest case — they need only local clone and
worktree operations, and neither resolved value can affect their outcome, yet they must construct the
full object to get one. The remedy is not an optional field, which is the shape this change deletes,
but smaller objects and settings resolved at the composition root. Both are recorded in
`plan.md` Complexity Tracking, filed under T072, and noted against `infp-546` Story 3.

## Verification

- `backend/tests/functional/git/test_repository_default_branch.py::test_warm_clone_operation_targets_configured_default_branch`
  is the reproduction. It was written first and **fails on the base commit** (`0a9cf432a`): the warm
  construction pulls the platform-default branch, so the trunk's new commit never arrives
  (`assert 'content' == 'trunk content'`). The remote carries both branches, so the wrong resolution
  succeeds while reading the wrong tree rather than erroring.
- **FR-009 mutation check, performed**: reverting `InfrahubRepository.push`'s refspec from
  `HEAD:refs/heads/<remote>` to the bare branch name makes
  `pytest backend/tests/component/git/test_git_repository.py -k non_main_default_branch` fail
  (1 failed); restoring the refspec makes it pass (1 passed). The guard bites.
- Baselines and per-tier counts: `dev/specs/ifc-3105-honour-default-branch/baseline.md`.

## Not included

No Playwright e2e test. This is a backend change with no frontend work, and every operator-visible
effect rides on UI that already exists — the connect form renders whatever validation error the API
returns, and the node Tasks tab already lists node-tagged runs. There is no new browser behaviour to
pin (plan Constitution Check, Principle IV).

The PRD's request for the skipped-branch condition as persistent repository state is superseded by an
owner decision of 2026-09-04 that a dedicated status surface for it is overkill, not left undone.
That work is US4 and is not in this pull request.
