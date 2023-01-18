from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypeVar, Union
from uuid import UUID

from infrahub.core import get_branch, registry
from infrahub.core.query.node import NodeCreateQuery, NodeDeleteQuery, NodeGetListQuery
from infrahub.core.schema import ATTRIBUTES_MAPPING, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

from ..attribute import BaseAttribute
from ..relationship import RelationshipManager
from ..utils import update_relationships_to
from .base import BaseNode, BaseNodeMeta, BaseNodeOptions

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch
"""
Type of Nodes
 - Core node, wo/ branch : Branch, MergeRequest, Comment
 - Core node, w/ branch : Repository, RFile, GQLQuery, Permission, Account, Groups, Schema
 - Location Node : Location,
 - Select Node : Status, Role, Manufacturer etc ..
 -
"""

SelfNode = TypeVar("SelfNode", bound="Node")


class Node(BaseNode, metaclass=BaseNodeMeta):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        _meta=None,
        default_filter=None,
        **options,
    ):
        if not _meta:
            _meta = BaseNodeOptions(cls)

        _meta.default_filter = default_filter
        super(Node, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    def get_kind(self):
        return self._schema.kind

    def __repr__(self):
        return f"{self.get_kind()}(ID: {str(self.id)})"

    def __init__(
        self,
        schema: NodeSchema,
        branch: Branch,
        at: Timestamp,
    ):

        self._schema: NodeSchema = schema
        self._branch: Branch = branch
        self._at: Timestamp = at

        self._updated_at: Optional[Timestamp] = None
        self.id: str = None
        self.db_id: int = None

        self._source: Node = None
        self._owner: Node = None
        self._is_protected: bool = None

        self._attributes = []
        self._relationships = []

    @classmethod
    async def init(
        cls,
        session: AsyncSession,
        schema: Union[NodeSchema, str],
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> SelfNode:

        attrs = {}

        if isinstance(schema, NodeSchema):
            attrs["schema"] = schema
        elif isinstance(schema, str):

            # TODO need to raise a proper exception for this, right now it will raise a generic ValueError
            attrs["schema"] = await registry.get_schema(session=session, name=schema, branch=branch)
        else:
            raise ValueError(f"Invalid schema provided {schema}")

        if not attrs["schema"].branch:
            attrs["branch"] = None
        else:
            attrs["branch"] = await get_branch(session=session, branch=branch)

        attrs["at"] = Timestamp(at)

        return cls(**attrs)

    async def _process_fields(self, fields: dict, session: AsyncSession):

        errors = []

        if "_source" in fields.keys():
            self._source = fields["_source"]

        # Validate input
        for field_name in fields.keys():
            if field_name not in self._schema.valid_input_names:
                errors.append(ValidationError({field_name: f"{field_name} is not a valid input for {self.get_kind()}"}))

        # If the object is new, we need to ensure that all mandatory attributes and relationships have been provided
        if not self.id:
            for mandatory_attr in self._schema.mandatory_attribute_names:
                if mandatory_attr not in fields.keys():
                    errors.append(
                        ValidationError({mandatory_attr: f"{mandatory_attr} is mandatory for {self.get_kind()}"})
                    )

            for mandatory_rel in self._schema.mandatory_relationship_names:
                if mandatory_rel not in fields.keys():
                    errors.append(
                        ValidationError({mandatory_rel: f"{mandatory_rel} is mandatory for {self.get_kind()}"})
                    )

        if errors:
            raise ValidationError(errors)

        # Assign values
        for attr_schema in self._schema.attributes:

            attr_class = ATTRIBUTES_MAPPING[attr_schema.kind]
            self._attributes.append(attr_schema.name)

            try:
                setattr(
                    self,
                    attr_schema.name,
                    attr_class(
                        data=fields.get(attr_schema.name, None),
                        name=attr_schema.name,
                        schema=attr_schema,
                        branch=self._branch,
                        at=self._at,
                        node=self,
                        source=self._source,
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        for rel_schema in self._schema.relationships:
            self._relationships.append(rel_schema.name)

            try:
                rm = await RelationshipManager.init(
                    session=session,
                    data=fields.get(rel_schema.name, None),
                    schema=rel_schema,
                    branch=self._branch,
                    at=self._at,
                    node=self,
                )

                setattr(
                    self,
                    rel_schema.name,
                    rm,
                )
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

    async def new(self, session: AsyncSession, **kwargs) -> SelfNode:

        await self._process_fields(session=session, fields=kwargs)
        return self

    async def load(
        self,
        session: AsyncSession,
        id: UUID = None,
        db_id: int = None,
        updated_at: Union[Timestamp, str] = None,
        **kwargs,
    ) -> SelfNode:

        self.id = id
        self.db_id = db_id

        if updated_at:
            self._updated_at = Timestamp(updated_at)

        await self._process_fields(session=session, fields=kwargs)
        return self

    async def _create(self, session: AsyncSession, at: Optional[Timestamp] = None):

        create_at = Timestamp(at)

        query = await NodeCreateQuery.init(session=session, node=self, at=create_at)
        await query.execute(session=session)
        self.id, self.db_id = query.get_new_ids()
        self._at = create_at
        self._updated_at = create_at

        # Go over the list of Attribute and create them one by one
        for name in self._attributes:

            attr: BaseAttribute = getattr(self, name)
            # Handle LocalAttribute attributes
            if issubclass(attr.__class__, BaseAttribute):
                await attr.save(at=create_at, session=session)

        # Go over the list of relationships and create them one by one
        for name in self._relationships:

            rel = getattr(self, name)
            await rel.save(at=create_at, session=session)

        return True

    async def _update(
        self,
        session: AsyncSession,
        at: Optional[Timestamp] = None,
    ):
        """Update the node in the database if needed."""

        update_at = Timestamp(at)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr = getattr(self, name)
            await attr.save(at=update_at, session=session)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel = getattr(self, name)
            await rel.save(at=update_at, session=session)

    async def save(
        self,
        session: AsyncSession,
        at: Optional[Timestamp] = None,
    ) -> SelfNode:
        """Create or Update the Node in the database."""

        save_at = Timestamp(at)

        if self.id:
            await self._update(at=save_at, session=session)
            return self

        await self._create(at=save_at, session=session)
        return self

    async def delete(self, session: AsyncSession, at: Optional[Timestamp] = None):
        """Delete the Node in the database."""

        delete_at = Timestamp(at)

        # Ensure the node can be safely deleted first TODO
        #  - Check if there is a relationship pointing to it that is mandatory
        #  - Check if some nodes must be deleted too CASCADE (TODO)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            await attr.delete(at=delete_at, session=session)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel: RelationshipManager = getattr(self, name)
            await rel.delete(at=delete_at, session=session)

        # Need to check if there are some unidirectional relationship as well
        # For example, if we delete a tag, we must check the permissions and update all the relationships pointing at it

        # Update the relationship to the branch itself
        query = await NodeGetListQuery.init(
            session=session, schema=self._schema, filters={"id": self.id}, branch=self._branch, at=delete_at
        )
        await query.execute(session=session)
        result = query.get_result()

        if result.get("br").get("name") == self._branch.name:
            await update_relationships_to([result.get("rb").element_id], to=delete_at, session=session)

        query = await NodeDeleteQuery.init(session=session, node=self, at=delete_at)
        await query.execute(session=session)

    async def to_graphql(self, session: AsyncSession, fields: dict = None) -> dict:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """

        response = {"id": self.id}

        for field_name in fields.keys():

            if field_name in ["id"] or field_name in self._schema.relationship_names:
                continue

            if field_name == "_updated_at":
                if self._updated_at:
                    response[field_name] = await self._updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            field = getattr(self, field_name)

            if not field:
                response[field_name] = None
                continue

            response[field_name] = await field.to_graphql(session=session, fields=fields[field_name])

        return response

    async def from_graphql(self, session: AsyncSession, data: dict) -> bool:
        """Update object from a GraphQL payload."""

        changed = False

        STANDARD_FIELDS = ["value", "is_protected", "is_visible"]
        NODE_FIELDS = ["source", "owner"]

        for key, value in data.items():
            if key in self._attributes and isinstance(value, dict):
                for field_name in value.keys():
                    if field_name in STANDARD_FIELDS:
                        attr = getattr(self, key)
                        if getattr(attr, field_name) != value.get(field_name):
                            setattr(attr, field_name, value.get(field_name))
                            changed = True

                    elif field_name in NODE_FIELDS:
                        attr = getattr(self, key)

                        # Right now we assume that the UUID is provided from GraphQL
                        # so we compare the value with <node>_id
                        if getattr(attr, f"{field_name}_id") != value.get(field_name):
                            setattr(attr, field_name, value.get(field_name))
                            changed = True

            if key in self._relationships:
                rel = getattr(self, key)
                changed = await rel.update(session=session, data=value)

        return changed
