from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.exceptions import RepositoryError
from infrahub.git.models import GitReadOnlyRepositoryCheckRefs, RepositoryBranchInfo, RepositoryData, TrackedRef
from infrahub.git.refs_check.checker import RefNameValidator
from infrahub.git.refs_check.factory import build_check_refs_model
from infrahub.git.refs_check.gateway import (
    GitRepositoryRefsGateway,
    _list_remote_head,
    _resolve_local_head,
    parse_ls_remote,
    select_remote_head,
)

if TYPE_CHECKING:
    from pathlib import Path


class RecordingCheckRefFormat:
    """Stands in for the ``git check-ref-format`` subprocess and records every name it was handed."""

    def __init__(self, *, accepts: bool = True) -> None:
        self.accepts = accepts
        self.calls: list[str] = []

    def __call__(self, ref: str) -> bool:
        self.calls.append(ref)
        return self.accepts


@dataclass
class RefValidationCase:
    name: str
    ref: str
    git_accepts: bool
    expected_valid: bool
    expected_calls: list[str] = field(default_factory=list)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            RefValidationCase(
                name="plain_branch_name_is_accepted",
                ref="main",
                git_accepts=True,
                expected_valid=True,
                expected_calls=["main"],
            ),
            id="plain_branch_name_is_accepted",
        ),
        pytest.param(
            RefValidationCase(
                name="option_like_name_is_refused_without_running_git",
                ref="--upload-pack=touch /tmp/pwned",
                git_accepts=True,
                expected_valid=False,
                expected_calls=[],
            ),
            id="option_like_name_is_refused_without_running_git",
        ),
        pytest.param(
            RefValidationCase(
                name="single_dash_name_is_refused_without_running_git",
                ref="-x",
                git_accepts=True,
                expected_valid=False,
                expected_calls=[],
            ),
            id="single_dash_name_is_refused_without_running_git",
        ),
        pytest.param(
            RefValidationCase(
                name="empty_name_is_refused_without_running_git",
                ref="",
                git_accepts=True,
                expected_valid=False,
                expected_calls=[],
            ),
            id="empty_name_is_refused_without_running_git",
        ),
        pytest.param(
            RefValidationCase(
                name="name_git_rejects_is_refused",
                ref="feature..branch",
                git_accepts=False,
                expected_valid=False,
                expected_calls=["feature..branch"],
            ),
            id="name_git_rejects_is_refused",
        ),
    ],
)
async def test_ref_name_validation(case: RefValidationCase) -> None:
    check_ref_format = RecordingCheckRefFormat(accepts=case.git_accepts)
    validator = RefNameValidator(check_ref_format=check_ref_format)

    assert await validator.is_valid(case.ref) is case.expected_valid
    assert check_ref_format.calls == case.expected_calls


LS_REMOTE_BRANCH_AND_TAG = (
    "1111111111111111111111111111111111111111\trefs/heads/release\n"
    "2222222222222222222222222222222222222222\trefs/tags/release\n"
    "3333333333333333333333333333333333333333\trefs/tags/release^{}\n"
)


def test_branch_wins_over_a_tag_of_the_same_name() -> None:
    lines = parse_ls_remote(LS_REMOTE_BRANCH_AND_TAG)

    assert select_remote_head(lines, "release") == "1111111111111111111111111111111111111111"


def test_a_tag_of_the_same_name_does_not_change_the_branch_outcome() -> None:
    without_tag = select_remote_head(
        parse_ls_remote("1111111111111111111111111111111111111111\trefs/heads/release\n"), "release"
    )

    # Pinned against the literal rather than against the other call, so that a function returning
    # nothing at all cannot satisfy both sides.
    assert without_tag == "1111111111111111111111111111111111111111"
    assert select_remote_head(parse_ls_remote(LS_REMOTE_BRANCH_AND_TAG), "release") == without_tag


def test_an_annotated_tag_is_compared_through_its_commit() -> None:
    lines = parse_ls_remote(
        "2222222222222222222222222222222222222222\trefs/tags/v1.0\n"
        "3333333333333333333333333333333333333333\trefs/tags/v1.0^{}\n"
    )

    assert select_remote_head(lines, "v1.0") == "3333333333333333333333333333333333333333"


