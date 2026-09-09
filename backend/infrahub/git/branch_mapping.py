from __future__ import annotations

import re


def get_mapped_remote_branch(
    branch_name: str,
    repository_default_branch: str,
    infrahub_default_branch: str,
) -> str:
    """Return the remote git branch an Infrahub branch reads from.

    Infrahub's default branch reads the repository's configured default branch; every other branch
    reads the remote branch of the same name.

    Every input is required: the caller has to state which trunk it means, so a missing value cannot
    silently resolve to Infrahub's default branch.
    """
    if branch_name != repository_default_branch and branch_name == infrahub_default_branch:
        return repository_default_branch
    return branch_name


def branch_name_matches_import_filters(branch_short_name: str, import_sync_branch_names: list[str]) -> bool:
    """Return whether a remote branch name matches one of the configured import filters.

    A filter matches either as a full-string regular expression or as a literal name.
    """
    for branch_filter in import_sync_branch_names:
        if re.fullmatch(branch_filter, branch_short_name) or branch_filter == branch_short_name:
            return True
    return False


def remote_branch_is_imported(
    remote_branch_name: str,
    branch_is_synced_with_git: bool,
    repository_default_branch: str,
    infrahub_default_branch: str,
    import_sync_branch_names: list[str],
) -> bool:
    """Return whether a sync imports this remote branch onto the Infrahub branch that maps to it.

    With no import filters configured every remote branch is imported, so `branch_is_synced_with_git`
    on its own does not decide the answer. Both trunks are always imported.
    """
    if not import_sync_branch_names:
        return True
    if remote_branch_name in {infrahub_default_branch, repository_default_branch}:
        return True
    if branch_is_synced_with_git:
        return True
    return branch_name_matches_import_filters(
        branch_short_name=remote_branch_name, import_sync_branch_names=import_sync_branch_names
    )
