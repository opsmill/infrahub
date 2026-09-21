from __future__ import annotations

import tempfile
from dataclasses import dataclass

import git
from git.exc import GitCommandError

from infrahub.exceptions import RepositoryError, RepositoryInvalidBranchError
from infrahub.git.base import InfrahubRepositoryBase

HEAD_SYMREF_PREFIX = "ref: refs/heads/"
BRANCH_REF_PREFIX = "refs/heads/"


@dataclass(frozen=True)
class RemoteRefs:
    default_branch: str | None
    branches: frozenset[str]


def list_remote_refs(name: str, url: str) -> RemoteRefs:
    """List a remote's default branch and branch heads without cloning it.

    Raises:
        RepositoryError: For any git failure, raised as its connection or credentials subtype
            where the failure can be classified.

    """
    # A neutral working directory keeps git from discovering a .git pointer in the process CWD,
    # which in a worktree build references a host path the container does not have.
    cmd = git.cmd.Git(working_dir=tempfile.gettempdir())
    try:
        listing = cmd.ls_remote("--symref", url, "HEAD", "refs/heads/*")
    except GitCommandError as exc:
        InfrahubRepositoryBase._raise_enriched_error_static(name=name, location=url, error=exc)

    if not isinstance(listing, str):
        raise RepositoryError(identifier=name, message=f"Unable to read the branches of the repository {name}.")

    default_branch: str | None = None
    branches: set[str] = set()
    for line in listing.splitlines():
        left, _, right = line.partition("\t")
        if right == "HEAD" and left.startswith(HEAD_SYMREF_PREFIX):
            default_branch = left.removeprefix(HEAD_SYMREF_PREFIX)
        elif right.startswith(BRANCH_REF_PREFIX):
            branches.add(right.removeprefix(BRANCH_REF_PREFIX))

    return RemoteRefs(default_branch=default_branch, branches=frozenset(branches))


def ensure_branch_exists(refs: RemoteRefs, *, branch_name: str, repository_name: str, location: str) -> None:
    """Confirm the remote has the requested branch, whether or not it is the remote's default.

    Raises:
        RepositoryInvalidBranchError: When the branch is absent from the listing.

    """
    if branch_name in refs.branches:
        return

    # A remote can advertise a default branch it then hides from the listing, which would otherwise
    # name the missing branch as the one to use instead.
    if refs.default_branch is not None and refs.default_branch in refs.branches:
        detail = f"the remote's default branch is '{refs.default_branch}'."
    else:
        detail = "the remote is empty or has no default branch."

    raise RepositoryInvalidBranchError(
        identifier=repository_name,
        branch_name=branch_name,
        location=location,
        message=f"Branch '{branch_name}' does not exist on the remote repository {repository_name}; {detail}",
    )