def test_a_lightweight_tag_is_compared_through_its_own_sha() -> None:
    lines = parse_ls_remote("2222222222222222222222222222222222222222\trefs/tags/v1.0\n")

    assert select_remote_head(lines, "v1.0") == "2222222222222222222222222222222222222222"


def test_a_ref_absent_from_the_remote_has_no_head() -> None:
    lines = parse_ls_remote("1111111111111111111111111111111111111111\trefs/heads/main\n")

    assert select_remote_head(lines, "gone") is None


def test_lines_that_carry_no_ref_name_are_ignored() -> None:
    heads = parse_ls_remote("warning: redirecting to https://example.com/repo.git\n")

    assert heads == {}


def build_remote_and_clone(tmp_path: Path) -> Repo:
    """Create an origin repository carrying a branch, a lightweight tag and an annotated tag, and clone it."""
    origin = Repo.init(tmp_path / "origin")
    with origin.config_writer() as config:
        config.set_value("user", "email", "test@example.com")
        config.set_value("user", "name", "Test")
    (tmp_path / "origin" / "file.txt").write_text("content", encoding="utf-8")
    origin.index.add(["file.txt"])
    origin.index.commit("initial")
    origin.create_head("stable")
    origin.create_tag("lightweight")
    origin.create_tag("annotated", message="a tag object of its own")

    return Repo.clone_from(str(tmp_path / "origin"), str(tmp_path / "clone"))


def test_an_annotated_tag_is_listed_through_the_commit_the_local_read_resolves(tmp_path: Path) -> None:
    """The remote head of an annotated tag must be its commit, not the tag object pointing at it.

    Comparing the tag object against the commit the local read resolves would report movement on
    every check, with nothing ever able to make the two agree.
    """
    clone = build_remote_and_clone(tmp_path)

    assert _list_remote_head(clone, "annotated") == _resolve_local_head(clone, "annotated")


def test_a_lightweight_tag_is_listed_through_its_own_sha(tmp_path: Path) -> None:
    clone = build_remote_and_clone(tmp_path)

    assert _list_remote_head(clone, "lightweight") == _resolve_local_head(clone, "lightweight")


def test_a_branch_is_listed_through_its_head(tmp_path: Path) -> None:
    clone = build_remote_and_clone(tmp_path)

    assert _list_remote_head(clone, "stable") == _resolve_local_head(clone, "stable")


def test_a_ref_missing_from_the_remote_has_no_head(tmp_path: Path) -> None:
    clone = build_remote_and_clone(tmp_path)

    assert _list_remote_head(clone, "never-existed") is None


