from __future__ import annotations

from pathlib import Path

from git import Repo
from infrahub_sdk.schema.repository import InfrahubPythonTransformConfig

from infrahub.git.closure_builder.python_closure import PythonClosure


def _config(*, name: str, file_path: str) -> InfrahubPythonTransformConfig:
    return InfrahubPythonTransformConfig(
        name=name,
        file_path=Path(file_path),
    )


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


def test_package_directory_floor_includes_all_python_siblings(tmp_path: Path) -> None:
    """All `.py` files under the transform's package directory are included in the closure.

    The package-directory floor catches the common transform-plus-sibling-helpers
    pattern at zero user cost. AST-precise import analysis was rejected because
    runtime imports (`importlib`, `__import__`, in-function imports) are invisible
    to it and missing one silently violates the correctness invariant.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "# entry\n")
    _write(tmp_path, "transforms/network/helpers.py", "# helper\n")
    _write(tmp_path, "transforms/network/sub/inner.py", "# inner\n")
    _write(tmp_path, "transforms/other/unrelated.py", "# unrelated\n")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/helpers.py",
        "transforms/network/sub/inner.py",
        "transforms/other/unrelated.py",
    )

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert "transforms/network/main.py" in result.dependencies
    assert "transforms/network/helpers.py" in result.dependencies
    assert "transforms/network/sub/inner.py" in result.dependencies
    assert "transforms/other/unrelated.py" not in result.dependencies
    assert result.complete is True
    assert result.unresolved == ()


def test_pyc_files_are_excluded(tmp_path: Path) -> None:
    """Bytecode artifacts must not appear in the stored closure.

    `.pyc` files are not source inputs to the rendered output; including them
    would create false positives in the regeneration gate when Python touches
    its cache.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/cached.pyc", "")
    _track(repo, "transforms/network/main.py", "transforms/network/cached.pyc")

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert "transforms/network/cached.pyc" not in result.dependencies


def test_pycache_directory_is_excluded(tmp_path: Path) -> None:
    """The `__pycache__/` directory is excluded from the closure regardless of git tracking.

    `__pycache__/` is a runtime artifact directory and should never feed the
    regeneration decision.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/__pycache__/main.cpython-313.pyc", "")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/__pycache__/main.cpython-313.pyc",
    )

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert not any("__pycache__" in entry for entry in result.dependencies)


def test_gitignored_files_are_excluded(tmp_path: Path) -> None:
    """Files matched by `.gitignore` do not enter the closure.

    The closure must match what git considers part of the repository so that
    the read-side intersection against `repo_diff.files_*` cannot diverge from
    the write-side dependency list.
    """
    repo = _init_repo(tmp_path, gitignore="transforms/network/secret.py\n")
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/secret.py", "")
    _track(repo, "transforms/network/main.py")

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert "transforms/network/secret.py" not in result.dependencies


def test_repo_root_transform_collapses_to_entry_file(tmp_path: Path) -> None:
    """A transform at the repository root must not pull every tracked file into its closure.

    The package-directory floor has no parent to bound below the entry file when
    the transform sits at the root, so the closure collapses to the entry file
    only. Including the whole repository would defeat the precise-regeneration
    gate entirely for any root-level transform.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "root_transform.py", "")
    _write(tmp_path, "unrelated/sibling.py", "")
    _write(tmp_path, "README.md", "")
    _track(repo, "root_transform.py", "unrelated/sibling.py", "README.md")

    result = PythonClosure().build(
        transform_config=_config(name="root", file_path="root_transform.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("root_transform.py",)
    assert result.complete is True


def test_git_enumeration_failure_flips_complete_false(tmp_path: Path) -> None:
    """When git cannot enumerate tracked files, the closure falls back with `complete=False`.

    The package-directory floor relies on `git ls-files` to enumerate. If the
    worktree is not a git repository (or the command fails), returning a trusted
    one-file closure would cause the regeneration gate to silently skip
    regenerations for any real sibling change. Flipping the trust bit forces the
    pipeline to fall back to the coarser file-change gate.
    """
    _write(tmp_path, "transforms/network/main.py", "")

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("transforms/network/main.py",)
    assert result.complete is False
    assert any(
        ref.file == "transforms/network/main.py" and ref.location == "git enumeration failed"
        for ref in result.unresolved
    )


def test_dependencies_are_sorted(tmp_path: Path) -> None:
    """Returned dependencies are lexicographically sorted for byte-stable storage."""
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/zeta.py", "")
    _write(tmp_path, "transforms/network/alpha.py", "")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/zeta.py",
        "transforms/network/alpha.py",
    )

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    expected_subset = ["transforms/network/alpha.py", "transforms/network/main.py", "transforms/network/zeta.py"]
    deps = list(result.dependencies)
    assert deps == sorted(deps)
    for entry in expected_subset:
        assert entry in deps
