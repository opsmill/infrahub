from __future__ import annotations

from typing import TYPE_CHECKING

from git import Repo

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult

if TYPE_CHECKING:
    import logging
    from pathlib import Path

    from infrahub.git.closure_builder.protocols import TransformConfig


def union_watch_files(
    *,
    result: ClosureResult,
    transform_config: TransformConfig,
    worktree_root: Path,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> ClosureResult:
    """Merge a transform's user-declared ``watch.files`` into its auto-detected closure.

    Directory entries are expanded recursively to the git-tracked files beneath them;
    symlinks, ``.pyc`` files and ``__pycache__`` entries are skipped, and gitignored
    paths are naturally absent because the expansion is driven by ``git ls-files``.

    When the user declares any watch files the closure is treated as complete: the user
    has taken responsibility for declaring the dependencies auto-detection cannot see, so
    ``complete`` becomes True even when auto-detection left unresolved references behind.
    A declared entry that matches no tracked file (typically a typo) cannot extend the
    closure but still counts as a declaration, so completeness is unaffected; the entry is
    logged as a warning so the mismatch is visible rather than silently under-regenerating.

    Raises:
        git.exc.GitCommandError: If git cannot enumerate a watch entry (for example a
            pathspec that escapes the repository). The caller isolates this so the
            transform's closure falls back to ``complete=False`` rather than aborting.

    """
    watch = transform_config.watch
    if watch is None or not watch.files:
        return result

    expanded = _expand_watch_files(
        watch_files=watch.files,
        worktree_root=worktree_root,
        transform_name=transform_config.name,
        logger=logger,
    )
    merged = tuple(sorted(set(result.dependencies) | expanded))
    return ClosureResult(dependencies=merged, complete=True, unresolved=result.unresolved)


def _expand_watch_files(
    *,
    watch_files: list[str],
    worktree_root: Path,
    transform_name: str,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> set[str]:
    repo = Repo(worktree_root)
    expanded: set[str] = set()

    for entry in watch_files:
        canonical_entry = canonicalize_path(entry)
        # A directory pathspec lists every tracked file beneath it; a file pathspec lists
        # just itself. Gitignored paths are untracked and so are never returned. The ``--``
        # separates options from the pathspec so an entry beginning with ``-`` is not
        # parsed as a git option.
        output = repo.git.ls_files("--", canonical_entry)
        tracked = [line for line in output.splitlines() if line]
        if not tracked:
            logger.warning(
                f"watch.files entry {entry!r} on transform {transform_name!r} matched no tracked file; "
                f"it does not extend the dependency closure. Check the path for typos."
            )
            continue
        for line in tracked:
            canonical = canonicalize_path(line)
            if canonical.endswith(".pyc") or "__pycache__" in canonical.split("/"):
                continue
            # A symlink is not followed: its target may escape the repository, and the
            # user is the right authority on whether the real file should be watched.
            if (worktree_root / canonical).is_symlink():
                continue
            expanded.add(canonical)

    return expanded
