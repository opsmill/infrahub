from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query.node import AttributeFromDB
from infrahub.core.schema.attribute_schema import AttributeSchema

from ..attribute import ListAttribute

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class HumanFriendlyIdentifier:
    def __init__(
        self,
        node_schema: NodeSchema | ProfileSchema | TemplateSchema,
        template: list[str] | None,
        value: list[str] | AttributeFromDB | None = None,
    ) -> None:
        self.node_schema = node_schema
        self.template = template
        self._value = value
        self.node_attributes: list[str] = []
        self.node_relationships: list[str] = []

        self.analyze_variables()

    @property
    def attribute_value(self) -> AttributeFromDB | dict[str, list[str] | None]:
        if isinstance(self._value, AttributeFromDB):
            return self._value
        return {"value": self._value}

    @property
    def value(self) -> list[str] | None:
        if isinstance(self._value, AttributeFromDB):
            return self._value.value
        return self._value

    def _update_value(self, value: list[str] | None) -> None:
        """Update the value of the HFID without overriding the attribute node in the database if it already exists."""
        if isinstance(self._value, AttributeFromDB):
            self._value.value = value
        else:
            self._value = value

    def needs_update(self, fields: list[str] | None) -> bool:
        """Tell if a display label must be recomputed given a list of updated fields of a node."""
        for field in fields or []:
            if field in self.node_attributes or field in self.node_relationships:
                return True

        return False

    async def _get_element_value(self, db: InfrahubDatabase, path: str, node: Node) -> Any:
        schema_path = self.node_schema.parse_schema_path(
            path=path, schema=db.schema.get_schema_branch(name=node.get_branch().name)
        )

        if schema_path.is_type_attribute:
            attr = getattr(node, schema_path.active_attribute_schema.name)
            return getattr(node, schema_path.active_attribute_property_name)

        # Not an attribute so matching schema_path.is_type_relationship:
        relm: RelationshipManager = getattr(self, schema_path.active_relationship_schema.name)
        await relm.resolve(db=db)
        peer = await relm.get_peer(db=db)
        attr = getattr(peer, schema_path.active_attribute_schema.name)
        return getattr(attr, schema_path.active_attribute_property_name)

    def _analyze_plain_value(self, value: str) -> None:
        items = value.split("__", maxsplit=1)
        if items[0] in self.node_schema.attribute_names:
            self.node_attributes.append(items[0])
        elif items[0] in self.node_schema.relationship_names:
            self.node_relationships.append(items[0])
        else:
            raise ValueError(f"{items[0]} is neither an attribute or a relationship of {self.node_schema.kind}")

    def analyze_variables(self) -> None:
        """Look at variables used in the display label and record attributes and relationships required to compute it."""
        for item in self.template or []:
            self._analyze_plain_value(value=item)

    async def compute(self, db: InfrahubDatabase, node: Node) -> None:
        """Update the display label value by recomputing it from the template."""
        if self.template is None:
            return

        if node.get_schema() != self.node_schema:
            raise ValueError(
                f"display_label for schema {self.node_schema.kind} cannot be rendered for node {node.get_schema().kind} {node.id}"
            )

        value: list[str] = []
        for path in self.template:
            value.append(str(await node.get_path_value(db=db, path=path)))

        self._update_value(value=value)

    async def get_node_attribute(self, node: Node, at: Timestamp) -> ListAttribute:
        """Return a node attribute that can be stored in the database for this display label and node."""
        return ListAttribute(
            name="human_friendly_id",
            schema=AttributeSchema(name="human_friendly_id", kind="List", branch=self.node_schema.branch),
            branch=node.get_branch(),
            at=at,
            node=node,
            data=self.attribute_value,
        )
