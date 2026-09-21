"""The git side of the refs check: the only module here that touches a repository on disk.

Every failure leaves as a ``RepositoryError``, so the decision logic never handles a git exception
and never imports the library that raises one.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from git.cmd import Git
from git.exc import BadName, GitError

from infrahub.exceptions import RepositoryError

from ..repository import InfrahubReadOnlyRepository
from .constants import REMOTE_TRANSPORT_ENVIRONMENT
from .models import RefHeads

if TYPE_CHECKING:
    from collections.abc import Iterator

    from git import Repo
    from infrahub_sdk.client import InfrahubClient

    from ..models import GitReadOnlyRepositoryCheckRefs

CheckRefFormat = Callable[[str], bool]
"""Decides whether git would accept a ref name. Must be synchronous: it is run in a worker thread."""

RemoteLister = Callable[[list[str]], str]
"""Runs one ``ls-remote`` for the given fully qualified patterns and returns its raw output."""


def git_check_ref_format(ref: str) -> bool:
    try:
        # --allow-onelevel: tracked refs are short names such as "main" or "release", which
        # check-ref-format rejects without it.
        Git().check_ref_format("--allow-onelevel", ref)
    except GitError:
        # GitCommandError means git rejected the name. Its siblings, such as a missing git binary,
        # mean the name could not be judged; both leave the ref unusable for this check.
        return False
    return True


def parse_ls_remote(output: str) -> dict[str, str]:
    """Map each fully qualified ref name in a listing to its hash.

    Lines carrying no ref name are dropped: git writes transport notices such as a redirect
    warning onto the same stream, and they are not part of the listing.
    """
    heads = {}
    for raw_line in output.splitlines():
        sha, separator, ref_name = raw_line.partition("\t")
        if separator:
            heads[ref_name.strip()] = sha.strip()
    return heads


def select_remote_head(heads: Mapping[str, str], ref: str) -> str | None:
    """Return the remote head for ``ref``, a branch of that name taking precedence over a tag.

    A name can exist in both namespaces, and nothing in the listing says which one the repository
    follows, so the precedence here has to be the same one the local read applies. An annotated tag
    resolves through its peeled commit, since that is the object a local read of a tag yields.
    """
    for candidate in (f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}"):
        if candidate in heads:
            return heads[candidate]
    return None


@contextmanager
def _as_repository_error(repository_name: str) -> Iterator[None]:
    """Present any git failure as the one exception type the refs check handles.

    Raises:
        RepositoryError: in place of whatever git raised.

    """
    try:
        yield
    except GitError as exc:
        raise RepositoryError(identifier=repository_name, message=str(exc)) from exc


class RepositoryRefsGateway(Protocol):
    """Every git operation the check performs, so the check itself holds no git code.

    Raises:
        RepositoryError: for every git or filesystem failure, so callers handle one exception type.

    """

    async def read_heads(
        self, model: GitReadOnlyRepositoryCheckRefs, refs: tuple[str, ...]
    ) -> tuple[RefHeads, ...]: ...

    async def fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None: ...


def _resolve_local_head(git_repo: Repo, ref: str) -> str | None:
    # Remote-tracking branch before tag, which is the precedence the remote listing also applies;
    # reordering these two would make the two sides resolve different objects for one name.
    for candidate in (f"origin/{ref}", ref):
        try:
            return str(git_repo.commit(candidate))
        except (BadName, ValueError):
            continue
    return None


def _fetch_moved_refs(git_repo: Repo, *, kill_after_seconds: float) -> None:
    """Bring the moved refs in, forcing tag updates rather than refusing them.

    git refuses to update an existing tag without being forced. The commits a moved tag used to
    point at stay readable because each imported commit has a worktree of its own holding it.
    """
    with git_repo.git.custom_environment(**REMOTE_TRANSPORT_ENVIRONMENT):
        git_repo.remotes.origin.fetch(
            prune=True, tags=True, prune_tags=True, force=True, kill_after_timeout=kill_after_seconds
        )


def _ref_patterns(ref: str) -> tuple[str, str, str]:
    # The third is the peeled line an annotated tag also publishes. Without it the listing returns
    # the tag object while the local read returns the commit, and the two can never agree.
    return (f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}")


def _list_remote_heads(list_remote: RemoteLister, refs: tuple[str, ...]) -> dict[str, str | None]:
    """Resolve every ref against the remote in one listing."""
    if not refs:
        # An ls-remote with no pattern lists the entire remote, which is not what an empty request
        # is asking for.
        return {}

    patterns = [pattern for ref in refs for pattern in _ref_patterns(ref)]
    heads = parse_ls_remote(list_remote(patterns))
    return {ref: select_remote_head(heads, ref) for ref in refs}


def _ls_remote(git_repo: Repo, *, kill_after_seconds: float) -> RemoteLister:
    """Bind one repository's origin to a listing call.

    ``kill_after_seconds`` is what actually bounds it: git applies no network timeout of its own,
    and abandoning the caller's await would leave the process running.
    """

    def run(patterns: list[str]) -> str:
        with git_repo.git.custom_environment(**REMOTE_TRANSPORT_ENVIRONMENT):
            return str(git_repo.git.ls_remote("origin", "--", *patterns, kill_after_timeout=kill_after_seconds))

    return run


class GitRepositoryRefsGateway:
    """Reads refs from an existing local copy and from its remote, and fetches when told to.

    The local copy is opened without initialization, so a refs check never clones and never pulls.
    """

    def __init__(
        self, client: InfrahubClient, *, list_kill_after_seconds: float, fetch_kill_after_seconds: float
    ) -> None:
        self._client = client
        self._list_kill_after_seconds = list_kill_after_seconds
        self._fetch_kill_after_seconds = fetch_kill_after_seconds

    def _open(self, model: GitReadOnlyRepositoryCheckRefs) -> InfrahubReadOnlyRepository:
        repo = InfrahubReadOnlyRepository(  # type: ignore[call-arg]
            id=UUID(model.repository_id),
            name=model.repository_name,
            location=model.location,
            client=self._client,
        )
        # Also what sets has_origin, by inspecting the remotes on disk.
        repo.validate_local_directories()
        return repo

    def _read_heads(self, model: GitReadOnlyRepositoryCheckRefs, refs: tuple[str, ...]) -> tuple[RefHeads, ...]:
        git_repo = self._open(model).get_git_repo_main()
        local_heads = {ref: _resolve_local_head(git_repo, ref) for ref in refs}
        remote_heads = _list_remote_heads(_ls_remote(git_repo, kill_after_seconds=self._list_kill_after_seconds), refs)
        return tuple(RefHeads(ref=ref, local_head=local_heads[ref], remote_head=remote_heads[ref]) for ref in refs)

    def _fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        repo = self._open(model)
        if not repo.has_origin:
            raise RepositoryError(
                identifier=model.repository_name,
                message=f"The local copy of {model.repository_name} has no remote to fetch the moved refs from.",
            )
        _fetch_moved_refs(repo.get_git_repo_main(), kill_after_seconds=self._fetch_kill_after_seconds)

    async def read_heads(self, model: GitReadOnlyRepositoryCheckRefs, refs: tuple[str, ...]) -> tuple[RefHeads, ...]:
        with _as_repository_error(model.repository_name):
            return await asyncio.to_thread(self._read_heads, model, refs)

    async def fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        with _as_repository_error(model.repository_name):
            await asyncio.to_thread(self._fetch, model)
