from __future__ import annotations

from pathlib import Path

from git import Repo
from infrahub_sdk.schema.repository import (
    InfrahubPythonTransformConfig,
    InfrahubWatchConfig,
)

from infrahub.git.closure_builder.result import ClosureResult, UnresolvedRef
from infrahub.git.closure_builder.watch import union_watch_files


def _init_repo(root: Path, *, gitignore: str = "") -> Repo:
    repo = Repo.init(root)
    if gitignore:
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")
        repo.index.add([".gitignore"])
        repo.index.commit("seed gitignore")
    return repo


def _write(root: Path, rel: str, content: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _track(repo: Repo, *rels: str) -> None:
    repo.index.add(list(rels))
    repo.index.commit("seed")


def _config(*, watch: list[str] | None) -> InfrahubPythonTransformConfig:
    return InfrahubPythonTransformConfig(
        name="net",
        file_path=Path("transforms/network/main.py"),
        watch=InfrahubWatchConfig(files=watch) if watch is not None else None,
    )


def test_directory_entry_expands_recursively(tmp_path: Path) -> None:
    """A directory in `watch.files` pulls in every tracked file beneath it, at any depth.

    Directory entries are the primary way a user declares a dependency that
    auto-detection cannot see (a folder of dynamically included partials), so the
    expansion must reach nested files, not just the directory's immediate children.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "templates/partials/header.j2", "")
    _write(tmp_path, "templates/partials/nested/footer.j2", "")
    _write(tmp_path, "templates/other/unrelated.j2", "")
    _track(
        repo,
        "templates/partials/header.j2",
        "templates/partials/nested/footer.j2",
        "templates/other/unrelated.j2",
    )

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["templates/partials"]),
        worktree_root=tmp_path,
    )

    assert "templates/partials/header.j2" in result.dependencies
    assert "templates/partials/nested/footer.j2" in result.dependencies
    assert "templates/other/unrelated.j2" not in result.dependencies


def test_watch_files_union_with_auto_detected_closure(tmp_path: Path) -> None:
    """Watch entries extend, never replace, the auto-detected closure.

    The stored dependency list is the union of what Infrahub detected and what the
    user declared, so a transform's own source and its declared extras both gate
    regeneration.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "utils/helper.py", "")
    _track(repo, "utils/helper.py")

    result = union_watch_files(
        result=ClosureResult(dependencies=("transforms/network/main.py",), complete=True, unresolved=()),
        transform_config=_config(watch=["utils/helper.py"]),
        worktree_root=tmp_path,
    )

    assert "transforms/network/main.py" in result.dependencies
    assert "utils/helper.py" in result.dependencies


def test_nonempty_watch_flips_complete_true_after_incomplete_autodetection(tmp_path: Path) -> None:
    """Declaring watch files marks the closure trusted even when auto-detection fell short.

    When auto-detection could not resolve every reference it returns
    `complete=False`, which forces the coarse regenerate-on-any-change fallback. A
    user who declares the missing dependencies via `watch.files` is taking
    responsibility for completeness, so the closure is trusted again. The unresolved
    references are kept for diagnostics.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "templates/partials/header.j2", "")
    _track(repo, "templates/partials/header.j2")

    incomplete = ClosureResult(
        dependencies=("templates/device.j2",),
        complete=False,
        unresolved=(UnresolvedRef(file="templates/device.j2", location="dynamic include"),),
    )

    result = union_watch_files(
        result=incomplete,
        transform_config=_config(watch=["templates/partials"]),
        worktree_root=tmp_path,
    )

    assert result.complete is True
    assert result.unresolved == incomplete.unresolved
    assert "templates/partials/header.j2" in result.dependencies


def test_each_entry_is_canonicalized(tmp_path: Path) -> None:
    """A watch entry is canonicalized before lookup, so non-canonical forms still resolve.

    Users write paths the way `.gitignore` accepts them - with a leading slash for
    the repository root - so a leading slash must be stripped to a repo-relative
    pathspec rather than treated as an absolute filesystem path that matches nothing.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "utils/helper.py", "")
    _track(repo, "utils/helper.py")

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["/utils/helper.py"]),
        worktree_root=tmp_path,
    )

    assert "utils/helper.py" in result.dependencies


def test_symlinks_under_a_watched_directory_are_skipped(tmp_path: Path) -> None:
    """A symlink inside a watched directory is not added to the closure.

    Following a symlink could escape the repository and add files outside the
    worktree to the closure; the user is the right authority on whether the real
    target should be watched, so the link itself is silently dropped.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "templates/partials/real.j2", "")
    (tmp_path / "templates/partials/alias.j2").symlink_to(tmp_path / "templates/partials/real.j2")
    _track(repo, "templates/partials/real.j2", "templates/partials/alias.j2")

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["templates/partials"]),
        worktree_root=tmp_path,
    )

    assert "templates/partials/real.j2" in result.dependencies
    assert "templates/partials/alias.j2" not in result.dependencies


def test_pyc_pycache_and_gitignored_files_are_excluded(tmp_path: Path) -> None:
    """Bytecode, cache directories, and gitignored files never enter the closure via watch.

    Watch entries must obey the same exclusions as auto-detection so the stored
    closure stays aligned with what git considers part of the repository and cannot
    trigger regeneration on runtime artifacts.
    """
    repo = _init_repo(tmp_path, gitignore="utils/secret.py\n")
    _write(tmp_path, "utils/helper.py", "")
    _write(tmp_path, "utils/cached.pyc", "")
    _write(tmp_path, "utils/__pycache__/helper.cpython-313.pyc", "")
    _write(tmp_path, "utils/secret.py", "")
    _track(
        repo,
        "utils/helper.py",
        "utils/cached.pyc",
        "utils/__pycache__/helper.cpython-313.pyc",
    )

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["utils"]),
        worktree_root=tmp_path,
    )

    assert "utils/helper.py" in result.dependencies
    assert "utils/cached.pyc" not in result.dependencies
    assert not any("__pycache__" in entry for entry in result.dependencies)
    assert "utils/secret.py" not in result.dependencies


def test_absent_watch_returns_the_auto_detected_result_unchanged(tmp_path: Path) -> None:
    """With no `watch:` block the auto-detected closure is returned verbatim.

    The completeness flag must reflect auto-detection alone when the user declared
    nothing, so an incomplete closure stays incomplete and falls back to the coarse
    gate.
    """
    auto = ClosureResult(
        dependencies=("templates/device.j2",),
        complete=False,
        unresolved=(UnresolvedRef(file="templates/device.j2", location="dynamic include"),),
    )

    result = union_watch_files(
        result=auto,
        transform_config=_config(watch=None),
        worktree_root=tmp_path,
    )

    assert result is auto


def test_empty_watch_files_list_returns_the_auto_detected_result_unchanged(tmp_path: Path) -> None:
    """An empty `watch: { files: [] }` block is a no-op and does not flip completeness."""
    auto = ClosureResult(
        dependencies=("templates/device.j2",),
        complete=False,
        unresolved=(),
    )

    result = union_watch_files(
        result=auto,
        transform_config=_config(watch=[]),
        worktree_root=tmp_path,
    )

    assert result is auto
    assert result.complete is False
