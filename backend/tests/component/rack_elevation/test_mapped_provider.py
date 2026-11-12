from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.node.rack import RackElevationRackNode
from infrahub.core.schema import SchemaRoot
from infrahub.rack_elevation.constants import RACK_ELEVATION_RACK_NODE_KEY
from infrahub.rack_elevation.models import RackRole
from infrahub.rack_elevation.provider import build_rack_elevation_provider
from tests.helpers.schema import load_schema as load_test_schema

from .dataset import (
    ACCESSORY_KIND,
    ACCESSORY_TYPE_KIND,
    DEVICE_KIND,
    DEVICE_TYPE_KIND,
    RACK_KIND,
    RackOptionFixture,
)
from .helpers import RunGraphQL, formatted_errors
from .option_2 import SCHEMA_FILE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

PHYSICAL_DEVICE_GENERIC = "DcimPhysicalDevice"


async def test_list_kinds_returns_the_generic_and_the_five_kinds_with_their_roles(
    rack_ids: dict[str, str], db: InfrahubDatabase, default_branch: Branch
) -> None:
    provider = build_rack_elevation_provider(db=db, branch=default_branch, at=None)

    roles_by_kind = {entry.kind: entry.role for entry in provider.list_kinds()}

    assert roles_by_kind == {
        RACK_KIND: RackRole.RACK,
        DEVICE_KIND: RackRole.MOUNTABLE,
        ACCESSORY_KIND: RackRole.MOUNTABLE,
        PHYSICAL_DEVICE_GENERIC: RackRole.MOUNTABLE,
        DEVICE_TYPE_KIND: RackRole.MOUNTABLE_TYPE,
        ACCESSORY_TYPE_KIND: RackRole.MOUNTABLE_TYPE,
    }


async def test_item_without_a_type_loads_with_no_type_and_no_height(
    rack_ids: dict[str, str], db: InfrahubDatabase, default_branch: Branch
) -> None:
    provider = build_rack_elevation_provider(db=db, branch=default_branch, at=None)

    item = await provider.load_item(item_id=rack_ids["spare2"])

    assert item.type_id is None
    assert item.type_display_label is None
    assert item.weight is None
    assert item.u_height == 0
    assert item.full_depth is False


@pytest.mark.parametrize(
    ("position", "face", "field_name"),
    [(12, "front", "position"), (12, "rear", "position"), (None, "front", "rack_face")],
    ids=["occupied-front", "occupied-rear", "face-without-position"],
)
async def test_refused_save_names_the_customer_attribute(
    position: int | None,
    face: str,
    field_name: str,
    rack_ids: dict[str, str],
    rack_option: RackOptionFixture,
    default_branch: Branch,
    run_graphql: RunGraphQL,
) -> None:
    document, variables = rack_option.standard_update_mutation(
        item_name="leaf2", item_id=rack_ids["leaf2"], rack_id=rack_ids["R1"], position=position, face=face
    )

    result = await run_graphql(branch=default_branch, document=document, variables=variables)

    errors = formatted_errors(result)
    assert len(errors) == 1
    assert errors[0]["extensions"]["data"]["field_name"] == field_name


async def test_saving_an_item_in_a_location_that_is_not_a_rack_is_refused_on_the_rack_relationship(
    register_core_models_schema: None,
    db: InfrahubDatabase,
    default_branch: Branch,
    run_graphql: RunGraphQL,
    rack_option: RackOptionFixture,
) -> None:
    schema = yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8"))
    schema["generics"].append(
        {
            "name": "Hosting",
            "namespace": "Location",
            "include_in_menu": False,
            "display_labels": ["name__value"],
            "attributes": [{"name": "name", "kind": "Text"}],
        }
    )
    schema["nodes"].append(
        {
            "name": "Site",
            "namespace": "Location",
            "include_in_menu": False,
            "inherit_from": ["LocationHosting"],
        }
    )
    for element in schema["nodes"]:
        if element["name"] == "Rack":
            element["inherit_from"] = ["LocationHosting"]
            element["attributes"] = [item for item in element["attributes"] if item["name"] != "name"]
    for element in schema["generics"]:
        if element["name"] == "PhysicalDevice":
            element["relationships"][0]["peer"] = "LocationHosting"
    registry.node[RACK_ELEVATION_RACK_NODE_KEY] = RackElevationRackNode
    await load_test_schema(db=db, schema=SchemaRoot(**schema), branch_name=default_branch.name)

    site = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await site.new(db=db, name="R1-site")
    await site.save(db=db)
    device = await Node.init(db=db, schema=DEVICE_KIND, branch=default_branch)
    await device.new(db=db, name="leaf1")
    await device.save(db=db)

    document, variables = rack_option.standard_update_mutation(
        item_name="leaf1", item_id=device.id, rack_id=site.id, position=None, face=None
    )
    result = await run_graphql(branch=default_branch, document=document, variables=variables)

    errors = formatted_errors(result)
    assert len(errors) == 1
    assert errors[0]["extensions"]["data"]["constraint"] == "RACK_NOT_A_RACK"
    assert errors[0]["extensions"]["data"]["field_name"] == "location"
