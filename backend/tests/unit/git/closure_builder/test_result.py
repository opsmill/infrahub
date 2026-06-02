from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.closure_builder.result import ClosureResult, UnresolvedRef


@dataclass(frozen=True, kw_only=True)
class ValidCase:
    name: str
    dependencies: tuple[str, ...]


VALID_CASES: list[ValidCase] = [
    ValidCase(name="empty_is_valid", dependencies=()),
    ValidCase(name="single_canonical", dependencies=("templates/device.j2",)),
    ValidCase(
        name="multiple_sorted_canonical",
        dependencies=(".infrahub.yml", "templates/device.j2", "templates/partials/header.j2"),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in VALID_CASES])
def test_closure_result_accepts_canonical_sorted_paths(case: ValidCase) -> None:
    """A `ClosureResult` constructed from canonical, sorted paths is accepted.

    The invariants serve the regeneration gate: byte-stable storage prevents
    spurious node modifications across re-imports, and the canonical form ensures
    the read-side intersection compares values shaped identically to git diff output.
    """
    result = ClosureResult(dependencies=case.dependencies, complete=True, unresolved=())
    assert result.dependencies == case.dependencies


@dataclass(frozen=True, kw_only=True)
class InvalidCase:
    name: str
    dependencies: tuple[str, ...]
    error_match: str


INVALID_CASES: list[InvalidCase] = [
    InvalidCase(
        name="non_canonical_leading_dot_slash",
        dependencies=("./templates/device.j2",),
        error_match=r"not in canonical form",
    ),
    InvalidCase(
        name="non_canonical_trailing_slash",
        dependencies=("templates/",),
        error_match=r"not in canonical form",
    ),
    InvalidCase(
        name="non_canonical_backslash",
        dependencies=("templates\\device.j2",),
        error_match=r"not in canonical form",
    ),
    InvalidCase(
        name="unsorted_pair",
        dependencies=("templates/device.j2", ".infrahub.yml"),
        error_match=r"sorted lexicographically",
    ),
    InvalidCase(
        name="duplicate_entry",
        dependencies=("templates/device.j2", "templates/device.j2"),
        error_match=r"duplicate dependency entry",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in INVALID_CASES])
def test_closure_result_rejects_non_canonical_or_unsorted(case: InvalidCase) -> None:
    """Non-canonical, unsorted, or duplicate entries are rejected at construction.

    Catching the violation at the closure-result boundary prevents non-canonical
    forms from reaching the persistence layer, where they would silently break the
    set intersection performed by the regeneration gate.
    """
    with pytest.raises(ValueError, match=case.error_match):
        ClosureResult(dependencies=case.dependencies, complete=True, unresolved=())


def test_closure_result_accepts_unresolved_refs() -> None:
    """Unresolved references are preserved verbatim on the result for diagnostic logging."""
    refs = (UnresolvedRef(file="templates/device.j2", location="line 42"),)
    result = ClosureResult(dependencies=(), complete=False, unresolved=refs)
    assert result.unresolved == refs
