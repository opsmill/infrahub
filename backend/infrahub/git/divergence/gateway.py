from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from git.exc import GitCommandError, GitError

from infrahub.exceptions import RepositoryError

if TYPE_CHECKING:
    from git import Repo

COMMIT_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}")

OBJECT_ABSENT_STATUS = 1
"""What `git cat-file -e` returns for a well-formed name no object answers to."""

NOT_AN_ANCESTOR_STATUS = 1
"""What `git merge-base --is-ancestor` returns for a true comparison with a false answer."""


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
            # Run as a plain command rather than through resolved objects: resolving them first
            # goes through the shared reader, which fails on its own terms.
            self.repo.git.merge_base("--is-ancestor", ancestor_commit, descendant_commit)
        except GitCommandError as exc:
            if exc.status == NOT_AN_ANCESTOR_STATUS:
                return False
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=exc.stderr or str(exc)
            ) from exc
        except (OSError, GitError) as exc:
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=str(exc)
            ) from exc
        return True

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
            RepositoryError: When the identifier is not a full object name, or when git could not
                be asked.

        """
        if not COMMIT_SHA_PATTERN.fullmatch(commit):
            raise RepositoryError(
                identifier=self.repository_name, message=f"{commit!r} is not a valid commit identifier"
            )

        try:
            # A dedicated process, so a broken shared reader cannot be read as a missing object.
            self.repo.git.cat_file("-e", commit)
        except GitCommandError as exc:
            if exc.status == OBJECT_ABSENT_STATUS:
                return False
            raise self._read_failed(commit=commit, detail=exc.stderr or str(exc)) from exc
        except (OSError, GitError) as exc:
            raise self._read_failed(commit=commit, detail=str(exc)) from exc
        return True

    def _read_failed(self, commit: str, detail: str) -> RepositoryError:
        return RepositoryError(
            identifier=self.repository_name,
            message=f"Unable to read {commit} from the object database: {detail}",
        )
