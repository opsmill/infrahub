from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from git import Repo
from infrahub_sdk.schema.repository import (
    InfrahubGeneratorDefinitionConfig,
    InfrahubPythonTransformConfig,
    InfrahubWatchConfig,
)

from infrahub.git.closure_builder.result import ClosureResult, UnresolvedRef
from infrahub.git.closure_builder.watch import union_watch_files

if TYPE_CHECKING:
    import pytest

LOGGER = logging.getLogger(__name__)


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


def _generator_config(*, watch: list[str] | None) -> InfrahubGeneratorDefinitionConfig:
    return InfrahubGeneratorDefinitionConfig(
        name="gen",
        file_path=Path("generators/widget/main.py"),
        query="some_query",
        targets="some_group",
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
        logger=LOGGER,
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
        logger=LOGGER,
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
        logger=LOGGER,
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
        logger=LOGGER,
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
        logger=LOGGER,
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
        logger=LOGGER,
    )

    assert "utils/helper.py" in result.dependencies
    assert "utils/cached.pyc" not in result.dependencies
    assert not any("__pycache__" in entry for entry in result.dependencies)
    assert "utils/secret.py" not in result.dependencies


def test_entry_matching_no_tracked_file_is_warned_and_keeps_completeness(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A watch entry that matches nothing is logged but still counts as a declaration.

    A typo'd or non-existent entry cannot extend the closure, but the completeness
    rule is "any watch.files declared", so the closure stays complete by design (the
    user has opted into trusting their declaration). The mismatch is surfaced as a
    warning so it does not silently cause under-regeneration rather than being lost.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "utils/config.yaml", "")
    _track(repo, "utils/config.yaml")

    with caplog.at_level(logging.WARNING):
        result = union_watch_files(
            result=ClosureResult(dependencies=("transforms/network/main.py",), complete=False, unresolved=()),
            transform_config=_config(watch=["utils/config.yml"]),
            worktree_root=tmp_path,
            logger=LOGGER,
        )

    assert result.complete is True
    assert "utils/config.yml" not in result.dependencies
    assert "matched no tracked file" in caplog.text
    assert "utils/config.yml" in caplog.text


def test_a_closure_that_stays_empty_is_never_trusted(tmp_path: Path) -> None:
    """An empty closure stays incomplete even though the user declared watch files.

    An empty closure names no file, so no change can ever intersect it and the definition
    would stop regenerating for good instead of falling back to regenerating on any file
    change. Auto-detection finding nothing and every declared entry matching nothing is a
    broken declaration, not a closed list.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "utils/config.yaml", "")
    _track(repo, "utils/config.yaml")

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["utils/config.yml"]),
        worktree_root=tmp_path,
        logger=LOGGER,
    )

    assert result.dependencies == ()
    assert result.complete is False


def test_entry_beginning_with_dash_is_treated_as_a_path(tmp_path: Path) -> None:
    """A watch entry starting with `-` is a path, not a git option.

    `git ls-files` is invoked with `--` separating options from the pathspec, so an
    unusual but legal filename beginning with a hyphen still resolves instead of being
    parsed as a flag (which would error and drop the whole closure to incomplete).
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "-weird/helper.py", "")
    _track(repo, "-weird/helper.py")

    result = union_watch_files(
        result=ClosureResult(dependencies=(), complete=True, unresolved=()),
        transform_config=_config(watch=["-weird/"]),
        worktree_root=tmp_path,
        logger=LOGGER,
    )

    assert "-weird/helper.py" in result.dependencies


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
        logger=LOGGER,
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
        logger=LOGGER,
    )

    assert result is auto
    assert result.complete is False


def test_generator_config_flows_through_watch_union(tmp_path: Path) -> None:
    """A generator config is accepted by the watch union and drives the same closure behavior as a transform.

    The union step reads `watch` off whichever config it is given, so the only generator-specific risk is
    that the generator config is accepted at all; the recursion, artifact exclusion, and completeness rules
    are the shared code exercised by the transform variants. This proves the generator path end-to-end: a
    directory entry expands recursively while skipping `.pyc`/`__pycache__`/symlinks, and declaring a
    non-empty `watch.files` flips an incomplete closure back to trusted.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "shared/util.py", "")
    _write(tmp_path, "shared/nested/more.py", "")
    _write(tmp_path, "shared/cached.pyc", "")
    _write(tmp_path, "shared/__pycache__/util.cpython-313.pyc", "")
    (tmp_path / "shared/alias.py").symlink_to(tmp_path / "shared/util.py")
    _track(
        repo,
        "shared/util.py",
        "shared/nested/more.py",
        "shared/cached.pyc",
        "shared/__pycache__/util.cpython-313.pyc",
        "shared/alias.py",
    )

    incomplete = ClosureResult(
        dependencies=("generators/widget/main.py",),
        complete=False,
        unresolved=(UnresolvedRef(file="generators/widget/main.py", location="git enumeration failed"),),
    )

    result = union_watch_files(
        result=incomplete,
        transform_config=_generator_config(watch=["shared/"]),
        worktree_root=tmp_path,
        logger=LOGGER,
    )

    assert result.complete is True
    assert result.unresolved == incomplete.unresolved
    assert "generators/widget/main.py" in result.dependencies
    assert "shared/util.py" in result.dependencies
    assert "shared/nested/more.py" in result.dependencies
    assert "shared/cached.pyc" not in result.dependencies
    assert not any("__pycache__" in entry for entry in result.dependencies)
    assert "shared/alias.py" not in result.dependencies
