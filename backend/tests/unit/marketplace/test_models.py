import pytest
from pydantic import ValidationError

from infrahub.marketplace.models import (
    MarketplaceInstallItem,
    MarketplaceInstallRequest,
)


def test_install_item_accepts_valid_semver() -> None:
    item = MarketplaceInstallItem(kind="schema", namespace="infrahub", name="vlan-translation", semver="1.0.0")
    assert item.semver == "1.0.0"


def test_install_item_semver_can_be_null() -> None:
    item = MarketplaceInstallItem(kind="schema", namespace="infrahub", name="vlan-translation", semver=None)
    assert item.semver is None


def test_install_item_rejects_bad_semver() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallItem(kind="schema", namespace="infrahub", name="vlan-translation", semver="not-a-semver")


def test_install_request_requires_non_empty_items() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallRequest(repository_id="repo-1", branch_name="main", items=[])


def test_install_request_rejects_too_many_items() -> None:
    items = [MarketplaceInstallItem(kind="schema", namespace="ns", name=f"s{i}", semver=None) for i in range(51)]
    with pytest.raises(ValidationError):
        MarketplaceInstallRequest(repository_id="repo-1", branch_name="main", items=items)


def test_install_request_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallItem(
            kind="bogus",  # type: ignore[arg-type]
            namespace="infrahub",
            name="vlan-translation",
        )


def test_install_request_default_target_is_repository() -> None:
    req = MarketplaceInstallRequest(
        repository_id="repo-1",
        branch_name="main",
        items=[MarketplaceInstallItem(kind="schema", namespace="ns", name="s")],
    )
    assert req.target == "repository"


def test_install_request_direct_target_allows_null_repository_id() -> None:
    req = MarketplaceInstallRequest(
        target="direct",
        branch_name="main",
        items=[MarketplaceInstallItem(kind="schema", namespace="ns", name="s")],
    )
    assert req.target == "direct"
    assert req.repository_id is None


def test_install_request_repository_target_requires_repository_id() -> None:
    with pytest.raises(ValidationError, match="repository_id is required"):
        MarketplaceInstallRequest(
            target="repository",
            branch_name="main",
            items=[MarketplaceInstallItem(kind="schema", namespace="ns", name="s")],
        )


def test_install_request_repository_target_rejects_empty_repository_id() -> None:
    # Empty / whitespace strings are normalized to None and then rejected by the
    # cross-field validator.
    with pytest.raises(ValidationError, match="repository_id is required"):
        MarketplaceInstallRequest(
            target="repository",
            repository_id="   ",
            branch_name="main",
            items=[MarketplaceInstallItem(kind="schema", namespace="ns", name="s")],
        )


@pytest.mark.parametrize(
    "bad_branch",
    [
        "-flag",  # leading hyphen — parseable as git CLI flag
        "..",  # path traversal
        "path/../other",  # embedded path traversal
        "",  # empty
        "has space",  # whitespace
        "has\ttab",  # control char
        "--upload-pack=/evil",  # flag injection attempt
        "/absolute",  # leading slash reserved
    ],
)
def test_install_request_rejects_unsafe_branch_name(bad_branch: str) -> None:
    item = MarketplaceInstallItem(kind="schema", namespace="ns", name="foo", semver=None)
    with pytest.raises(ValidationError):
        MarketplaceInstallRequest(target="direct", branch_name=bad_branch, items=[item])


@pytest.mark.parametrize("good_branch", ["main", "develop", "feature/foo", "release-1.2", "v1.0.0", "a"])
def test_install_request_accepts_normal_branch_names(good_branch: str) -> None:
    item = MarketplaceInstallItem(kind="schema", namespace="ns", name="foo", semver=None)
    req = MarketplaceInstallRequest(target="direct", branch_name=good_branch, items=[item])
    assert req.branch_name == good_branch
