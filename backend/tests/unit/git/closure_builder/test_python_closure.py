from __future__ import annotations

import logging
from pathlib import Path

from git import Repo
from infrahub_sdk.schema.repository import (
    InfrahubGeneratorDefinitionConfig,
    InfrahubPythonTransformConfig,
    InfrahubWatchConfig,
)

from infrahub.git.closure_builder.python_closure import PythonClosure
from infrahub.git.closure_builder.watch import union_watch_files


def _config(*, name: str, file_path: str, watch: InfrahubWatchConfig | None = None) -> InfrahubPythonTransformConfig:
    return InfrahubPythonTransformConfig(
        name=name,
        file_path=Path(file_path),
        watch=watch,
    )


def _generator_config(
    *, name: str, file_path: str, watch: InfrahubWatchConfig | None = None
) -> InfrahubGeneratorDefinitionConfig:
    return InfrahubGeneratorDefinitionConfig(
        name=name,
        file_path=Path(file_path),
        query="some_query",
        targets="some_group",
        watch=watch,
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


def test_closure_is_the_entry_file_only(tmp_path: Path) -> None:
    """Files sitting next to the transform's source file stay out of its closure.

    A transform directory routinely holds several unrelated transforms with their own
    queries and helpers, so co-location is no evidence of a dependency. Auto-detection
    claims only the file the config points at; anything else is the author's to declare.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "# entry\n")
    _write(tmp_path, "transforms/network/helpers.py", "# helper\n")
    _write(tmp_path, "transforms/network/other.gql", "query {}\n")
    _write(tmp_path, "transforms/network/sub/inner.py", "# inner\n")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/helpers.py",
        "transforms/network/other.gql",
        "transforms/network/sub/inner.py",
    )

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("transforms/network/main.py",)
    assert result.complete is True
    assert result.unresolved == ()


def test_repo_root_transform_closure_is_the_entry_file(tmp_path: Path) -> None:
    """A transform at the repository root behaves like any other: only its own file."""
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


def test_closure_is_computed_without_a_git_repository(tmp_path: Path) -> None:
    """Naming the entry file needs no git enumeration, so a non-git worktree is not a failure.

    The closure no longer depends on `git ls-files`, so there is nothing left that can
    fail here and drop the result to `complete=False`.
    """
    _write(tmp_path, "transforms/network/main.py", "")

    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("transforms/network/main.py",)
    assert result.complete is True
    assert result.unresolved == ()


def test_entry_path_is_canonicalized(tmp_path: Path) -> None:
    """A config path written with a leading `./` is stored in canonical repo-relative form.

    The stored closure is intersected against git's diff output, so both sides have to
    agree on the spelling of a path.
    """
    result = PythonClosure().build(
        transform_config=_config(name="net", file_path="./transforms/network/main.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("transforms/network/main.py",)


def test_supports_generator_definition_config() -> None:
    """The Python closure builder claims generator definitions, not just transforms.

    Generators are Python sources with the same `file_path` shape, so the same builder
    must dispatch for them; otherwise the aggregator would have no builder to compute a
    generator's closure and the import would persist none.
    """
    assert PythonClosure().supports(_generator_config(name="gen", file_path="generators/widget/main.py")) is True


def test_generator_closure_is_the_entry_file_only(tmp_path: Path) -> None:
    """A generator's closure excludes its siblings exactly as a Python transform's does."""
    repo = _init_repo(tmp_path)
    _write(tmp_path, "generators/widget/main.py", "# entry\n")
    _write(tmp_path, "generators/widget/helpers.py", "# helper\n")
    _track(repo, "generators/widget/main.py", "generators/widget/helpers.py")

    result = PythonClosure().build(
        transform_config=_generator_config(name="widget", file_path="generators/widget/main.py"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("generators/widget/main.py",)
    assert result.complete is True
    assert result.unresolved == ()


def test_watching_the_containing_directory_readmits_the_siblings(tmp_path: Path) -> None:
    """Declaring the transform's own directory in `watch.files` brings every sibling back.

    This is the escape hatch for the transform-plus-helper-modules layout: auto-detection
    no longer assumes it, so the author asks for it by naming the directory.
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
    transform_config = _config(
        name="net",
        file_path="transforms/network/main.py",
        watch=InfrahubWatchConfig(files=["transforms/network/"]),
    )

    result = union_watch_files(
        result=PythonClosure().build(transform_config=transform_config, worktree_root=tmp_path),
        transform_config=transform_config,
        worktree_root=tmp_path,
        logger=logging.getLogger(__name__),
    )

    assert result.dependencies == (
        "transforms/network/helpers.py",
        "transforms/network/main.py",
        "transforms/network/sub/inner.py",
    )
    assert result.complete is True


def test_watching_a_single_sibling_admits_only_that_sibling(tmp_path: Path) -> None:
    """A `watch.files` entry naming one file adds that file and nothing else beside it.

    Declaring one helper must not drag in the rest of the directory, otherwise narrowing
    the auto-detected closure would buy nothing for anyone who uses `watch` at all.
    """
    repo = _init_repo(tmp_path)
    _write(tmp_path, "transforms/network/main.py", "# entry\n")
    _write(tmp_path, "transforms/network/helpers.py", "# helper\n")
    _write(tmp_path, "transforms/network/noise.gql", "query {}\n")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/helpers.py",
        "transforms/network/noise.gql",
    )
    transform_config = _config(
        name="net",
        file_path="transforms/network/main.py",
        watch=InfrahubWatchConfig(files=["transforms/network/helpers.py"]),
    )

    result = union_watch_files(
        result=PythonClosure().build(transform_config=transform_config, worktree_root=tmp_path),
        transform_config=transform_config,
        worktree_root=tmp_path,
        logger=logging.getLogger(__name__),
    )

    assert result.dependencies == (
        "transforms/network/helpers.py",
        "transforms/network/main.py",
    )
    assert result.complete is True


def test_watched_directory_excludes_bytecode_and_gitignored_files(tmp_path: Path) -> None:
    """Re-admitting a directory through `watch.files` still drops bytecode and ignored files.

    `.pyc`, `__pycache__/` and Git-ignored paths are not source inputs; letting them in
    would fire the regeneration gate whenever Python touches its cache.
    """
    repo = _init_repo(tmp_path, gitignore="transforms/network/secret.py\n")
    _write(tmp_path, "transforms/network/main.py", "")
    _write(tmp_path, "transforms/network/helpers.py", "")
    _write(tmp_path, "transforms/network/cached.pyc", "")
    _write(tmp_path, "transforms/network/__pycache__/main.cpython-313.pyc", "")
    _write(tmp_path, "transforms/network/secret.py", "")
    _track(
        repo,
        "transforms/network/main.py",
        "transforms/network/helpers.py",
        "transforms/network/cached.pyc",
        "transforms/network/__pycache__/main.cpython-313.pyc",
    )
    transform_config = _config(
        name="net",
        file_path="transforms/network/main.py",
        watch=InfrahubWatchConfig(files=["transforms/network/"]),
    )

    result = union_watch_files(
        result=PythonClosure().build(transform_config=transform_config, worktree_root=tmp_path),
        transform_config=transform_config,
        worktree_root=tmp_path,
        logger=logging.getLogger(__name__),
    )

    assert result.dependencies == (
        "transforms/network/helpers.py",
        "transforms/network/main.py",
    )
