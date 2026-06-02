from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.git.closure_builder.canonicalizer import canonicalize_path

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class CanonicalizeCase:
    name: str
    raw: str
    expected: str


CANONICALIZE_CASES: list[CanonicalizeCase] = [
    CanonicalizeCase(name="plain_file", raw="utils.py", expected="utils.py"),
    CanonicalizeCase(name="nested_file", raw="src/utils.py", expected="src/utils.py"),
    CanonicalizeCase(name="leading_dot_slash", raw="./utils", expected="utils"),
    CanonicalizeCase(name="repeated_leading_dot_slash", raw="././utils", expected="utils"),
    CanonicalizeCase(name="trailing_slash", raw="utils/", expected="utils"),
    CanonicalizeCase(name="leading_dot_and_trailing_slash", raw="./templates/partials/", expected="templates/partials"),
    CanonicalizeCase(name="windows_backslash", raw="src\\utils.py", expected="src/utils.py"),
    CanonicalizeCase(name="mixed_separators", raw="src\\sub/utils.py", expected="src/sub/utils.py"),
    CanonicalizeCase(name="case_preserved", raw="Templates/Header.j2", expected="Templates/Header.j2"),
    CanonicalizeCase(name="dot_file_at_root", raw=".infrahub.yml", expected=".infrahub.yml"),
    CanonicalizeCase(name="deeply_nested", raw="./a/b/c/d/", expected="a/b/c/d"),
    CanonicalizeCase(name="leading_slash_is_repo_root", raw="/templates/foo.j2", expected="templates/foo.j2"),
    CanonicalizeCase(name="windows_absolute_is_repo_root", raw="\\templates\\foo.j2", expected="templates/foo.j2"),
    CanonicalizeCase(name="dot_slash_then_slash", raw=".//file", expected="file"),
    CanonicalizeCase(name="slash_then_dot_slash", raw="/./file", expected="file"),
    CanonicalizeCase(name="interleaved_prefixes", raw="/.//./templates/", expected="templates"),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in CANONICALIZE_CASES])
def test_canonicalize_produces_expected(case: CanonicalizeCase) -> None:
    """The canonical form follows the documented contract for the inputs that enter a transform's dependency closure."""
    assert canonicalize_path(case.raw) == case.expected


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in CANONICALIZE_CASES])
def test_canonicalize_is_idempotent(case: CanonicalizeCase) -> None:
    """Applying canonicalization twice yields the same result as applying it once.

    Idempotency is required because the same helper runs at write time (closure builder
    storing dependencies) and at read time (pipeline predicate canonicalizing diff paths
    before set intersection). Without idempotency a re-read could produce a different
    value than what was stored.
    """
    once = canonicalize_path(case.raw)
    twice = canonicalize_path(once)
    assert once == twice == case.expected


def test_canonicalize_does_not_resolve_symlinks(tmp_path: Path) -> None:
    """The canonical form preserves the path as git sees it; symlink targets are not substituted.

    Resolving symlinks would diverge from git diff output (which reports the link path,
    not the target), making the set intersection at pipeline time unreliable.
    """
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    link_dir = tmp_path / "link"
    link_dir.symlink_to(target_dir)

    assert canonicalize_path("link/file.j2") == "link/file.j2"


def test_canonicalize_rejects_empty_path() -> None:
    """An empty string has no meaningful canonical form and would silently match every diff if accepted."""
    with pytest.raises(ValueError, match=r"empty"):
        canonicalize_path("")


def test_canonicalize_rejects_paths_collapsing_to_repo_root() -> None:
    """Inputs that strip down to the repository root (``.``, ``./``, ``/``) do not name a dependency.

    They are rejected so stored closures stay meaningful — an empty canonical form would
    silently match every entry in a per-repo diff.
    """
    with pytest.raises(ValueError, match=r"repository root"):
        canonicalize_path("./")
    with pytest.raises(ValueError, match=r"repository root"):
        canonicalize_path(".")
    with pytest.raises(ValueError, match=r"repository root"):
        canonicalize_path("/")
