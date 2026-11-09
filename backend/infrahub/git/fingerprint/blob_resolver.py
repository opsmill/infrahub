"""Resolve repo-relative paths to their git blob SHAs from the tree at a commit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from git import Repo


class BlobResolver(Protocol):
    """Resolve repo-relative paths to sorted `(path, blob_sha)` pairs."""

    def resolve(self, paths: Sequence[str]) -> list[tuple[str, str]]: ...


class GitBlobResolver:
    """Resolve `(repo_relative_path, git_blob_sha)` pairs from the git tree at a commit.

    Only git metadata (the tree entries) is read; file contents are never loaded.
    """

    def __init__(self, *, repo: Repo, commit: str) -> None:
        self._repo = repo
        self._commit = commit

    def resolve(self, paths: Sequence[str]) -> list[tuple[str, str]]:
        """Return the sorted `(path, blob_sha)` pairs for the given paths.

        A path with no corresponding tree entry resolves to an empty SHA so the path
        still contributes to the ordering and reappears distinctly once it is tracked.
        """
        tree = self._repo.commit(self._commit).tree
        resolved: list[tuple[str, str]] = []
        for path in paths:
            try:
                entry = tree / path
            except KeyError:
                resolved.append((path, ""))
                continue
            resolved.append((path, entry.hexsha))
        return sorted(resolved)
