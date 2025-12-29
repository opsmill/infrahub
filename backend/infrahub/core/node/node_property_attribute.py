from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from infrahub_sdk.template import Jinja2Template

from infrahub.core.query.node import AttributeFromDB
from infrahub.core.schema import NodeSchema, ProfileSchema, TemplateSchema

from ..attribute import BaseAttribute, ListAttributeOptional, StringOptional

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema, ProfileSchema, TemplateSchema
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

T = TypeVar("T")


class NodePropertyAttribute[T]:
    """A node property attribute is a construct that seats between a property and an attribute.

    View it as a property, set at the node level but stored in the database as an attribute. It usually is something computed from other components of
    a node, such as its attributes and its relationships.
    """

    def __init__(
        self,
        node_schema: NodeSchema | ProfileSchema | TemplateSchema,
        template: T | None,
        value: AttributeFromDB | T | None = None,
    ) -> None:
        self.node_schema = node_schema

        self.node_attributes: list[str] = []
        self.node_relationships: list[str] = []

        self.template = template
        self._value = value
        self._manually_assigned = False

        self.schema: AttributeSchema

        self.analyze_variables()

    def needs_update(self, fields: list[str] | None) -> bool:
        """Tell if this node property attribute must be recomputed given a list of updated fields of a node."""
        if self._manually_assigned or not fields:
            return True
        for field in fields:
            if field in self.node_attributes or field in self.node_relationships:
                return True

        return False

    @property
    def attribute_value(self) -> AttributeFromDB | dict[str, T | None]:
        if isinstance(self._value, AttributeFromDB):
            return self._value
        return {"value": self._value}

    def set_value(self, value: T | None, manually_assigned: bool = False) -> None:
        """Force the value of the node property attribute to the given one."""
        if isinstance(self._value, AttributeFromDB):
            self._value.value = value
        else:
            self._value = value

        if manually_assigned:
            self._manually_assigned = True

    def get_value(self, node: Node, at: Timestamp) -> T | None:
        if isinstance(self._value, AttributeFromDB):
            attr = self.get_node_attribute(node=node, at=at)
            return attr.value  # type: ignore

        return self._value

    @abstractmethod
    def analyze_variables(self) -> None: ...

    @abstractmethod
    async def compute(self, db: InfrahubDatabase, node: Node) -> None: ...

    @abstractmethod
    def get_node_attribute(self, node: Node, at: Timestamp) -> BaseAttribute: ...


class DisplayLabel(NodePropertyAttribute[str]):
    def __init__(
        self,
        node_schema: NodeSchema | ProfileSchema | TemplateSchema,
        template: str | None,
        value: AttributeFromDB | str | None = None,
    ) -> None:
        super().__init__(node_schema=node_schema, template=template, value=value)

        self.schema = node_schema.get_attribute(name="display_label")

    @property
    def is_jinja2_template(self) -> bool:
        if self.template is None:
            return False

        return any(c in self.template for c in "{}")

    def _analyze_plain_value(self) -> None:
        if self.template is None or "__" not in self.template:
            return

        items = self.template.split("__", maxsplit=1)
        if items[0] not in self.node_schema.attribute_names:
            raise ValueError(f"{items[0]} is not an attribute of {self.node_schema.kind}")

        self.node_attributes.append(items[0])

    def _analyze_jinja2_value(self) -> None:
        if self.template is None or not self.is_jinja2_template:
            return

        tpl = Jinja2Template(template=self.template)
        for variable in tpl.get_variables():
            items = variable.split("__", maxsplit=1)
            if items[0] in self.node_schema.attribute_names:
                self.node_attributes.append(items[0])
            elif items[0] in self.node_schema.relationship_names:
                self.node_relationships.append(items[0])
            else:
                raise ValueError(f"{items[0]} is neither an attribute or a relationship of {self.node_schema.kind}")

    def analyze_variables(self) -> None:
        """Look at variables used in the display label and record attributes and relationships required to compute it."""
        if not self.is_jinja2_template:
            self._analyze_plain_value()
        else:
            self._analyze_jinja2_value()

    async def compute(self, db: InfrahubDatabase, node: Node) -> None:
        """Update the display label value by recomputing it from the template."""
        if self.template is None or self._manually_assigned:
            return

        if node.get_schema() != self.node_schema:
            raise ValueError(
                f"display_label for schema {self.node_schema.kind} cannot be rendered for node {node.get_schema().kind} {node.id}"
            )

        if not self.is_jinja2_template:
            path_value = await node.get_path_value(db=db, path=self.template)
            # Use .value for enum to keep compat with old style display label
            self.set_value(value=str(path_value if not isinstance(path_value, Enum) else path_value.value))
            return

        jinja2_template = Jinja2Template(template=self.template)

        variables: dict[str, Any] = {}
        for variable in jinja2_template.get_variables():
            variables[variable] = await node.get_path_value(db=db, path=variable)

        self.set_value(value=await jinja2_template.render(variables=variables))

    def get_node_attribute(self, node: Node, at: Timestamp) -> StringOptional:
        """Return a node attribute that can be stored in the database for this display label and node."""
        return StringOptional(
            name="display_label",
            schema=self.schema,
            branch=node.get_branch(),
            at=at,
            node=node,
            data=self.attribute_value,
        )


class HumanFriendlyIdentifier(NodePropertyAttribute[list[str]]):
    def __init__(
        self,
        node_schema: NodeSchema | ProfileSchema | TemplateSchema,
        template: list[str] | None,
        value: AttributeFromDB | list[str] | None = None,
    ) -> None:
        super().__init__(node_schema=node_schema, template=template, value=value)

        self.schema = node_schema.get_attribute(name="human_friendly_id")

    def _analyze_single_variable(self, value: str) -> None:
        items = value.split("__", maxsplit=1)
        if items[0] in self.node_schema.attribute_names:
            self.node_attributes.append(items[0])
        elif items[0] in self.node_schema.relationship_names:
            self.node_relationships.append(items[0])
        else:
            raise ValueError(f"{items[0]} is neither an attribute or a relationship of {self.node_schema.kind}")

    def analyze_variables(self) -> None:
        """Look at variables used in the HFID and record attributes and relationships required to compute it."""
        for item in self.template or []:
            self._analyze_single_variable(value=item)

    async def compute(self, db: InfrahubDatabase, node: Node) -> None:
        """Update the HFID value by recomputing it from the template."""
        if self.template is None or self._manually_assigned:
            return

        if node.get_schema() != self.node_schema:
            raise ValueError(
                f"human_friendly_id for schema {self.node_schema.kind} cannot be computed for node {node.get_schema().kind} {node.id}"
            )

        value: list[str] = []
        for path in self.template:
            path_value = await node.get_path_value(db=db, path=path)
            # Use .value for enum to be consistent with display label
            value.append(path_value if not isinstance(path_value, Enum) else path_value.value)

        self.set_value(value=value)

    def get_node_attribute(self, node: Node, at: Timestamp) -> ListAttributeOptional:
        """Return a node attribute that can be stored in the database for this HFID and node."""
        return ListAttributeOptional(
            name="human_friendly_id",
            schema=self.schema,
            branch=node.get_branch(),
            at=at,
            node=node,
            data=self.attribute_value,
        )
