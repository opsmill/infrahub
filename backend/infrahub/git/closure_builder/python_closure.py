from __future__ import annotations

from typing import TYPE_CHECKING

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.schema.repository import InfrahubPythonTransformConfig


class PythonClosure:
    """Compute a Python transform's dependency closure as the package-directory floor.

    The closure is every git-tracked file under the directory containing the
    transform's ``file_path``, minus ``.pyc`` files and ``__pycache__/`` entries.
    A transform that sits at the repository root collapses to its own file
    instead of pulling in the entire repository.
    """

    def build(
        self,
        transform_config: InfrahubPythonTransformConfig,
        worktree_root: Path,
    ) -> ClosureResult:
        entry_path = canonicalize_path(str(transform_config.file_path))

        if "/" not in entry_path:
            return ClosureResult(dependencies=(entry_path,), complete=True, unresolved=())

        package_dir = entry_path.rsplit("/", 1)[0]

        try:
            repo = Repo(worktree_root)
            output = repo.git.ls_files(package_dir)
        except (InvalidGitRepositoryError, GitCommandError):
            return ClosureResult(dependencies=(entry_path,), complete=True, unresolved=())

        dependencies: list[str] = []
        for line in output.splitlines():
            if not line:
                continue
            canonical = canonicalize_path(line)
            if canonical.endswith(".pyc") or "__pycache__" in canonical.split("/"):
                continue
            dependencies.append(canonical)

        sorted_unique = tuple(sorted(set(dependencies)))
        return ClosureResult(
            dependencies=sorted_unique,
            complete=True,
            unresolved=(),
        )
