from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.exceptions import RepositoryError
from tests.unit.git.divergence.conftest import (
    ABSENT,
    break_object_database,
    commit_file,
    deny_access_to_packs,
    pack_directory_of,
    pack_loose_objects,
    pack_objects,
)

if TYPE_CHECKING:
    from infrahub.git.divergence.gateway import GitAncestryGateway


def test_an_earlier_commit_is_an_ancestor_of_a_later_one(repo: Repo, gateway: GitAncestryGateway) -> None:
    first = commit_file(repo=repo, content="one")
    second = commit_file(repo=repo, content="two")

    assert gateway.is_ancestor(ancestor_commit=first, descendant_commit=second) is True
    assert gateway.is_ancestor(ancestor_commit=second, descendant_commit=first) is False


def test_an_unreachable_commit_leaves_as_a_repository_error(repo: Repo, gateway: GitAncestryGateway) -> None:
    present = commit_file(repo=repo, content="one")

    with pytest.raises(RepositoryError, match=r"^Unable to compare 0{40} against [0-9a-f]{40}: "):
        gateway.is_ancestor(ancestor_commit=ABSENT, descendant_commit=present)


def test_a_broken_repository_fails_the_comparison(repo: Repo, gateway: GitAncestryGateway) -> None:
    commit = commit_file(repo=repo, content="one")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"^Unable to compare [0-9a-f]{40} against [0-9a-f]{40}: "):
        gateway.is_ancestor(ancestor_commit=commit, descendant_commit=commit)


def test_the_error_message_is_one_line(repo: Repo, gateway: GitAncestryGateway) -> None:
    """GitPython wraps what git wrote in a newline and a quoted prefix."""
    present = commit_file(repo=repo, content="one")

    with pytest.raises(RepositoryError) as caught:
        gateway.is_ancestor(ancestor_commit=ABSENT, descendant_commit=present)

    assert "\n" not in str(caught.value)
    assert "stderr:" not in str(caught.value)
    assert str(caught.value).endswith("Not a valid commit name " + ABSENT)


def test_a_commit_in_the_object_database_is_present(repo: Repo, gateway: GitAncestryGateway) -> None:
    assert gateway.has_commit(commit=commit_file(repo=repo, content="one")) is True


def test_a_packed_commit_is_still_present(repo: Repo, gateway: GitAncestryGateway) -> None:
    """Packing moves the object out of its loose file, and it must still read as present."""
    commit = commit_file(repo=repo, content="one")
    commit_file(repo=repo, content="two")
    repo.git.gc("--prune=now")

    assert gateway.has_commit(commit=commit) is True


def test_a_pruned_commit_reads_as_absent_rather_than_raising(repo: Repo, gateway: GitAncestryGateway) -> None:
    """Without this the branch raises every cycle and never classifies at all."""
    keep = commit_file(repo=repo, content="one")
    pruned = commit_file(repo=repo, content="two")
    repo.git.reset("--hard", keep)
    repo.git.reflog("expire", "--expire=now", "--all")
    repo.git.prune()

    assert gateway.has_commit(commit=pruned) is False


def test_a_name_that_is_not_a_commit_holds_no_commit(repo: Repo, gateway: GitAncestryGateway) -> None:
    """An annotated tag carries a commit, and its own object must still not read as one."""
    commit_file(repo=repo, content="one")
    tree = str(repo.head.commit.tree.hexsha)
    blob = str(repo.head.commit.tree["file.txt"].hexsha)
    annotated = repo.create_tag("v1", message="annotated").tag
    assert annotated is not None

    assert gateway.has_commit(commit=tree) is False
    assert gateway.has_commit(commit=blob) is False
    assert gateway.has_commit(commit=str(annotated.hexsha)) is False


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod does not restrict root")
def test_an_unreadable_pack_is_an_error_not_an_absence(repo: Repo, gateway: GitAncestryGateway) -> None:
    """Git returns the absent status for a commit it holds but cannot read."""
    commit = commit_file(repo=repo, content="one")
    commit_file(repo=repo, content="two")
    pack_objects(repo=repo)
    packs = deny_access_to_packs(repo=repo)

    try:
        with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
            gateway.has_commit(commit=commit)
    finally:
        for pack in packs:
            pack.chmod(0o644)


