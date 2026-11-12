"""The rack model of option 2: the customer's own schema, with `rack_elevation` mappings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.node.rack import RackElevationRackNode
from infrahub.core.schema import SchemaRoot
from infrahub.rack_elevation.constants import RACK_ELEVATION_RACK_NODE_KEY
from tests.helpers.schema import load_schema as load_test_schema

from .dataset import ACCESSORY_KIND, DEVICE_KIND, ITEMS, RACK_KIND, RACKS, TYPES

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SCHEMA_FILE = Path(__file__).parent / "schemas" / "option_2.yml"

TYPE_RELATIONSHIP_BY_KIND = {DEVICE_KIND: "device_type", ACCESSORY_KIND: "accessory_type"}
UPDATE_MUTATION_BY_KIND = {DEVICE_KIND: "DcimDeviceUpdate", ACCESSORY_KIND: "DcimRackAccessoryUpdate"}

UPDATE_DOCUMENT = """
mutation ($id: String!, $position: Int, $face: String, $rack: String!) {
  %s(data: {id: $id, position: {value: $position}, rack_face: {value: $face}, location: {id: $rack}}) {
    ok
  }
}
"""


class Option2:
    async def load_schema(self, db: InfrahubDatabase, branch: Branch) -> None:
        registry.node[RACK_ELEVATION_RACK_NODE_KEY] = RackElevationRackNode
        schema = SchemaRoot(**yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8")))
        await load_test_schema(db=db, schema=schema, branch_name=branch.name)

    async def create_dataset(self, db: InfrahubDatabase, branch: Branch) -> dict[str, str]:
        ids: dict[str, str] = {}
        for rack in RACKS:
            ids[rack.name] = await self._create(
                db=db, branch=branch, kind=RACK_KIND, data={"name": rack.name, "height": rack.u_height}
            )
        for item_type in TYPES:
            ids[item_type.name] = await self._create(
                db=db,
                branch=branch,
                kind=item_type.kind,
                data={
                    "name": item_type.name,
                    "height": item_type.u_height,
                    "full_depth": item_type.full_depth,
                    "weight": item_type.weight,
                },
            )
        for item in ITEMS:
            data: dict[str, Any] = {"name": item.name, "location": ids[item.rack_name]}
            if item.role:
                data["role"] = item.role
            if item.type_name:
                data[TYPE_RELATIONSHIP_BY_KIND[item.kind]] = ids[item.type_name]
            if item.position is not None:
                data["position"] = item.position
                data["rack_face"] = item.face
            ids[item.name] = await self._create(db=db, branch=branch, kind=item.kind, data=data)
        return ids

    def standard_update_mutation(
        self, item_name: str, item_id: str, rack_id: str, position: int | None, face: str | None
    ) -> tuple[str, dict[str, Any]]:
        kind = next(item.kind for item in ITEMS if item.name == item_name)
        return UPDATE_DOCUMENT % UPDATE_MUTATION_BY_KIND[kind], {
            "id": item_id,
            "rack": rack_id,
            "position": position,
            "face": face,
        }

    @staticmethod
    async def _create(db: InfrahubDatabase, branch: Branch, kind: str, data: dict[str, Any]) -> str:
        node = await Node.init(db=db, schema=kind, branch=branch)
        await node.new(db=db, **data)
        await node.save(db=db)
        return node.id
