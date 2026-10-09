from types import MappingProxyType
from typing import Final, Mapping

COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

<<<<<<< HEAD
READ_ONLY_FETCH_TIMEOUT_SECONDS: Final = 900
"""Ceiling on a read-only repository's fetch, after which git and every process it started are told
to stop. Generous: a first transfer of a large repository is legitimately slow."""

READ_ONLY_FETCH_STOP_GRACE_SECONDS: Final = 10
"""How long a fetch told to stop has to exit, removing its lock files, before it is killed outright."""

# git applies no network timeout of its own. These end an HTTP transfer that has stalled below a
# trickle; every transport, SSH included, is bounded instead by the kill timeout git is given.
REMOTE_TRANSPORT_ENVIRONMENT: Final[Mapping[str, str]] = MappingProxyType(
    {"GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "20"}
)
=======
# Branch names resolved per query when reading a repository's per-branch commit and internal status.
REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100
>>>>>>> origin/develop

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
