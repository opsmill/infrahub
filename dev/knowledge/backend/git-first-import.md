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

Both flows check, under the repository lock and after the clone, whether the graph already holds the
cloned commit imported or is importing it, and skip the import when it does.
`InfrahubRepository.holds_or_imports_commit` reads the repository node on the branch and answers yes
only when the node records that commit and the branch is `in-sync` or `syncing`.

- **Mark the branch `syncing` in the same hold of the lock that records the commit.** Each flow builds
  its import outside the lock, and the build sets `syncing` only once its subflow starts. Without the
  mark, a clone that takes the lock in between reads the new commit next to the status of the earlier
  one, `unknown` for a new repository, and imports the commit too.
  `InfrahubRepository.record_commit_for_import` records the commit and marks the branch together.
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

## The cycle passes the syncer the commit the bootstrap left recorded

A synchronization cycle reads the commits of every repository once, before the bootstrap takes the
lock, and the syncer compares each remote head against them. When the bootstrap seeds the default
branch or finds its commit already imported, it returns that commit in
`BootstrappedRepository.recorded_commit`, and `sync_remote_repository` replaces the cycle's earlier
read with it. Without that, the syncer compares the remote head against the earlier read, which held
no commit for a new repository, and imports the branch a second time.
