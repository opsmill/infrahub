COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Ref targeted by the write-access probe. The probe never mutates the remote because it runs under
# --dry-run; this name is merely improbable, so the probe is meaningful even on a remote that happens
# to hold a branch by this name.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"

IMPORT_STATUS_CHECK_KIND = "RepositoryImportCheck"
IMPORT_STATUS_CHECK_NAME = "Repository Import Check"
MERGE_CONFLICT_CHECK_KIND = "MergeConflictCheck"

# A branch merge reads the remote heads before it takes the global merge lock, so a remote that does
# not answer must stop delaying the merge after this time.
REMOTE_HEADS_TIMEOUT_SECONDS = 30
