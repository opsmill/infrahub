from __future__ import annotations

import asyncio
import os
import signal
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

import git
from git.exc import GitCommandError

from infrahub.exceptions import RepositoryConnectionError, RepositoryError, RepositoryInvalidBranchError
from infrahub.git.base import InfrahubRepositoryBase
from infrahub.git.constants import WRITE_ACCESS_PROBE_REF

if TYPE_CHECKING:
    from collections.abc import Sequence

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


async def list_remote_heads(name: str, url: str, branch_names: Sequence[str], timeout_seconds: int) -> dict[str, str]:
    """Return the head commit of each named branch the remote holds, without cloning it.

    A branch the remote does not hold is absent from the result.

    Raises:
        RepositoryConnectionError: When the remote does not answer within ``timeout_seconds``.
        RepositoryError: For any other git failure, raised as its connection or credentials subtype
            where the failure can be classified.

    """
    refs = [f"{BRANCH_REF_PREFIX}{branch_name}" for branch_name in branch_names]
    command = ["git", "ls-remote", url, *refs]
    # A session of its own lets the timeout stop the remote helpers git starts, which keep the pipes open.
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=tempfile.gettempdir(),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        output, error_output = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError as exc:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise RepositoryConnectionError(
            identifier=name,
            message=f"The remote of repository {name} did not answer within {timeout_seconds} seconds.",
        ) from exc

    if process.returncode != 0:
        InfrahubRepositoryBase._raise_enriched_error_static(
            name=name, location=url, error=GitCommandError(command, process.returncode, error_output.decode())
        )

    listing = output.decode()
    heads: dict[str, str] = {}
    for line in listing.splitlines():
        commit, _, ref = line.partition("\t")
        # Git matches a pattern against the end of a ref, so a longer ref can answer for a requested one.
        if ref in refs:
            heads[ref.removeprefix(BRANCH_REF_PREFIX)] = commit
    return heads


class GitRemoteHeadReader:
    """Reads the remote heads with ``git ls-remote``, bounded in time."""

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        return await list_remote_heads(
            name=repository_name, url=location, branch_names=branch_names, timeout_seconds=self.timeout_seconds
        )


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


def ensure_write_access(name: str, url: str) -> None:
    """Confirm the credentials can push to the remote, not only read from it.

    Authorization to ``receive-pack`` is checked before refs are advertised, so a dry-run
    delete of a throwaway ref reaches the write-gated service while ``--dry-run`` sends no
    ref update and no pack. The remote is never mutated, even when the probe ref happens to
    exist on it. ``git push`` needs a repository to run from - unlike ``ls-remote`` - so the
    probe runs from a throwaway ``git init``-ed directory.

    Raises:
        RepositoryPermissionError: When the credentials authenticate but are not allowed to push.
        RepositoryCredentialsError: When the push service rejects the credentials.
        RepositoryConnectionError: When the remote is unreachable.
        RepositoryError: For any other git failure.

    """
    with tempfile.TemporaryDirectory() as probe_dir:
        cmd = git.cmd.Git(working_dir=probe_dir)
        try:
            cmd.init()
            cmd.push("--dry-run", "--porcelain", "--delete", url, f"refs/heads/{WRITE_ACCESS_PROBE_REF}")
        except GitCommandError as exc:
            InfrahubRepositoryBase._raise_enriched_error_static(
                name=name, location=url, error=exc, is_write_operation=True
            )
