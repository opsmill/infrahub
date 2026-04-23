import pytest
from pydantic import ValidationError

from infrahub.marketplace.models import (
    MarketplaceInstallItem,
    MarketplaceInstallRequest,
)


def test_install_item_accepts_valid_semver() -> None:
    item = MarketplaceInstallItem(
        kind="schema", namespace="infrahub", name="vlan-translation", semver="1.0.0"
    )
    assert item.semver == "1.0.0"


def test_install_item_semver_can_be_null() -> None:
    item = MarketplaceInstallItem(
        kind="schema", namespace="infrahub", name="vlan-translation", semver=None
    )
    assert item.semver is None


def test_install_item_rejects_bad_semver() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallItem(
            kind="schema", namespace="infrahub", name="vlan-translation", semver="not-a-semver"
        )


def test_install_request_requires_non_empty_items() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallRequest(repository_id="repo-1", branch_name="main", items=[])


def test_install_request_rejects_too_many_items() -> None:
    items = [
        MarketplaceInstallItem(kind="schema", namespace="ns", name=f"s{i}", semver=None)
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        MarketplaceInstallRequest(repository_id="repo-1", branch_name="main", items=items)


def test_install_request_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        MarketplaceInstallItem(
            kind="bogus",  # type: ignore[arg-type]
            namespace="infrahub",
            name="vlan-translation",
        )
