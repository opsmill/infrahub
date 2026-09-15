COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Ref deleted by the write-access probe. It must never name a branch a remote actually holds,
# so the dry-run delete is always a no-op on the remote's refs.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"
