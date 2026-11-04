# First Import of a Repository

> Part of: `dev/knowledge/backend/` | Related: [Git Sync](git-sync.md), [Git Integration](git-integration.md)

How the default branch of a new repository is imported once, although two flows import it after a
clone. Read this before changing the add flow, the seed import of the periodic sync, or what either
reads from the graph before it imports.

## Two flows import the default branch after a clone

The add flow (`git/sync.py::RepositoryAdder`) clones a new repository and imports its default branch.
The periodic sync (`git/tasks.py::bootstrap_local_repository`) clones any repository the worker holds
no copy of, and runs a seed import of its default branch. Storage is per worker, so both run for the
same new repository on different workers, in either order:

- The periodic sync can clone the repository before its add flow runs, while the graph holds no
  commit, and import it first.
- A worker that holds no copy yet, such as the second worker of a pool, clones the repository after
  its add flow imported it.

Each import sets the branch to `syncing` when it starts and to `in-sync` when it ends. A second
import of the same commit therefore sends the branch back to `syncing` until it finishes, after the
first one already set it to `in-sync`, and repeats the work of the first.

## Skip the import of a commit the graph holds or is importing

Both flows read, under the repository lock and after the clone, the commit the graph records for the
branch and the status of the branch (`InfrahubRepository.read_recorded_import`). They skip the import
when `RecordedImport.covers` answers yes: the graph records the cloned commit and the branch is
`in-sync` or `syncing`.

- **Record the commit and mark the branch `syncing` in one write, under the lock.** Each flow builds
  its import outside the lock, and the build sets `syncing` only once its subflow starts. Without the
  mark, a clone that takes the lock in between reads the new commit next to the status of the earlier
  one, `unknown` for a new repository, and imports the commit too.
  `InfrahubRepository.record_commit_for_import` writes both in one mutation.
- **Import when the status is `unknown` or `error-import`.** `error-import` means the import of the
  recorded commit failed, so a fresh clone still retries it. `unknown` with a recorded commit means no
  flow marked an import, as for a commit written through the API.
- **A flow that stops between the mark and the end of its import leaves the branch `syncing`.** A
  fresh clone then skips the import as well, so the branch stays `syncing` until a new commit or a
  manual re-import.
- **The add flow records the commit after the check.** It clones without recording, then records the
  commit when it goes on to import. Recording during the clone would make the check read the add
  flow's own write.
- **The seed import checks only a reinitialized copy.** The fallback clone that follows a failed
  `init()` records its commit while it clones, so a check after it would read that write.

## The commit event of a new repository

An import from a reinitialized copy sends no `CommitUpdatedEvent`, because a re-clone of a repository
does not change its commit. The first import of a new repository does, and when the periodic sync
imports it first, the add flow skips its own import and would send none either. So a seed import that
records a commit on a branch where the graph recorded none sends the event itself, once its import
succeeds (`InfrahubRepositoryIntegrator.announce_commit_update`).

## The cycle passes the syncer the commit the seed import recorded

A synchronization cycle reads the commits of every repository once, before the bootstrap takes the
lock, and the syncer compares each remote head against them. The bootstrap returns the commit the
graph records once it ran in `BootstrappedRepository.recorded_commit`.

- **A missing commit is replaced with it.** For a new repository the cycle's read holds no commit, so
  the syncer would compare the remote head against nothing and import the seeded commit again.
- **An earlier commit is kept.** The syncer classifies the remote head against it, so a rewrite of the
  remote that a fresh clone holds is still recorded as a rewrite.
