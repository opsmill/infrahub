from __future__ import annotations


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
