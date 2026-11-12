from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.rack_elevation.constants import RackTotalAttribute

TOTAL_NAMES = RackTotalAttribute.available_types()


def _definition() -> dict[str, Any]:
    return {
        "generics": [
            {
                "name": "PhysicalDevice",
                "namespace": "Dcim",
                "include_in_menu": False,
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "position", "kind": "Number", "optional": True},
                    {
                        "name": "rack_face",
                        "kind": "Dropdown",
                        "optional": True,
                        "choices": [{"name": "front"}, {"name": "rear"}],
                    },
                ],
                "relationships": [
                    {"name": "location", "peer": "LocationRack", "optional": True, "cardinality": "one"},
                ],
                "rack_elevation": {
                    "role": "mountable",
                    "rack": "location",
                    "position": "position__value",
                    "face": "rack_face__value",
                },
            }
        ],
        "nodes": [
            {
                "name": "Rack",
                "namespace": "Location",
                "include_in_menu": False,
                "attributes": [{"name": "name", "kind": "Text"}, {"name": "height", "kind": "Number"}],
                "rack_elevation": {"role": "rack", "u_height": "height__value"},
            },
            {
                "name": "DeviceType",
                "namespace": "Dcim",
                "include_in_menu": False,
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "height", "kind": "Number"},
                    {"name": "full_depth", "kind": "Boolean"},
                    {"name": "weight", "kind": "Number", "optional": True},
                ],
                "rack_elevation": {
                    "role": "mountable_type",
                    "u_height": "height__value",
                    "full_depth": "full_depth__value",
                    "weight": "weight__value",
                },
            },
            {
                "name": "Device",
                "namespace": "Dcim",
                "include_in_menu": False,
                "inherit_from": ["DcimPhysicalDevice"],
                "relationships": [
                    {"name": "device_type", "peer": "DcimDeviceType", "optional": True, "cardinality": "one"},
                ],
                "rack_elevation": {
                    "role": "mountable",
                    "rack": "location",
                    "position": "position__value",
                    "face": "rack_face__value",
                    "type": "device_type",
                },
            },
        ],
    }


def _node(definition: dict[str, Any], kind: str) -> dict[str, Any]:
    for element in [*definition["generics"], *definition["nodes"]]:
        if f"{element['namespace']}{element['name']}" == kind:
            return element
    raise KeyError(kind)


def _process(definition: dict[str, Any]) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", **definition))
    schema_branch.process()
    return schema_branch


def _total_attributes(schema_branch: SchemaBranch, kind: str) -> list[AttributeSchema]:
    return [item for item in schema_branch.get(name=kind, duplicate=False).attributes if item.name in TOTAL_NAMES]


def test_valid_mapping_is_accepted() -> None:
    schema_branch = _process(_definition())

    mapping = schema_branch.get(name="DcimDevice", duplicate=False).rack_elevation
    assert mapping is not None
    assert mapping.role == "mountable"


def test_path_to_a_missing_attribute_is_refused_with_the_kind_key_and_path() -> None:
    definition = _definition()
    _node(definition, "DcimDevice")["rack_elevation"]["position"] = "positon__value"

    with pytest.raises(ValueError, match=r"DcimDevice\.rack_elevation\.position: .*positon"):
        _process(definition)


def test_path_to_an_attribute_of_the_wrong_kind_is_refused_with_the_kind_key_and_path() -> None:
    definition = _definition()
    _node(definition, "DcimDevice")["rack_elevation"]["position"] = "name__value"

    with pytest.raises(
        ValueError, match=r"DcimDevice\.rack_elevation\.position: attribute 'name' is a Text, expected a Number"
    ):
        _process(definition)


def test_path_must_end_with_the_value_property() -> None:
    definition = _definition()
    _node(definition, "DcimPhysicalDevice")["rack_elevation"]["face"] = "rack_face__color"

    with pytest.raises(ValueError, match=r"DcimPhysicalDevice\.rack_elevation\.face: .*__value"):
        _process(definition)


def test_face_dropdown_without_a_rear_choice_is_refused() -> None:
    definition = _definition()
    _node(definition, "DcimPhysicalDevice")["attributes"][2]["choices"] = [{"name": "front"}]

    with pytest.raises(
        ValueError, match=r"rack_elevation\.face: dropdown 'rack_face' must have the choices front, rear"
    ):
        _process(definition)


def test_type_relationship_to_a_peer_without_the_mountable_type_role_is_refused() -> None:
    definition = _definition()
    _node(definition, "DcimDeviceType")["rack_elevation"] = None
    del _node(definition, "DcimDeviceType")["rack_elevation"]

    with pytest.raises(
        ValueError, match=r"DcimDevice\.rack_elevation\.type: the peer 'DcimDeviceType' .* 'mountable_type'"
    ):
        _process(definition)


