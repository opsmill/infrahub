# Contract: Skipped colliding branch in the repository task log

Covers FR-008. No new repository attribute, status value, relationship or persistent state.

The warning has two carriers: the flow that adds a repository reports it once at connect, and the
per-repository synchronisation child flow reports it afterwards for a run that either imported
something or saw the skipped branch's own remote head move. A cycle where nothing moved on the remote
records nothing. See research.md D6 for why a warning on every cycle was rejected, and for the
per-worker duplication the second trigger accepts.

## Collection

The collision predicate stays where the decision is made. `validate_remote_branch` already evaluates
`branch_name == registry.default_branch and branch_name != self.default_branch` (`git/base.py:890`)
and returns `False`; it must not be re-evaluated in the caller. Re-deriving it there would put one
predicate in two files, and a drift between them would drop the branch while telling the operator
nothing — the exact defect class this feature exists to delete.

So `validate_remote_branch` reports **why** it rejected a branch instead of returning a bare `bool`:

```python
class BranchSkipReason(Enum):
    DEFAULT_BRANCH_COLLISION = "default_branch_collision"
    INVALID_BRANCH_NAME = "invalid_branch_name"

# None means "import this branch"; a member means "skip it, for this reason".
def validate_remote_branch(self, branch_name: str) -> BranchSkipReason | None
```

`validate_remote_branch` moves to `InfrahubRepository` with this change (research.md D3); it is
reached only through `collect_pending_imports`, which is defined on the read-write class.

`collect_pending_imports` calls it at **two** sites — `git/repository.py:178` for new branches and
`:211` for updated ones. Both sites skip on any reason, and both append to
`CollectedImports.skipped_branches` when the reason is `DEFAULT_BRANCH_COLLISION`. Neither site
re-tests the condition. The remaining validation (`Branch(name=...)` construction, conflict warning)
is unchanged in behaviour; only the return value's shape changes.

```python
class CollectedImports(BaseModel):
    imports: list[PendingObjectImport] = []
    failed_imports: list[FailedImport] = []
    skipped_branches: list[str] = []              # new
    advanced_skipped_branches: list[str] = []     # new
```

### Detecting that a skipped branch advanced

`collect_pending_imports` calls `self.fetch()` at `git/repository.py:159`. Immediately **before** that
call it lists the remote heads with `get_branches_from_remote()`, keeping a `{branch: commit}` map,
and afterwards a skipped branch is recorded in `advanced_skipped_branches` when:

- the branch is in `skipped_branches` for this run, **and**
- the pre-fetch map has an entry for it, **and**
- that entry's commit differs from the branch's commit after the fetch.

The middle condition is the cold-clone rule: a worker with no prior ref for the branch records
nothing, because otherwise its first sync of the repository would report every skipped branch as
newly advanced. The connect-time carrier reports unconditionally, so nothing is lost.

No new persistent state and no extra network call. `fetch` uses no refspec
(`origin.fetch(prune=True, tags=True, prune_tags=True)`), so the colliding branch has a
remote-tracking ref like any other, and `get_branches_from_remote` already reads that ref's commit;
calling it before the fetch is a local ref walk. `compare_local_remote` cannot substitute for this: it
diffs remote heads against *local* branches, and the colliding branch has no local branch, so it
reports the branch as new on every cycle whether or not it moved.

**The detection is per worker.** Git storage is per worker and the periodic sync has no worker
affinity, so each worker compares against its own previous fetch. One push to the skipped branch can
therefore be reported once by each worker that subsequently synchronises the repository. This is
accepted, not solved: deduplicating it needs state shared between workers, which is the GraphQL
schema gate this feature is scoped to avoid. The bound is the worker count, not the cycle rate.

## Report

```python
@dataclass(frozen=True)
class SyncReport:
    skipped_branches: tuple[str, ...]
    imported_branches: tuple[str, ...]
    advanced_skipped_branches: tuple[str, ...]

async def RepositorySyncer.sync(self, repo: InfrahubRepository, staging_branch: str | None = None) -> SyncReport
```

- `skipped_branches` is copied from `CollectedImports.skipped_branches` for the run.
- `imported_branches` holds the Infrahub branch name of every import the run applied successfully.
  Empty means the run imported nothing, which is the case on every cycle where the only "new" remote
  branch is the permanently-skipped colliding one.
- `advanced_skipped_branches` is copied from `CollectedImports.advanced_skipped_branches`. Non-empty
  means a skipped branch received a commit since this worker's previous fetch.
- The two together are the run's answer to "is this cycle worth reporting". Both empty means nothing
  moved: no warning, no node link.
- `sync` still raises through `raise_if_branches_failed` when any import failed.

**The report must survive that raise.** `raise_if_branches_failed` is the last statement of `sync`
(`git/sync.py:129`), so a run that imported the trunk fine but failed some other branch would, if the
report were returned only on success, emit no skipped-branch warning at all. At connect that breaks
FR-008's "MUST be recorded when the repository is connected", and it breaks it precisely for a
repository that is already in trouble and whose operator most needs the full picture.