PARTIALLY_DENIED_PACK_TEST_CASES = [
    pytest.param((".idx", ".pack"), id="the_index_and_the_pack"),
    pytest.param((".pack",), id="only_the_pack"),
]


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod does not restrict root")
@pytest.mark.parametrize("denied_suffixes", PARTIALLY_DENIED_PACK_TEST_CASES)
def test_one_unreadable_pack_among_several_is_an_error_not_an_absence(
    repo: Repo, gateway: GitAncestryGateway, denied_suffixes: tuple[str, ...]
) -> None:
    """Git skips the pack it cannot read and answers the absent status from the packs it can."""
    commit = commit_file(repo=repo, content="one")
    first_pack = pack_loose_objects(repo=repo)
    commit_file(repo=repo, content="two")
    pack_loose_objects(repo=repo)
    denied = [path for path in first_pack if path.suffix in denied_suffixes]

    for path in denied:
        path.chmod(0o000)
    try:
        assert gateway.has_commit(commit=str(repo.head.commit.hexsha)) is True
        with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
            gateway.has_commit(commit=commit)
    finally:
        for path in denied:
            path.chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod does not restrict root")
def test_an_unlistable_pack_directory_is_an_error_not_an_absence(repo: Repo, gateway: GitAncestryGateway) -> None:
    """Git drops every pack when it cannot list them, and still answers from the loose objects."""
    commit = commit_file(repo=repo, content="one")
    pack_loose_objects(repo=repo)
    commit_file(repo=repo, content="two")
    pack_directory = pack_directory_of(repo=repo)

    pack_directory.chmod(0o000)
    try:
        assert gateway.has_commit(commit=str(repo.head.commit.hexsha)) is True
        with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
            gateway.has_commit(commit=commit)
    finally:
        pack_directory.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod does not restrict root")
def test_an_unreadable_borrowed_object_database_is_an_error_not_an_absence(
    tmp_path: Path, repo: Repo, gateway: GitAncestryGateway
) -> None:
    """A repository reads the objects of the one it borrows from, and must read its failures too."""
    lender = Repo.init(tmp_path / "lender")
    borrowed = commit_file(repo=lender, content="one")
    denied = pack_loose_objects(repo=lender)
    commit_file(repo=repo, content="two")
    alternates = Path(str(repo.git_dir), "objects", "info", "alternates")
    alternates.write_text(f"{pack_directory_of(repo=lender).parent}\n", encoding="utf-8")
    assert gateway.has_commit(commit=borrowed) is True

    for path in denied:
        path.chmod(0o000)
    try:
        with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
            gateway.has_commit(commit=borrowed)
    finally:
        for path in denied:
            path.chmod(0o644)


def test_an_undecodable_alternates_file_leaves_as_a_repository_error(repo: Repo, gateway: GitAncestryGateway) -> None:
    """An alternates file holds filesystem paths, and a path is not always valid text."""
    commit_file(repo=repo, content="one")
    alternates = Path(str(repo.git_dir), "objects", "info", "alternates")
    alternates.write_bytes(b"/not-there/\xff\xfe\n")

    with pytest.raises(RepositoryError, match=r"^Unable to read 0{40} from the object database: "):
        gateway.has_commit(commit=ABSENT)


def test_a_broken_object_database_is_an_error_not_an_absence(repo: Repo, gateway: GitAncestryGateway) -> None:
    """A reader that cannot answer must not be read as a pruned commit."""
    commit = commit_file(repo=repo, content="one")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
        gateway.has_commit(commit=commit)


@dataclass
class MalformedIdentifierTestCase:
    name: str
    identifier: str


MALFORMED_IDENTIFIER_TEST_CASES: list[MalformedIdentifierTestCase] = [
    MalformedIdentifierTestCase(name="not_hexadecimal", identifier="not-a-sha"),
    MalformedIdentifierTestCase(name="far_too_short", identifier="abcd"),
    MalformedIdentifierTestCase(name="one_character_short", identifier="0" * 39),
    MalformedIdentifierTestCase(name="one_character_long", identifier="0" * 41),
    MalformedIdentifierTestCase(name="uppercase", identifier="A" * 40),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MALFORMED_IDENTIFIER_TEST_CASES])
def test_a_malformed_commit_identifier_is_an_error_not_an_absence(
    gateway: GitAncestryGateway, test_case: MalformedIdentifierTestCase
) -> None:
    expected = re.escape(f"{test_case.identifier!r} is not a valid commit identifier")

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.has_commit(commit=test_case.identifier)


COMPARISON_IDENTIFIER_TEST_CASES: list[MalformedIdentifierTestCase] = [
    MalformedIdentifierTestCase(name="not_hexadecimal", identifier="not-a-sha"),
    MalformedIdentifierTestCase(name="uppercase", identifier="A" * 40),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in COMPARISON_IDENTIFIER_TEST_CASES])
def test_the_comparison_rejects_a_malformed_identifier(
    gateway: GitAncestryGateway, test_case: MalformedIdentifierTestCase
) -> None:
    expected = re.escape(f"{test_case.identifier!r} is not a valid commit identifier")

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.is_ancestor(ancestor_commit=test_case.identifier, descendant_commit=ABSENT)

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.is_ancestor(ancestor_commit=ABSENT, descendant_commit=test_case.identifier)
