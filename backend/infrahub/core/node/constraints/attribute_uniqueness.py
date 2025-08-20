from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

from .interface import NodeConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


class NodeAttributeUniquenessConstraint(NodeConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def check(self, node: Node, at: Timestamp | None = None, filters: list[str] | None = None) -> None:
        at = Timestamp(at)
        node_schema = node.get_schema()
        for unique_attr in node_schema.unique_attributes:
            if filters and unique_attr.name not in filters:
                continue

            comparison_schema: MainSchemaTypes = node_schema
            attr = getattr(node, unique_attr.name)
            if unique_attr.inherited:
                for generic_parent_schema_name in node_schema.inherit_from:
                    generic_parent_schema = self.db.schema.get(generic_parent_schema_name, branch=self.branch)
                    parent_attr = generic_parent_schema.get_attribute_or_none(unique_attr.name)
                    if parent_attr is None:
                        continue
                    if parent_attr.unique is True:
                        comparison_schema = generic_parent_schema
                        break
            nodes = await registry.manager.query(
                schema=comparison_schema,
                filters={f"{unique_attr.name}__value": attr.value},
                fields={},
                db=self.db,
                branch=self.branch,
                at=at,
            )

            if any(n for n in nodes if n.get_id() != node.id):
                raise ValidationError(
                    {unique_attr.name: f"An object already exist with this value: {unique_attr.name}: {attr.value}"}
                )