async def test_the_gateway_presents_a_git_failure_as_a_repository_error(tmp_path: Path) -> None:
    """``GitCommandError`` is one leaf of the git error tree, not its root.

    A directory that is no longer a git repository raises a sibling of it, and the check handles
    one exception type rather than every shape git can fail in.
    """
    gateway = GitRepositoryRefsGateway(client=InfrahubClient(config=Config(address="http://mock")))
    model = GitReadOnlyRepositoryCheckRefs(
        repository_id="8808dcea-f7b4-4f5a-b5e9-a0605d4c11ba",
        repository_name="never-cloned",
        location=str(tmp_path / "absent"),
        refs=(TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-id", ref="stable", commit=None),),
    )

    with pytest.raises(RepositoryError):
        await gateway.read_local_head(model, "stable")


@dataclass
class StubAttribute:
    value: str | None


@dataclass
class StubRepository:
    location: StubAttribute


def build_repository_data(
    *,
    location: str | None = "https://example.com/repo.git",
    branch_info: dict[str, RepositoryBranchInfo],
    branches: dict[str, str | None],
) -> RepositoryData:
    # model_construct: the repository field only has to answer `.location.value` here, and the
    # declared union validates against SDK node classes a unit test has no way to build.
    return RepositoryData.model_construct(
        repository_id="8808dcea-f7b4-4f5a-b5e9-a0605d4c11ba",
        repository_name="readonly-repo",
        repository=StubRepository(location=StubAttribute(value=location)),
        branches=branches,
        branch_info=branch_info,
    )


def test_every_branch_tracking_a_ref_becomes_a_tracked_ref() -> None:
    repository_data = build_repository_data(
        branch_info={
            "main": RepositoryBranchInfo(internal_status="active", ref="stable"),
            "feature": RepositoryBranchInfo(internal_status="active", ref="other"),
        },
        branches={"main": "aaa", "feature": "bbb"},
    )

    model = build_check_refs_model(
        repository_data=repository_data, branch_ids={"main": "main-id", "feature": "feature-id"}
    )

    assert model is not None
    assert [
        (tracked.infrahub_branch_name, tracked.infrahub_branch_id, tracked.ref, tracked.commit)
        for tracked in model.refs
    ] == [
        ("main", "main-id", "stable", "aaa"),
        ("feature", "feature-id", "other", "bbb"),
    ]


def test_the_global_branch_is_never_tracked() -> None:
    """The global branch holds branch-agnostic data and does not exist in any repository."""
    repository_data = build_repository_data(
        branch_info={
            "main": RepositoryBranchInfo(internal_status="active", ref="stable"),
            GLOBAL_BRANCH_NAME: RepositoryBranchInfo(internal_status="active", ref="stable"),
        },
        branches={"main": "aaa", GLOBAL_BRANCH_NAME: "aaa"},
    )

    model = build_check_refs_model(
        repository_data=repository_data, branch_ids={"main": "main-id", GLOBAL_BRANCH_NAME: "global-id"}
    )

    assert model is not None
    assert [tracked.infrahub_branch_name for tracked in model.refs] == ["main"]


def test_a_repository_whose_only_branch_is_the_global_one_is_not_checked() -> None:
    repository_data = build_repository_data(
        branch_info={GLOBAL_BRANCH_NAME: RepositoryBranchInfo(internal_status="active", ref="stable")},
        branches={GLOBAL_BRANCH_NAME: "aaa"},
    )

    model = build_check_refs_model(repository_data=repository_data, branch_ids={GLOBAL_BRANCH_NAME: "global-id"})

    assert model is None


def test_a_branch_whose_id_is_unknown_is_left_out() -> None:
    repository_data = build_repository_data(
        branch_info={
            "main": RepositoryBranchInfo(internal_status="active", ref="stable"),
            "vanished": RepositoryBranchInfo(internal_status="active", ref="stable"),
        },
        branches={"main": "aaa", "vanished": "bbb"},
    )

    model = build_check_refs_model(repository_data=repository_data, branch_ids={"main": "main-id"})

    assert model is not None
    assert [tracked.infrahub_branch_name for tracked in model.refs] == ["main"]


def test_a_branch_where_the_repository_is_not_active_is_left_out() -> None:
    """A staging branch has no completed import, so this worker has no local copy to compare."""
    repository_data = build_repository_data(
        branch_info={
            "main": RepositoryBranchInfo(internal_status="active", ref="stable"),
            "staging": RepositoryBranchInfo(internal_status="staging", ref="stable"),
        },
        branches={"main": "aaa", "staging": "bbb"},
    )

    model = build_check_refs_model(
        repository_data=repository_data, branch_ids={"main": "main-id", "staging": "staging-id"}
    )

    assert model is not None
    assert [tracked.infrahub_branch_name for tracked in model.refs] == ["main"]


def test_a_branch_tracking_no_ref_is_left_out() -> None:
    repository_data = build_repository_data(
        branch_info={
            "main": RepositoryBranchInfo(internal_status="active", ref="stable"),
            "untracked": RepositoryBranchInfo(internal_status="active", ref=None),
        },
        branches={"main": "aaa", "untracked": "bbb"},
    )

    model = build_check_refs_model(
        repository_data=repository_data, branch_ids={"main": "main-id", "untracked": "untracked-id"}
    )

    assert model is not None
    assert [tracked.infrahub_branch_name for tracked in model.refs] == ["main"]


def test_a_repository_with_no_location_is_not_checked() -> None:
    repository_data = build_repository_data(
        location=None,
        branch_info={"main": RepositoryBranchInfo(internal_status="active", ref="stable")},
        branches={"main": "aaa"},
    )

    model = build_check_refs_model(repository_data=repository_data, branch_ids={"main": "main-id"})

    assert model is None
