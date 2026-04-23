import pytest

from infrahub.marketplace.cli_snippet import parse_install_item, render_cli_snippet
from infrahub.marketplace.models import MarketplaceInstallItem


def test_parse_install_item_schema_with_version() -> None:
    item = parse_install_item("schema:infrahub/vlan-translation@1.0.0")
    assert item.kind == "schema"
    assert item.namespace == "infrahub"
    assert item.name == "vlan-translation"
    assert item.semver == "1.0.0"


def test_parse_install_item_schema_latest() -> None:
    item = parse_install_item("schema:infrahub/base-schema")
    assert item.semver is None


def test_parse_install_item_collection_ignores_semver() -> None:
    # Even if a caller passes @version on a collection, semver is not retained.
    item = parse_install_item("collection:infrahub/base-schemas")
    assert item.kind == "collection"
    assert item.semver is None


def test_parse_install_item_rejects_bad_kind() -> None:
    with pytest.raises(ValueError):
        parse_install_item("unknown:infrahub/foo")


def test_parse_install_item_rejects_missing_namespace() -> None:
    with pytest.raises(ValueError):
        parse_install_item("schema:foo")


def test_render_cli_snippet_single_schema() -> None:
    items = [
        MarketplaceInstallItem(
            kind="schema", namespace="infrahub", name="vlan-translation", semver="1.0.0"
        )
    ]
    snippet = render_cli_snippet(items=items, branch_name="main")
    assert snippet.downloads[0].command == (
        "infrahubctl marketplace download infrahub/vlan-translation -v 1.0.0"
    )
    assert snippet.load_command == "infrahubctl schema load ./schemas --branch main"
    assert "infrahubctl marketplace download" in snippet.rendered
    assert snippet.rendered.endswith("--branch main")


def test_render_cli_snippet_collection_uses_c_flag() -> None:
    items = [
        MarketplaceInstallItem(
            kind="collection", namespace="infrahub", name="base-schemas", semver=None
        )
    ]
    snippet = render_cli_snippet(items=items, branch_name="main")
    assert snippet.downloads[0].command == (
        "infrahubctl marketplace download -c infrahub/base-schemas"
    )


def test_render_cli_snippet_custom_output_dir() -> None:
    items = [
        MarketplaceInstallItem(kind="schema", namespace="foo", name="bar", semver="2.1.0"),
    ]
    snippet = render_cli_snippet(items=items, branch_name="dev", output_dir="./vendor/schemas")
    assert "-o ./vendor/schemas" in snippet.downloads[0].command
    assert snippet.load_command == "infrahubctl schema load ./vendor/schemas --branch dev"


def test_render_cli_snippet_injects_marketplace_url_when_overridden() -> None:
    items = [
        MarketplaceInstallItem(kind="schema", namespace="foo", name="bar", semver=None),
    ]
    snippet = render_cli_snippet(
        items=items,
        branch_name="main",
        marketplace_url="https://marketplace-staging.example.com",
    )
    assert "--marketplace-url https://marketplace-staging.example.com" in snippet.downloads[0].command


def test_render_cli_snippet_no_url_flag_when_default() -> None:
    items = [
        MarketplaceInstallItem(kind="schema", namespace="foo", name="bar", semver=None),
    ]
    snippet = render_cli_snippet(
        items=items,
        branch_name="main",
        marketplace_url="https://marketplace.infrahub.app",
    )
    assert "--marketplace-url" not in snippet.downloads[0].command


def test_render_cli_snippet_rejects_empty() -> None:
    with pytest.raises(ValueError):
        render_cli_snippet(items=[], branch_name="main")


def test_render_cli_snippet_rejects_too_many() -> None:
    items = [
        MarketplaceInstallItem(kind="schema", namespace="n", name=f"s{i}", semver=None)
        for i in range(51)
    ]
    with pytest.raises(ValueError):
        render_cli_snippet(items=items, branch_name="main")
