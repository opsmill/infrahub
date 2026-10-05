COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Branch names resolved per query when reading a repository's per-branch commit and internal status.
REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100

# Ref targeted by the write-access probe. The probe never mutates the remote because it runs under
# --dry-run; this name is merely improbable, so the probe is meaningful even on a remote that happens
# to hold a branch by this name.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"