def test_rack_relationship_to_a_peer_without_the_rack_role_is_refused() -> None:
    definition = _definition()
    rack = _node(definition, "LocationRack")
    rack["attributes"].append({"name": "full_depth", "kind": "Boolean"})
    rack["rack_elevation"] = {"role": "mountable_type", "u_height": "height__value", "full_depth": "full_depth__value"}

    with pytest.raises(ValueError, match=r"rack_elevation\.rack: the peer 'LocationRack' .* 'rack'"):
        _process(definition)


def test_rack_relationship_to_a_generic_peer_is_accepted() -> None:
    definition = _definition()
    definition["generics"].append(
        {"name": "Hosting", "namespace": "Location", "attributes": [{"name": "name", "kind": "Text"}]}
    )
    rack = _node(definition, "LocationRack")
    rack["inherit_from"] = ["LocationHosting"]
    rack["attributes"] = [item for item in rack["attributes"] if item["name"] != "name"]
    _node(definition, "DcimPhysicalDevice")["relationships"][0]["peer"] = "LocationHosting"

    schema_branch = _process(definition)

    assert schema_branch.get(name="DcimPhysicalDevice", duplicate=False).get_relationship("location").peer == (
        "LocationHosting"
    )


def test_node_must_name_its_type_relationship() -> None:
    definition = _definition()
    del _node(definition, "DcimDevice")["rack_elevation"]["type"]

    with pytest.raises(ValueError, match=r"DcimDevice\.rack_elevation\.type: a node must name its type relationship"):
        _process(definition)


@pytest.mark.parametrize("name", TOTAL_NAMES)
def test_rack_kind_with_its_own_calculated_attribute_is_refused(name: str) -> None:
    definition = _definition()
    _node(definition, "LocationRack")["attributes"].append({"name": name, "kind": "Number", "optional": True})

    with pytest.raises(
        ValueError, match=rf"LocationRack\.rack_elevation: attribute '{name}' is calculated by Infrahub"
    ):
        _process(definition)


def test_node_inherits_the_mapping_of_its_generic() -> None:
    definition = _definition()
    device = _node(definition, "DcimDevice")
    generic = _node(definition, "DcimPhysicalDevice")
    generic["relationships"].extend(device.pop("relationships"))
    generic["rack_elevation"]["type"] = "device_type"
    del device["rack_elevation"]

    schema_branch = _process(definition)

    mapping = schema_branch.get(name="DcimDevice", duplicate=False).rack_elevation
    assert mapping is not None
    assert mapping.model_dump(exclude={"id", "state"}) == {
        "role": "mountable",
        "rack": "location",
        "position": "position__value",
        "face": "rack_face__value",
        "type": "device_type",
    }


def test_own_mapping_of_a_node_replaces_the_mapping_of_its_generic() -> None:
    schema_branch = _process(_definition())

    generic_mapping = schema_branch.get(name="DcimPhysicalDevice", duplicate=False).rack_elevation
    node_mapping = schema_branch.get(name="DcimDevice", duplicate=False).rack_elevation
    assert generic_mapping is not None
    assert node_mapping is not None
    assert getattr(generic_mapping, "type", None) is None
    assert getattr(node_mapping, "type", None) == "device_type"


def test_rack_kind_gets_the_three_read_only_attributes() -> None:
    schema_branch = _process(_definition())

    attributes = _total_attributes(schema_branch, "LocationRack")
    assert sorted(item.name for item in attributes) == sorted(TOTAL_NAMES)
    assert all(item.kind == "Number" and item.read_only and item.optional for item in attributes)
    assert _total_attributes(schema_branch, "DcimDevice") == []


def test_processing_the_same_schema_twice_gives_the_same_result() -> None:
    schema_branch = _process(_definition())
    hash_before = schema_branch.get_hash()

    schema_branch.load_schema(schema=SchemaRoot(version="1.0", **_definition()))
    schema_branch.process()

    assert schema_branch.get_hash() == hash_before
    assert len(_total_attributes(schema_branch, "LocationRack")) == len(TOTAL_NAMES)


def test_removing_the_mapping_of_a_rack_kind_removes_its_calculated_attributes() -> None:
    schema_branch = _process(_definition())
    rack = schema_branch.get_node(name="LocationRack")
    rack.rack_elevation = None
    schema_branch.set(name="LocationRack", schema=rack)

    schema_branch.add_rack_elevation_attributes()

    assert {item.state for item in _total_attributes(schema_branch, "LocationRack")} == {HashableModelState.ABSENT}


def test_renaming_an_attribute_used_by_a_mapping_is_refused_on_the_next_load() -> None:
    schema_branch = _process(_definition())
    renamed = deepcopy(_definition())
    rack = _node(renamed, "LocationRack")
    rack["attributes"] = [{"name": "height", "kind": "Number", "state": "absent"}, {"name": "units", "kind": "Number"}]

    schema_branch.load_schema(schema=SchemaRoot(version="1.0", nodes=[rack]))

    with pytest.raises(ValueError, match=r"LocationRack\.rack_elevation\.u_height: .*height"):
        schema_branch.process()
