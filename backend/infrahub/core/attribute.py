from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import ujson

from infrahub.core import registry
from infrahub.core.constants import RelationshipStatus
from infrahub.core.property import FlagPropertyMixin, NodePropertyMixin
from infrahub.core.query import QueryElement, QueryNode, QueryRel
from infrahub.core.query.attribute import (
    AttributeCreateQuery,
    AttributeGetQuery,
    AttributeUpdateFlagQuery,
    AttributeUpdateNodePropertyQuery,
    AttributeUpdateValueQuery,
)
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import add_relationship, update_relationships_to
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import AttributeSchema

# pylint: disable=redefined-builtin,c-extension-no-member


class BaseAttribute(FlagPropertyMixin, NodePropertyMixin):
    type = None

    _rel_to_node_label: str = "HAS_ATTRIBUTE"
    _rel_to_value_label: str = "HAS_VALUE"

    def __init__(
        self,
        name: str,
        schema: AttributeSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        id: UUID = None,
        db_id: Optional[str] = None,
        data: Union[dict, str] = None,
        updated_at: Union[Timestamp, str] = None,
        **kwargs,
    ):
        self.id: UUID = id
        self.db_id: str = db_id

        self.updated_at = updated_at
        self.name = name
        self.node = node
        self.schema = schema
        self.branch = branch
        self.at = at

        self._init_node_property_mixin(kwargs)
        self._init_flag_property_mixin(kwargs)

        self.value = None

        if data is not None and isinstance(data, dict):
            self.value = self.from_db(data.get("value", None))

            fields_to_extract_from_data = ["id", "db_id"] + self._flag_properties + self._node_properties
            for field_name in fields_to_extract_from_data:
                setattr(self, field_name, data.get(field_name, None))

            if not self.updated_at and "updated_at" in data:
                self.updated_at = Timestamp(data.get("updated_at"))

        elif data is not None:
            self.value = self.from_db(data)

        # Assign default values
        if self.value is None and self.schema.default_value is not None:
            self.value = self.schema.default_value

        if self.value is not None:
            self.validate(value=self.value, name=self.name, schema=self.schema)

        if self.is_protected is None:
            self.is_protected = False

        if self.is_visible is None:
            self.is_visible = True

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry.attribute[cls.__name__] = cls

    def get_kind(self) -> str:
        return self.schema.kind

    @classmethod
    def validate(cls, value: Any, name: str, schema: AttributeSchema) -> bool:
        if value is None and schema.optional is False:
            raise ValidationError({name: f"A value must be provided for {name}"})
        if value is None and schema.optional is True:
            return True

        cls.validate_format(value=value, name=name, schema=schema)
        cls.validate_content(value=value, name=name, schema=schema)

        return True

    @classmethod
    def validate_format(cls, value: Any, name: str, schema: AttributeSchema) -> None:
        """Validate the format of the attribute.

        Args:
            value (Any): value to validate
            name (str): name of the attribute to include in a potential error message
            schema (AttributeSchema): schema for this attribute

        Raises:
            ValidationError: Format of the attribute value is not valid
        """
        if not isinstance(value, cls.type):  # pylint: disable=isinstance-second-argument-not-valid-type
            raise ValidationError({name: f"{name} is not of type {schema.kind}"})

    @classmethod
    def validate_content(cls, value: Any, name: str, schema: AttributeSchema) -> None:
        """Validate the content of the attribute.

        Args:
            value (Any): value to validate
            name (str): name of the attribute to include in a potential error message
            schema (AttributeSchema): schema for this attribute

        Raises:
            ValidationError: Content of the attribute value is not valid
        """

        if schema.regex:
            try:
                is_valid = re.match(pattern=schema.regex, string=str(value))
            except re.error as exc:
                raise ValidationError(
                    {name: f"The regex defined in the schema is not valid ({schema.regex!r})"}
                ) from exc

            if not is_valid:
                raise ValidationError({name: f"{value} be conform with the regex: {schema.regex!r}"})

        if schema.min_length:
            if len(value) < schema.min_length:
                raise ValidationError({name: f"{value} must have a minimum length of {schema.min_length!r}"})

        if schema.max_length:
            if len(value) > schema.max_length:
                raise ValidationError({name: f"{value} must have a maximum length of {schema.max_length!r}"})

        if schema.enum:
            if value not in schema.enum:
                raise ValidationError({name: f"{value} must be one of {schema.enum!r}"})

    def to_db(self):
        if self.value is None:
            return "NULL"

        return self.serialize(self.value)

    @classmethod
    def from_db(cls, value: Any):
        if value == "NULL":
            return None

        return cls.deserialize(value)

    @classmethod
    def serialize(cls, value: Any) -> Any:
        """Serialize the value before storing it in the database."""
        return value

    @classmethod
    def deserialize(cls, value: Any) -> Any:
        """Deserialize the value coming from the database."""
        return value

    async def save(self, session: AsyncSession, at: Optional[Timestamp] = None):
        """Create or Update the Attribute in the database."""

        save_at = Timestamp(at)

        if self.id:
            return await self._update(at=save_at, session=session)

        return await self._create(at=save_at, session=session)

    async def delete(self, session: AsyncSession, at: Optional[Timestamp] = None) -> bool:
        if not self.db_id:
            return False

        delete_at = Timestamp(at)

        query = await AttributeGetQuery.init(session=session, attr=self)
        await query.execute(session=session)
        results = query.get_results()

        if not results:
            return False

        properties_to_delete = []

        # Check all the relationship and update the one that are in the same branch
        rel_ids_to_update = set()
        for result in results:
            properties_to_delete.append((result.get("r2").type, result.get("ap").element_id))

            await add_relationship(
                src_node_id=self.db_id,
                dst_node_id=result.get("ap").element_id,
                rel_type=result.get("r2").type,
                branch_name=self.branch.name,
                branch_level=self.branch.hierarchy_level,
                at=delete_at,
                status=RelationshipStatus.DELETED,
                session=session,
            )

            for rel in result.get_rels():
                if rel.get("branch") == self.branch.name:
                    rel_ids_to_update.add(rel.element_id)

        if rel_ids_to_update:
            await update_relationships_to(ids=list(rel_ids_to_update), to=delete_at, session=session)

        await add_relationship(
            src_node_id=self.node.db_id,
            dst_node_id=self.db_id,
            rel_type="HAS_ATTRIBUTE",
            branch_name=self.branch.name,
            branch_level=self.branch.hierarchy_level,
            at=delete_at,
            status=RelationshipStatus.DELETED,
            session=session,
        )

        return True

    async def _create(self, session: AsyncSession, at: Optional[Timestamp] = None) -> bool:
        create_at = Timestamp(at)

        query = await AttributeCreateQuery.init(session=session, attr=self, branch=self.branch, at=create_at)
        await query.execute(session=session)

        self.id, self.db_id = query.get_new_ids()
        self.at = create_at

        return True

    async def _update(self, session: AsyncSession, at: Optional[Timestamp] = None) -> bool:
        """Update the attribute in the database.

        Get the current value
         - If the value is the same, do nothing
         - If the value is inherited and is different, raise error (for now just ignore)
         - If the value is different, create new node and update relationship

        """

        update_at = Timestamp(at)

        # Validate if the value is still correct, will raise a ValidationError if not
        self.validate(value=self.value, name=self.name, schema=self.schema)

        query = await NodeListGetAttributeQuery.init(
            session=session,
            ids=[self.node.id],
            fields={self.name: True},
            branch=self.branch,
            at=update_at,
            include_source=True,
            include_owner=True,
        )
        await query.execute(session=session)
        current_attr = query.get_result_by_id_and_name(self.node.id, self.name)

        # ---------- Update the Value ----------
        current_value = self.from_db(current_attr.get("av").get("value"))

        if current_value != self.value:
            # Create the new AttributeValue and update the existing relationship
            query = await AttributeUpdateValueQuery.init(session=session, attr=self, at=update_at)
            await query.execute(session=session)

            # TODO check that everything went well
            rel = current_attr.get("r2")
            if rel.get("branch") == self.branch.name:
                await update_relationships_to([rel.element_id], to=update_at, session=session)

        # ---------- Update the Flags ----------
        SUPPORTED_FLAGS = (
            ("is_visible", "isv", "rel_isv"),
            ("is_protected", "isp", "rel_isp"),
        )

        for flag_name, node_name, rel_name in SUPPORTED_FLAGS:
            if current_attr.get(node_name).get("value") != getattr(self, flag_name):
                query = await AttributeUpdateFlagQuery.init(
                    session=session, attr=self, at=update_at, flag_name=flag_name
                )
                await query.execute(session=session)

                rel = current_attr.get(rel_name)
                if rel.get("branch") == self.branch.name:
                    await update_relationships_to([rel.element_id], to=update_at, session=session)

        # ---------- Update the Node Properties ----------
        for prop in self._node_properties:
            if getattr(self, f"{prop}_id") and not (
                current_attr.get(prop) and current_attr.get(prop).get("uuid") == getattr(self, f"{prop}_id")
            ):
                query = await AttributeUpdateNodePropertyQuery.init(
                    session=session, attr=self, at=update_at, prop_name=prop, prop_id=getattr(self, f"{prop}_id")
                )
                await query.execute(session=session)

                rel = current_attr.get(f"rel_{prop}")
                if rel and rel.get("branch") == self.branch.name:
                    await update_relationships_to([rel.element_id], to=update_at, session=session)

        return True

    @classmethod
    def get_query_filter(  # pylint: disable=unused-argument
        cls,
        name: str,
        filter_name: str,
        branch=None,
        filter_value: Optional[Union[str, int, bool]] = None,
        include_match: bool = True,
        param_prefix: Optional[str] = None,
    ) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
        """Generate Query String Snippet to filter the right node."""

        query_filter: List[QueryElement] = []
        query_params: Dict[str, Any] = {}
        query_where: List[str] = []

        if filter_value and not isinstance(filter_value, (str, bool, int)):
            raise TypeError(f"filter {filter_name}: {filter_value} ({type(filter_value)}) is not supported.")

        param_prefix = param_prefix or f"attr_{name}"

        if include_match:
            query_filter.append(QueryNode(name="n"))

        query_filter.extend(
            [
                QueryRel(labels=[cls._rel_to_node_label]),
                QueryNode(name="i", labels=["Attribute"], params={"name": f"${param_prefix}_name"}),
                QueryRel(labels=["HAS_VALUE"]),
                QueryNode(name="av", labels=["AttributeValue"]),
            ]
        )
        query_params[f"{param_prefix}_name"] = name

        if filter_value is not None:
            query_filter[-1].params = {"value": f"${param_prefix}_value"}
            query_params[f"{param_prefix}_value"] = filter_value

        return query_filter, query_params, query_where

    async def to_graphql(self, session: AsyncSession, fields: dict = None) -> dict:
        """Generate GraphQL Payload for this attribute."""

        response = {
            "id": self.id,
        }

        for field_name in fields.keys():
            if field_name == "updated_at":
                if self.updated_at:
                    response[field_name] = await self.updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            if field_name == "__typename":
                response[field_name] = self.get_kind()
                continue

            if field_name in ["source", "owner"]:
                node_attr_getter = getattr(self, f"get_{field_name}")
                node_attr = await node_attr_getter(session=session)
                if not node_attr:
                    response[field_name] = None
                else:
                    response[field_name] = await node_attr.to_graphql(session=session, fields=fields[field_name])
                continue

            if field_name.startswith("_"):
                field = getattr(self, field_name[1:])
            else:
                field = getattr(self, field_name)

            if isinstance(field, (str, int, bool, dict, list)):
                response[field_name] = field

        return response


class AnyAttribute(BaseAttribute):
    type = Any

    @classmethod
    def validate_format(cls, *args, **kwargs) -> None:
        pass


class String(BaseAttribute):
    type = str


class Integer(BaseAttribute):
    type = int


class Boolean(BaseAttribute):
    type = bool


class ListAttribute(BaseAttribute):
    type = list

    @classmethod
    def serialize(cls, value: Any) -> Any:
        """Serialize the value before storing it in the database."""

        return ujson.dumps(value)

    @classmethod
    def deserialize(cls, value: Any) -> Any:
        """Deserialize the value (potentially) coming from the database."""
        if isinstance(value, (str, bytes)):
            return ujson.loads(value)
        return value
