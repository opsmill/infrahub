from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from git import BadName
from git.exc import GitCommandError

from infrahub.exceptions import RepositoryError

if TYPE_CHECKING:
    from git import Repo


class AncestryGateway(Protocol):
    """Answers ancestry questions about one repository's object database.

    Implementations raise RepositoryError for every git failure, so a caller handles one
    exception type and imports no git library.
    """

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool: ...

    def has_commit(self, commit: str) -> bool: ...


class GitPythonAncestryGateway:
    def __init__(self, repository_name: str, repo: Repo) -> None:
        self.repository_name = repository_name
        self.repo = repo

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool:
        """Whether ancestor_commit is reachable from descendant_commit.

        Raises:
            RepositoryError: When git could not answer, including when either commit is absent.

        """
        try:
            return self.repo.is_ancestor(
                ancestor_rev=self.repo.commit(ancestor_commit), rev=self.repo.commit(descendant_commit)
            )
        except GitCommandError as exc:
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=exc.stderr or str(exc)
            ) from exc
        except (BadName, ValueError) as exc:
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=str(exc)
            ) from exc

    def _comparison_failed(self, ancestor_commit: str, descendant_commit: str, detail: str) -> RepositoryError:
        return RepositoryError(
            identifier=self.repository_name,
            message=f"Unable to compare {ancestor_commit} against {descendant_commit}: {detail}",
        )

    def has_commit(self, commit: str) -> bool:
        """Whether the object is present in the local object database.

        A caller needs this separately from is_ancestor because a commit that is merely absent and
        a git call that could not run both surface as the same error from the ancestry check.

        Raises:
            RepositoryError: When the identifier is not a well-formed object name.

        """
        try:
            binary_sha = bytes.fromhex(commit)
        except ValueError as exc:
            raise RepositoryError(
                identifier=self.repository_name, message=f"{commit!r} is not a valid commit identifier"
            ) from exc

        try:
            self.repo.odb.info(binary_sha)
        except ValueError:
            # The object database reports an absent object by refusing to resolve its sha.
            return False
        return True
