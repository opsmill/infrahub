from __future__ import annotations

from typing import TYPE_CHECKING

from git import Repo

from infrahub.git.fingerprint.blob_resolver import GitBlobResolver

if TYPE_CHECKING:
    from pathlib import Path


def _commit_files(repo_dir: Path, files: dict[str, str]) -> str:
    repo = Repo.init(repo_dir, initial_branch="main")
    for relative_path, content in files.items():
        target = repo_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    repo.index.add(list(files))
    commit = repo.index.commit("initial")
    return commit.hexsha


def test_resolve_returns_sorted_path_blob_pairs(tmp_path: Path) -> None:
    commit = _commit_files(tmp_path, {"b.py": "b", "a.py": "a", "sub/c.py": "c"})
    resolver = GitBlobResolver(repo=Repo(tmp_path), commit=commit)

    pairs = resolver.resolve(["sub/c.py", "a.py", "b.py"])

    assert [path for path, _ in pairs] == ["a.py", "b.py", "sub/c.py"]
    assert all(len(blob_sha) == 40 for _, blob_sha in pairs)


def test_identical_content_resolves_to_identical_blob_sha(tmp_path: Path) -> None:
    commit = _commit_files(tmp_path, {"a.py": "same", "b.py": "same"})
    resolver = GitBlobResolver(repo=Repo(tmp_path), commit=commit)

    pairs = dict(resolver.resolve(["a.py", "b.py"]))

    assert pairs["a.py"] == pairs["b.py"]


def test_changed_content_changes_blob_sha(tmp_path: Path) -> None:
    repo = Repo.init(tmp_path, initial_branch="main")
    (tmp_path / "a.py").write_text("before", encoding="utf-8")
    repo.index.add(["a.py"])
    first = repo.index.commit("first")
    (tmp_path / "a.py").write_text("after", encoding="utf-8")
    repo.index.add(["a.py"])
    second = repo.index.commit("second")

    before = dict(GitBlobResolver(repo=repo, commit=first.hexsha).resolve(["a.py"]))
    after = dict(GitBlobResolver(repo=repo, commit=second.hexsha).resolve(["a.py"]))

    assert before["a.py"] != after["a.py"]


def test_missing_path_resolves_to_empty_sha(tmp_path: Path) -> None:
    commit = _commit_files(tmp_path, {"a.py": "a"})
    resolver = GitBlobResolver(repo=Repo(tmp_path), commit=commit)

    assert resolver.resolve(["missing.py"]) == [("missing.py", "")]
