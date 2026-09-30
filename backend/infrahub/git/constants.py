COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Ref targeted by the write-access probe. The probe never mutates the remote because it runs under
# --dry-run; this name is merely improbable, so the probe is meaningful even on a remote that happens
# to hold a branch by this name.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"
