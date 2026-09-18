COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

# Deliberately not a setting: no operator has a reason to tune it, and exposing it would drag in the
# generated Compose environment block and the configuration reference documentation.
REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100
