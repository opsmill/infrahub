from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.internal import base_node_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.schema.lag_interface import LAG_SCHEMA

GENERIC_KIND = "InfraLagInterface"
L2_KIND = "InfraLagInterfaceL2"
L2_INDEX = 0


def exact_message(message: str) -> str:
    return f"^{re.escape(message)}$"


def _processed_branch(schema: dict[str, Any]) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="main")
    schema_branch.load_schema(schema=SchemaRoot(**schema))
    schema_branch.process()
    return schema_branch


def _lag_schema_with_generic_containers(containers: list[dict[str, Any]]) -> dict[str, Any]:
    schema = copy.deepcopy(LAG_SCHEMA)
    schema["generics"][0]["containers"].extend(containers)
    return schema


def _lag_schema_with_l2_field(field_list: str, field: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(LAG_SCHEMA)
    schema["nodes"][L2_INDEX][field_list] = [field]
    return schema


def _lag_schema_with_l2_containers(containers: list[dict[str, Any]]) -> dict[str, Any]:
    schema = copy.deepcopy(LAG_SCHEMA)
    schema["nodes"][L2_INDEX]["containers"] = containers
    return schema


def _lag_schema_with_unweighted_container(container: dict[str, Any]) -> dict[str, Any]:
    schema = _lag_schema_with_generic_containers([container])
    for attribute in schema["generics"][0]["attributes"]:
        if attribute["name"] == "lacp_mode":
            attribute["container"] = container["name"]
    return schema


@dataclass(frozen=True)
class RefusedContainerCase:
    name: str
    schema: dict[str, Any]
    message: str


@dataclass(frozen=True)
class AcceptedContainerCase:
    name: str
    schema: dict[str, Any]
    kind: str
    container_names: list[str]
    """Names of the containers the kind carries after processing, in order."""


REFUSED_CONTAINER_CASES = [
    RefusedContainerCase(
        name="attribute_referencing_an_undeclared_container",
        schema=_lag_schema_with_l2_field(
            field_list="attributes",
            field={"name": "mtu", "kind": "Number", "optional": True, "container": "layer4"},
        ),
        message=f"{L2_KIND}.attributes.mtu.container: container 'layer4' is not declared on {L2_KIND}",
    ),
    RefusedContainerCase(
        name="relationship_referencing_an_undeclared_container",
        schema=_lag_schema_with_l2_field(
            field_list="relationships",
            field={
                "name": "sub_interfaces",
                "peer": GENERIC_KIND,
                "cardinality": "many",
                "optional": True,
                "container": "layer4",
            },
        ),
        message=f"{L2_KIND}.relationships.sub_interfaces.container: container 'layer4' is not declared on {L2_KIND}",
    ),
    RefusedContainerCase(
        name="duplicate_container_names",
        schema=_lag_schema_with_generic_containers([{"name": "lacp", "label": "Link aggregation"}]),
        message=f"{GENERIC_KIND}.containers: container names must be unique, duplicate 'lacp'",
    ),
    RefusedContainerCase(
        name="duplicate_container_names_on_a_node_with_a_generic",
        schema=_lag_schema_with_l2_containers(
            [{"name": "extra", "label": "Extra"}, {"name": "extra", "label": "Extra again"}]
        ),
        message=f"{L2_KIND}.containers: container names must be unique, duplicate 'extra'",
    ),
    RefusedContainerCase(
        name="declaring_the_advanced_container",
        schema=_lag_schema_with_generic_containers([{"name": "advanced", "label": "Advanced"}]),
        message=f"{GENERIC_KIND}.containers: 'advanced' is a built-in container and cannot be declared",
    ),
    RefusedContainerCase(
        name="declaring_the_details_container",
        schema=_lag_schema_with_generic_containers([{"name": "details", "label": "General"}]),
        message=f"{GENERIC_KIND}.containers: 'details' is a built-in container and cannot be declared",
    ),
    RefusedContainerCase(
        name="attribute_referencing_the_details_container",
        schema=_lag_schema_with_l2_field(
            field_list="attributes",
            field={"name": "mtu", "kind": "Number", "optional": True, "container": "details"},
        ),
        message=f"{L2_KIND}.attributes.mtu.container: container 'details' is not declared on {L2_KIND}",
    ),
]

ACCEPTED_CONTAINER_CASES = [
    AcceptedContainerCase(
        name="container_named_like_an_attribute",
        schema=_lag_schema_with_generic_containers([{"name": "mtu", "label": "MTU", "order_weight": 400}]),
        kind=GENERIC_KIND,
        container_names=["lacp", "layer2", "layer3", "mtu"],
    ),
    AcceptedContainerCase(
        name="declared_container_with_no_field",
        schema=_lag_schema_with_generic_containers([{"name": "spare", "label": "Spare", "order_weight": 400}]),
        kind=L2_KIND,
        container_names=["lacp", "layer2", "layer3", "spare"],
    ),
    AcceptedContainerCase(
        name="container_without_order_weight",
        schema=_lag_schema_with_unweighted_container({"name": "monitoring", "label": "Monitoring"}),
        kind=GENERIC_KIND,
        container_names=["lacp", "layer2", "layer3", "monitoring"],
    ),
]


@pytest.mark.parametrize("case", REFUSED_CONTAINER_CASES, ids=lambda case: case.name)
def test_container_declaration_is_refused(case: RefusedContainerCase) -> None:
    with pytest.raises(ValueError, match=exact_message(case.message)):
        _processed_branch(schema=case.schema)


@pytest.mark.parametrize("case", ACCEPTED_CONTAINER_CASES, ids=lambda case: case.name)
def test_container_declaration_is_accepted(case: AcceptedContainerCase) -> None:
    schema_branch = _processed_branch(schema=case.schema)

    node = schema_branch.get(name=case.kind, duplicate=False)
    assert [container.name for container in node.containers] == case.container_names


def test_advanced_reference_without_a_declaration_is_accepted() -> None:
    schema_branch = _processed_branch(schema=copy.deepcopy(LAG_SCHEMA))

    node = schema_branch.get(name=L2_KIND, duplicate=False)
    assert node.get_relationship(name="sub_interfaces").container == "advanced"
    assert [container.name for container in node.containers] == ["lacp", "layer2", "layer3"]


def test_reference_resolved_through_an_inherited_container_is_accepted() -> None:
    schema_branch = _processed_branch(schema=copy.deepcopy(LAG_SCHEMA))

    node = schema_branch.get(name=L2_KIND, duplicate=False)
    layer2 = next(container for container in node.containers if container.name == "layer2")
    assert layer2.inherited is True
    assert node.get_attribute(name="l2_mode").container == "layer2"


def test_removing_a_container_from_the_generic_refuses_the_inherited_field_on_the_next_load() -> None:
    schema_branch = _processed_branch(schema=copy.deepcopy(LAG_SCHEMA))
    generic = copy.deepcopy(LAG_SCHEMA["generics"][0])
    generic["containers"] = [{"name": "layer2", "label": "Layer 2", "state": HashableModelState.ABSENT.value}]
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", generics=[generic]))

    with pytest.raises(
        ValueError,
        match=exact_message(f"{L2_KIND}.attributes.l2_mode.container: container 'layer2' is not declared on {L2_KIND}"),
    ):
        schema_branch.process()


def _reload_generic(schema_branch: SchemaBranch, generic: dict[str, Any]) -> None:
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", generics=[generic]))
    schema_branch.process()


def _generic_without_field_container(field_list: str, field_name: str) -> dict[str, Any]:
    generic = copy.deepcopy(LAG_SCHEMA["generics"][0])
    field = next(field for field in generic[field_list] if field["name"] == field_name)
    del field["container"]
    return generic


@pytest.mark.parametrize(
    ("field_list", "field_name"), [("attributes", "lacp_rate"), ("relationships", "sub_interfaces")]
)
def test_reload_without_container_moves_a_field_back_to_details(field_list: str, field_name: str) -> None:
    schema_branch = _processed_branch(schema=copy.deepcopy(LAG_SCHEMA))

    _reload_generic(schema_branch, _generic_without_field_container(field_list=field_list, field_name=field_name))

    for kind in (GENERIC_KIND, L2_KIND):
        node = schema_branch.get(name=kind, duplicate=False)
        assert next(field for field in getattr(node, field_list) if field.name == field_name).container is None


def test_reload_removing_a_container_and_its_references_together_is_accepted() -> None:
    schema_branch = _processed_branch(schema=copy.deepcopy(LAG_SCHEMA))
    generic = copy.deepcopy(LAG_SCHEMA["generics"][0])
    generic["containers"] = [{"name": "lacp", "label": "LACP", "state": HashableModelState.ABSENT.value}]
    for attribute in generic["attributes"]:
        if attribute.get("container") == "lacp":
            del attribute["container"]

    _reload_generic(schema_branch, generic)

    node = schema_branch.get(name=L2_KIND, duplicate=False)
    assert [container.name for container in node.containers] == ["layer2", "layer3"]
    assert node.get_attribute(name="lacp_rate").container is None
    assert node.get_attribute(name="lacp_mode").container is None


def test_container_marked_absent_on_a_first_load_is_dropped() -> None:
    schema = _lag_schema_with_generic_containers(
        [{"name": "legacy", "label": "Legacy", "state": HashableModelState.ABSENT.value}]
    )

    schema_branch = _processed_branch(schema=schema)

    for kind in (GENERIC_KIND, L2_KIND, "InfraLagInterfaceL3"):
        node = schema_branch.get(name=kind, duplicate=False)
        assert [container.name for container in node.containers] == ["lacp", "layer2", "layer3"]


def test_reference_to_a_container_marked_absent_on_a_first_load_is_refused() -> None:
    schema = _lag_schema_with_generic_containers(
        [{"name": "legacy", "label": "Legacy", "state": HashableModelState.ABSENT.value}]
    )
    lacp_rate = next(attribute for attribute in schema["generics"][0]["attributes"] if attribute["name"] == "lacp_rate")
    lacp_rate["container"] = "legacy"

    with pytest.raises(
        ValueError,
        match=exact_message(
            f"{L2_KIND}.attributes.lacp_rate.container: container 'legacy' is not declared on {L2_KIND}"
        ),
    ):
        _processed_branch(schema=schema)


def test_emptying_inherit_from_drops_the_inherited_containers() -> None:
    generic = {
        "name": "Item",
        "namespace": "Test",
        "containers": [{"name": "spare", "label": "Spare"}],
        "attributes": [{"name": "name", "kind": "Text"}],
    }
    node = {
        "name": "Thing",
        "namespace": "Test",
        "inherit_from": ["TestItem"],
        "containers": [{"name": "extra", "label": "Extra"}],
    }
    schema_branch = _processed_branch(schema={"version": "1.0", "generics": [generic], "nodes": [node]})

    schema_branch.load_schema(schema=SchemaRoot(version="1.0", nodes=[{**node, "inherit_from": []}]))
    schema_branch.process()

    containers = schema_branch.get(name="TestThing", duplicate=False).containers
    assert [(container.name, container.inherited) for container in containers] == [("extra", False)]


def test_reload_changing_only_the_container_order_changes_the_hash_and_the_diff() -> None:
    reordered = copy.deepcopy(LAG_SCHEMA)
    reordered["generics"][0]["containers"] = [
        {**container, "order_weight": None} for container in reversed(reordered["generics"][0]["containers"])
    ]
    original = copy.deepcopy(LAG_SCHEMA)
    original["generics"][0]["containers"] = [
        {**container, "order_weight": None} for container in original["generics"][0]["containers"]
    ]
    schema_branch = _processed_branch(schema=original)
    before = schema_branch.get_generic(name=GENERIC_KIND, duplicate=True)
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", generics=reordered["generics"]))
    schema_branch.process()
    after = schema_branch.get_generic(name=GENERIC_KIND, duplicate=False)

    assert [container.name for container in after.containers] == ["layer3", "layer2", "lacp"]
    assert after.get_hash() != before.get_hash()
    assert "containers" in before.diff(other=after).changed


def test_branches_compare_containers_in_order() -> None:
    containers = next(attribute for attribute in base_node_schema.attributes if attribute.name == "containers")

    assert containers.ordered is True
