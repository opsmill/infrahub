from collections.abc import Callable

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget


@pytest.fixture
def make_attr() -> Callable[[str], AttributeSchema]:
    def _make_attr(name: str) -> AttributeSchema:
        return AttributeSchema(name=name, kind="Text")

    return _make_attr


@pytest.fixture
def make_rel() -> Callable[[str, str], RelationshipSchema]:
    def _make_rel(name: str, peer: str) -> RelationshipSchema:
        return RelationshipSchema(
            name=name, peer=peer, cardinality=RelationshipCardinality.ONE, kind=RelationshipKind.ATTRIBUTE
        )

    return _make_rel


@pytest.fixture
def make_target(make_attr: Callable[[str], AttributeSchema]) -> Callable[..., ComputedAttributeTarget]:
    def _make_target(kind: str, attr_name: str, filter_keys: list[str] | None = None) -> ComputedAttributeTarget:
        return ComputedAttributeTarget(kind=kind, attribute=make_attr(attr_name), filter_keys=filter_keys or [])

    return _make_target


@pytest.fixture
def make_node() -> Callable[..., NodeSchema]:
    def _make_node(name: str, namespace: str = "Infra") -> NodeSchema:
        return NodeSchema(name=name, namespace=namespace)

    return _make_node
