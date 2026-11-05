# Imports That Stop Partway

> Part of: `dev/knowledge/backend/` | Related: [Git Sync](git-sync.md)

How a branch import that stops before it ends leaves the branch status, and how the periodic sync
repairs a default branch left `syncing`. Read this before changing what runs between the start of an
import and its apply step, the run records of `ActivityRun`, or how the sync records a new commit of
the default branch.

## A failure before the apply starts sets `error-import`

The failure boundary of an import covers its build and its apply step (see
[Import failures](git-sync.md#import-failures)), not the steps `import_branch` runs around them:
creating the import's flow run, recording the run's phase, and taking the repository lock before the
apply. A failure in one of those steps sets the branch to `error-import`
(`InfrahubRepositoryIntegrator.mark_import_failed`), because the branch may already read `syncing`.
Once the apply starts, the apply sets the final status. A failure after every object is imported
leaves the branch `in-sync` when the repository is added; the periodic sync still reports such a
failed branch as `error-import` afterwards, as it did before.

## Repair a default branch left syncing

A run that stops without raising, such as a killed worker or a cancelled flow, writes no status, so
its branch keeps `syncing`. A `syncing` status has no owner, so it cannot tell an import under way
from one whose run stopped. Each run on a repository keeps a record in the cache instead
(`ActivityRun`). The run renews the record every minute and deletes it when it ends, and a record
that is not renewed expires after five minutes. A record therefore exists only while its run works
on the repository, or shortly after the run stopped.

- **Import the default branch again when it reads `syncing` and no other run has a record.** The
  periodic sync checks this after the bootstrap (`import_stopped_partway`) and asks the syncer to import
  the default branch again (`reimport_default_branch`). The record of the cycle's own run does not
  count. The cycle reads each branch's status in its existing query (`RepositoryBranchInfo.sync_status`),
  and reads a branch it saw as `syncing` again after the bootstrap, which can import it. After a run
  stops, the repair waits for its record to expire and for the next cycle, so up to about six minutes.
- **Drop the recorded commit only when it is the remote head.** The syncer imports a branch whose
  recorded commit differs from the remote head anyway, and classifies the head against that commit, so
  a rewrite of the remote since the stopped import is still recorded. When the recorded commit is the
  remote head, nothing was rewritten, and the syncer reads the branch as holding no commit so that it
  imports it.
- **Repair only an active repository with no pushes waiting.** The sync leaves the default branch
  alone in an inactive repository and while merges wait for their push, so the repair does not run
  then.
- **A status that cannot be read skips the repair for that cycle.** The synchronization of the
  repository goes on.
- **Record the default branch's new commit with its `syncing` mark.** The syncer writes the commit
  under the lock and imports it later. Written alone, a sync that stops in between leaves the new
  commit next to the `in-sync` of the earlier one, which no check tells apart from an import that
  finished. `InfrahubRepository.record_commit_for_import` writes both in one mutation, on the branch
  whose status the import sets.
- **A cache that cannot be read answers that no other run has a record.** The branch is then imported
  again, which at worst repeats an import that is under way.
- **An import that stops its worker is tried again on every repair.** An import that runs out of
  memory, for example, is started again about every six minutes. Before, the branch stayed `syncing`.
- **Two periodic syncs never overlap.** The flow runs on one worker at a time, so the record of
  another cycle cannot hold off the repair. Any other run on the repository does, until it ends.
- **The delivery of a merge imports the default branch without a record.** The periodic sync leaves
  the default branch alone while merges wait for their push, and the delivery imports before it
  clears that queue, so the repair does not import alongside it.
- **Only the default branch is repaired.** A seed into a staging branch, and every other branch, are
  imported again only by a fresh clone on a worker that holds no copy of the repository.
- **A default branch the worker does not hold yet records its commit without the mark.** When a
  repository's default branch is changed to a Git branch that this worker has not created, the sync
  records its commit alone, so a sync that stops before the import still leaves the earlier status.
