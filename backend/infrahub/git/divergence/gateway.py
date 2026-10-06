from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from git.exc import GitCommandError, GitError

from infrahub.exceptions import RepositoryError

if TYPE_CHECKING:
    from git import Repo

COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")

GITPYTHON_STDERR_PREFIX = "stderr: '"
"""GitPython wraps the text git wrote in a newline, this prefix and a closing quote."""

OBJECT_ABSENT_STATUS = 1
"""What `git rev-parse --verify` returns for a name that answers to no commit.

Git returns the same status when it holds the object in a store it cannot read, so a pack it is
denied looks exactly like a pruned commit. Every store the commit could sit in is read before an
absence is reported, because git skips an unreadable store without saying so.
"""

PACK_FILE_SUFFIXES = (".idx", ".pack")
"""The pack files git must open to answer for a packed object.

Git drops the whole pack when it cannot read the index, and reports the object absent when it
cannot read the pack itself. Its other files are caches, and git answers without them.
"""

NOT_AN_ANCESTOR_STATUS = 1
"""What `git merge-base --is-ancestor` returns for a true comparison with a false answer."""


def readable_commit(commit: str | None) -> str | None:
    """Return a commit the graph records, or None when the value is empty or not a full commit id."""
    return commit if commit and COMMIT_SHA_PATTERN.fullmatch(commit) else None


class GitAncestryGateway:
    def __init__(self, repository_name: str, repo: Repo) -> None:
        self.repository_name = repository_name
        self.repo = repo

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool:
        """Whether ancestor_commit is reachable from descendant_commit.

        Raises:
            RepositoryError: When git could not answer, including when either commit is absent.

        """
        self._require_full_sha(commit=ancestor_commit)
        self._require_full_sha(commit=descendant_commit)

        try:
            # The shared object reader fails on its own terms, so ask git directly.
            self.repo.git.merge_base("--is-ancestor", ancestor_commit, descendant_commit)
        except GitCommandError as exc:
            if exc.status == NOT_AN_ANCESTOR_STATUS:
                return False
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=self._git_detail(exc)
            ) from exc
        except (OSError, GitError) as exc:
            raise self._comparison_failed(
                ancestor_commit=ancestor_commit, descendant_commit=descendant_commit, detail=str(exc)
            ) from exc
        return True

    def has_commit(self, commit: str) -> bool:
        """Whether a commit of that name is present in the local object database.

        An absent commit and a git call that could not run are the same error once a comparison
        raises, so the two are told apart here instead. A name that answers to a tree, a blob or an
        annotated tag holds no commit, so it reports absent.

        Raises:
            RepositoryError: When the identifier is not a full object name, when git could not be
                asked, or when a store the commit could sit in is unreadable.

        """
        self._require_full_sha(commit=commit)

        try:
            # Peeling to a commit answers presence and kind together, in one process.
            resolved = self.repo.git.rev_parse("--verify", "--quiet", f"{commit}^{{commit}}")
        except GitCommandError as exc:
            if exc.status == OBJECT_ABSENT_STATUS:
                # A false absence is recorded as a rewrite, so prove git read every store.
                self._require_a_readable_object_database(commit=commit)
                return False
            raise self._read_failed(commit=commit, detail=self._git_detail(exc)) from exc
        except (OSError, GitError) as exc:
            raise self._read_failed(commit=commit, detail=str(exc)) from exc

        # Peeling walks an annotated tag through to its commit, so a name that resolves to
        # another object is not a commit itself.
        return str(resolved).strip() == commit

    def _require_a_readable_object_database(self, commit: str) -> None:
        """Reject an absence git reports because it cannot read where the commit would sit.

        Raises:
            RepositoryError: When any store git searches for the commit is unreadable.

        """
        try:
            directories = self._object_directories()
        except (OSError, GitError) as exc:
            raise self._read_failed(commit=commit, detail=f"the object database is unreadable: {exc}") from exc

        for directory in directories:
            unreadable = self._unreadable_store(directory=directory, commit=commit)
            if unreadable is not None:
                raise self._read_failed(commit=commit, detail=f"{unreadable} is unreadable")

    def _object_directories(self) -> list[Path]:
        """Every object directory git searches, the ones borrowed through alternates included."""
        # A worktree keeps its objects in the common directory, so ask git where they are.
        objects = str(self.repo.git.rev_parse("--git-path", "objects")).strip()
        pending = [Path(self.repo.working_dir or self.repo.common_dir) / objects]
        directories: list[Path] = []
        seen: set[Path] = set()

        while pending:
            directory = pending.pop().resolve()
            if directory in seen:
                continue
            seen.add(directory)
            directories.append(directory)
            pending.extend(self._alternates_of(directory=directory))

        return directories

    def _alternates_of(self, directory: Path) -> list[Path]:
        try:
            content = (directory / "info" / "alternates").read_bytes()
        except FileNotFoundError:
            return []
        # The file holds filesystem paths, so decode it the way the system decodes a path.
        lines = os.fsdecode(content).splitlines()
        # A relative alternate path starts from the object directory that lists it.
        return [directory / line for line in lines if line and not line.startswith("#")]

    def _unreadable_store(self, directory: Path, commit: str) -> Path | None:
        """Return the first part of an object directory git cannot read, or None when it reads all."""
        if not directory.is_dir():
            return directory

        pack_directory = directory / "pack"
        try:
            packs = sorted(path for path in pack_directory.iterdir() if path.suffix in PACK_FILE_SUFFIXES)
        except FileNotFoundError:
            packs = []
        except OSError:
            return pack_directory

        for path in (*packs, directory / commit[:2] / commit[2:]):
            if not self._opens(path=path):
                return path
        return None

    def _opens(self, path: Path) -> bool:
        try:
            with path.open("rb"):
                return True
        except FileNotFoundError:
            # A file that is not there holds no object, so it hides none either.
            return True
        except OSError:
            return False

    def require_present_commit(self, commit: str) -> None:
        """Reject a commit the local object database does not hold.

        Raises:
            RepositoryError: When the identifier is not a full object name, when git could not be
                asked, or when the object database holds no such commit.

        """
        if not self.has_commit(commit=commit):
            raise self._read_failed(commit=commit, detail="the object is absent")

    def require_commit(self, commit: str) -> None:
        """Reject an identifier git would read as a name rather than a commit.

        Raises:
            RepositoryError: When the identifier is not forty lowercase hexadecimal characters.

        """
        self._require_full_sha(commit=commit)

    def _require_full_sha(self, commit: str) -> None:
        if not COMMIT_SHA_PATTERN.fullmatch(commit):
            raise RepositoryError(
                identifier=self.repository_name, message=f"{commit!r} is not a valid commit identifier"
            )

    def _git_detail(self, exc: GitCommandError) -> str:
        text = (exc.stderr or "").strip()
        if text.startswith(GITPYTHON_STDERR_PREFIX):
            text = text[len(GITPYTHON_STDERR_PREFIX) :].removesuffix("'")
        return text or str(exc)

    def _comparison_failed(self, ancestor_commit: str, descendant_commit: str, detail: str) -> RepositoryError:
        return RepositoryError(
            identifier=self.repository_name,
            message=f"Unable to compare {ancestor_commit} against {descendant_commit}: {detail}",
        )

    def _read_failed(self, commit: str, detail: str) -> RepositoryError:
        return RepositoryError(
            identifier=self.repository_name,
            message=f"Unable to read {commit} from the object database: {detail}",
        )
