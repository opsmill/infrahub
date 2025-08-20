from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase

from .interface import MutationNodeGetterInterface


class MutationNodeGetterByHfid(MutationNodeGetterInterface):
    def __init__(self, db: InfrahubDatabase, node_manager: NodeManager) -> None:
        self.db = db
        self.node_manager = node_manager

    async def get_node(
        self,
        node_schema: MainSchemaTypes,
        data: InputObjectType,
        branch: Branch,
    ) -> Node | None:
        if not node_schema.human_friendly_id:
            return None

        if "hfid" in data:
            return await self.node_manager.get_one_by_hfid(
                db=self.db,
                hfid=data["hfid"],
                kind=node_schema.kind,
                branch=branch,
            )

        for component in node_schema.human_friendly_id:
            name = component.split("__")[0]
            if name not in data.keys():
                # The update neither includes "hfid" or all components to form an hfid:
                return None

        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        hfid: list[str] = []
        for component in node_schema.human_friendly_id:
            attribute_path = node_schema.parse_schema_path(path=component, schema=schema_branch)

            if attribute_path.is_type_attribute and attribute_path.attribute_schema:
                hfid_component = data[attribute_path.attribute_schema.name].get(attribute_path.attribute_property_name)
                if hfid_component is not None:
                    hfid.append(str(hfid_component))
            if (
                attribute_path.relationship_schema
                and attribute_path.related_schema
                and attribute_path.attribute_property_name
                and attribute_path.attribute_schema
            ):
                related_node = await self.node_manager.find_object(
                    db=self.db,
                    kind=attribute_path.relationship_schema.peer,
                    branch=branch,
                    id=data[attribute_path.relationship_schema.name].get("id"),
                    hfid=data[attribute_path.relationship_schema.name].get("hfid"),
                )
                relationship_attribute = getattr(related_node, attribute_path.attribute_schema.name)
                relationship_attribute_value = getattr(relationship_attribute, attribute_path.attribute_property_name)
                if relationship_attribute_value is None:
                    return None

                hfid.append(str(relationship_attribute_value))

        if len(hfid) == len(node_schema.human_friendly_id):
            return await self.node_manager.get_one_by_hfid(
                db=self.db,
                hfid=hfid,
                kind=node_schema.kind,
                branch=branch,
            )

        return None