`sync` therefore **emits nothing itself but makes the report available on both paths**: the carriers
below read `report.skipped_branches` and log before any failure is re-raised. Concretely, `sync`
builds the `SyncReport` before calling `raise_if_branches_failed` and attaches it to the raised error
(`RepositoryBranchesFailedError.report`), so a carrier's `except` block has the same report a
successful run returns. A carrier that catches the failure logs the skipped-branch warnings and then
re-raises.

## Warning text

One line per skipped branch, through `prefect.logging.get_run_logger()`, verbatim:

```text
Skipped remote branch 'main' of repository demo: its name collides with the Infrahub default branch, which is mapped to this repository's default branch 'develop'.
```

Both carriers emit the same text.

## Carrier 1: at connect

`backend/infrahub/git/tasks.py::add_git_repository`:

1. Already calls `add_tags(branches=[...], nodes=[model.repository_id])` as its first statement, so
   the run is linked to the repository node before anything else happens.
2. Already runs `RepositorySyncer.sync(repo)` after the add (`git/tasks.py:103`), for an active
   repository.
3. Emits one warning per `report.skipped_branches` entry, unconditionally — **on both the success
   and the failure path**. The call at step 2 is wrapped so that a
   `RepositoryBranchesFailedError` still yields its report, the warnings are logged, and the error is
   re-raised unchanged. This run happens exactly once per repository, so the condition is reported
   exactly once, at the moment the operator connects it, whether or not every branch imported.

No tagging change is needed here. A repository added in staging returns at `git/tasks.py:100` before
the sync and reports nothing; the condition is then reported by the first cycle that imports
something after the proposed change merges.

## Carrier 2: per synchronisation cycle

`backend/infrahub/git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure`, per run:

1. Build the repository object through the factory (no trunk or status parameters), **inside** the
   existing `try`. The construction now performs a graph read that can raise `RepositoryError`
   (`contracts/repository-object.md`, error contract); today it sits outside the `try`
   (`git/tasks.py:225` versus `:235`), so such a failure would bypass this flow's own tag-on-failure
   handler and leave the run unlinked from the repository node — invisible in the Tasks tab that
   SC-005 relies on. The cycle survives either way, because `sync_repository_from_origin` isolates
   it one level up (`git/tasks.py:338`); the visibility is what is lost.
2. `report = await syncer.sync(repo, staging_branch=...)`, with the same failure-path handling as
   carrier 1: a `RepositoryBranchesFailedError` still yields its report.
3. Emit one warning per skipped branch **only when** `report.skipped_branches` is non-empty **and**
   at least one of `report.imported_branches` / `report.advanced_skipped_branches` is non-empty. The
   warning is emitted for every entry in `skipped_branches`, not only for the branches that advanced:
   a run triggered by one skipped branch moving reports the full set skipped in that run, so the
   operator sees the whole condition rather than a slice of it. This holds on the failure path too: a
   run that imported at least one branch and failed another still reports the skipped branch before
   re-raising.
4. Link the run to the repository node with a single
   `add_tags(branches=[infrahub_branch], nodes=[repository_id])` call when at least one of the
   following holds:
   - the run emitted a skipped-branch warning under step 3;
   - the sync raised `RepositoryError` or `CommitNotFoundError` while the repository's operational
     status was `ONLINE` (today's rule, unchanged).

   The call is issued once, after both conditions are known, because tags added mid-run replace any
   tags another mid-run update added earlier.
5. Re-raise the sync error if there was one.

## Observable outcomes

Repository with trunk `develop`, remote also has `main`, Infrahub default `main`:

| Situation | Warning | Run linked to the node |
|---|---|---|
| The repository is connected | one line naming `main`, in the add task | yes, the add task already links itself |
| Idle cycle, nothing changed on any branch | none | no |
| Cycle that imported a changed branch | one line naming `main` | yes |
| Push to the colliding `main` only, nothing imported | one line naming `main`, on the first cycle each worker runs after the push | yes |
| Second and later cycles on the same worker after that push, nothing further moved | none | no |
| Colliding branch deleted, or trunk changed to `main` | none | no |
| First cycle on a worker with no prior clone of the repository | none on the advance trigger; the ordinary import rules apply | only under the ordinary rules |
| Sync failure while `ONLINE` | the existing failure log, plus a skip warning only if the run also imported something or saw the skipped branch advance | yes |
| First sync at connect fails on some other branch | one line naming `main`, logged before the error is re-raised | yes, the add task already links itself |
| Later cycle imports one branch and fails another | one line naming `main`, logged before the error is re-raised | yes |

Trunk equals the Infrahub default, so no collision is possible: never a warning, and the run is
linked only on failure.

The repository's Tasks tab therefore lists the add task, the cycles that did real work, the cycles
that saw a commit land on a branch Infrahub is not importing, and the failures. A standing collision
costs one entry plus one per push to the skipped branch per worker, not one per minute.

## Logger

The warning must go through `prefect.logging.get_run_logger()` inside the flow. The module-level
structlog logger in `backend/infrahub/git/base.py` is not in the worker's task-logger set and never
reaches the task log. The existing structlog "Ignoring import of mismatched default branch" line may
stay for process logs but is not the operator-facing record.
