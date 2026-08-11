import pytest
from infrahub_sdk.client import Config as InfrahubClientConfig

from infrahub.pytest_plugin import InfrahubBackendPlugin


class OrderingItem(pytest.Item):
    def runtest(self) -> None:
        raise NotImplementedError


def build_item(session: pytest.Session, name: str, markers: list[str]) -> pytest.Item:
    item = OrderingItem.from_parent(session, name=name)
    for marker in markers:
        item.add_marker(getattr(pytest.mark, marker))
    return item


@pytest.fixture
def plugin() -> InfrahubBackendPlugin:
    return InfrahubBackendPlugin(
        config=InfrahubClientConfig(address="http://localhost:8000", api_token="token"),
        repository_id="11111111-1111-1111-1111-111111111111",
        proposed_change_id="22222222-2222-2222-2222-222222222222",
    )


def test_items_are_ordered_by_type_then_by_resource(
    request: pytest.FixtureRequest, plugin: InfrahubBackendPlugin
) -> None:
    items = [
        build_item(request.session, name, ["infrahub", *markers])
        for name, markers in (
            ("integration_check", ["infrahub_integration", "infrahub_check"]),
            ("unit_python_transform", ["infrahub_unit", "infrahub_python_transform"]),
            ("smoke_python_transform", ["infrahub_smoke", "infrahub_python_transform"]),
            ("smoke_check", ["infrahub_smoke", "infrahub_check"]),
        )
    ]

    plugin.pytest_collection_modifyitems(session=request.session, config=request.config, items=items)

    assert [item.name for item in items] == [
        "smoke_check",
        "smoke_python_transform",
        "unit_python_transform",
        "integration_check",
    ]


def test_items_without_the_infrahub_marker_are_discarded(
    request: pytest.FixtureRequest, plugin: InfrahubBackendPlugin
) -> None:
    items = [
        build_item(request.session, "unrelated", []),
        build_item(request.session, "smoke_check", ["infrahub", "infrahub_smoke", "infrahub_check"]),
    ]

    plugin.pytest_collection_modifyitems(session=request.session, config=request.config, items=items)

    assert [item.name for item in items] == ["smoke_check"]


def test_items_without_a_known_marker_are_ordered_last(
    request: pytest.FixtureRequest, plugin: InfrahubBackendPlugin
) -> None:
    items = [
        build_item(request.session, "unknown", ["infrahub"]),
        build_item(request.session, "integration_check", ["infrahub", "infrahub_integration", "infrahub_check"]),
    ]

    plugin.pytest_collection_modifyitems(session=request.session, config=request.config, items=items)

    assert [item.name for item in items] == ["integration_check", "unknown"]
