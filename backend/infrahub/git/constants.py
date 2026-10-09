COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Branch names resolved per query when reading a repository's per-branch commit and internal status.
REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100

# Ref targeted by the write-access probe. The probe never mutates the remote because it runs under
# --dry-run; this name is merely improbable, so the probe is meaningful even on a remote that happens
# to hold a branch by this name.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"

IMPORT_STATUS_CHECK_KIND = "RepositoryImportCheck"
IMPORT_STATUS_CHECK_NAME = "Repository Import Check"
MERGE_CONFLICT_CHECK_KIND = "MergeConflictCheck"

# One read of the remote heads of a repository stops after this time, and its git process is killed. It
# is lower than the deadline below, so a remote that hangs frees its place for a read that waits.
REMOTE_HEADS_TIMEOUT_SECONDS = 20

# A branch merge reads the remote heads before it takes the global merge lock, so it waits for all the reads
# together at most this long, and a remote not read by then does not hold the merge.
REMOTE_HEADS_DEADLINE_SECONDS = 30

# Each remote head read runs a git process, so a merge over many repositories reads only this many at once.
REMOTE_HEADS_PARALLEL_READS = 8
