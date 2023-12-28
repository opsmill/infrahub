from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Union

from infrahub_sdk import UUIDT
from infrahub_sdk.utils import is_valid_uuid

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.query.node import (
    NodeCheckIDQuery,
    NodeCreateAllQuery,
    NodeDeleteQuery,
    NodeGetListQuery,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError
from infrahub.types import ATTRIBUTE_TYPES

from ..relationship import RelationshipManager
from ..utils import update_relationships_to
from .base import BaseNode, BaseNodeMeta, BaseNodeOptions

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..attribute import BaseAttribute

# ---------------------------------------------------------------------------------------
# Type of Nodes
#  - Core node, wo/ branch : Branch, MergeRequest, Comment
#  - Core node, w/ branch : Repository, RFile, GQLQuery, Permission, Account, Groups, Schema
#  - Location Node : Location,
#  - Select Node : Status, Role, Manufacturer etc ..
#  -
# ---------------------------------------------------------------------------------------

# pylint: disable=redefined-builtin,too-many-branches


class Node(BaseNode, metaclass=BaseNodeMeta):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        _meta=None,
        default_filter=None,
        **options,
    ):
        if not _meta:
            _meta = BaseNodeOptions(cls)

        _meta.default_filter = default_filter
        super(Node, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    def get_kind(self) -> str:
        """Return the main Kind of the Object."""
        return self._schema.kind

    def get_labels(self) -> List[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""

        if isinstance(self._schema, NodeSchema):
            labels: List[str] = [self.get_kind()] + self._schema.inherit_from
            if self._schema.namespace not in ["Schema", "Internal"] and "CoreGroup" not in self._schema.inherit_from:
                labels.append("CoreNode")
            return labels

        return [self.get_kind()]

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Returns:
            Branch:
        """
        if self._schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self._branch

    def __repr__(self):
        if not self._existing:
            return f"{self.get_kind()}(ID: {str(self.id)})[NEW]"

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
        self._existing: bool = False

        self._updated_at: Optional[Timestamp] = None
        self.id: str = None
        self.db_id: str = None

        self._source: Node = None
        self._owner: Node = None
        self._is_protected: bool = None

        # Lists of attributes and relationships names
        self._attributes: List[str] = []
        self._relationships: List[str] = []

    @classmethod
    async def init(
        cls,
        schema: Union[NodeSchema, str],
        db: InfrahubDatabase,
        branch: Optional[Union[Branch, str]] = None,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> Self:
        attrs = {}

        branch = await registry.get_branch(branch=branch, db=db)

        if isinstance(schema, NodeSchema):
            attrs["schema"] = schema
        elif isinstance(schema, str):
            # TODO need to raise a proper exception for this, right now it will raise a generic ValueError
            attrs["schema"] = registry.schema.get(name=schema, branch=branch)
        else:
            raise ValueError(f"Invalid schema provided {type(schema)}, expected NodeSchema")

        attrs["branch"] = branch
        attrs["at"] = Timestamp(at)

        return cls(**attrs)

    async def _process_fields(self, fields: dict, db: InfrahubDatabase):
        errors = []

        if "_source" in fields.keys():
            self._source = fields["_source"]
        if "_owner" in fields.keys():
            self._owner = fields["_owner"]

        # -------------------------------------------
        # Validate Input
        # -------------------------------------------
        for field_name in fields.keys():
            if field_name not in self._schema.valid_input_names:
                errors.append(ValidationError({field_name: f"{field_name} is not a valid input for {self.get_kind()}"}))

        # If the object is new, we need to ensure that all mandatory attributes and relationships have been provided
        if not self._existing:
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

        # -------------------------------------------
        # Generate Attribute and Relationship and assign them
        # -------------------------------------------
        for attr_schema in self._schema.attributes:
            self._attributes.append(attr_schema.name)

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_attribute_default"
            if hasattr(self, f"generate_{attr_schema.name}"):
                generator_method_name = f"generate_{attr_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    attr_schema.name,
                    await generator_method(
                        db=db,
                        name=attr_schema.name,
                        schema=attr_schema,
                        data=fields.get(attr_schema.name, None),
                    ),
                )
                if not self.id:
                    attribute = getattr(self, attr_schema.name)
                    attribute.validate(value=attribute.value, name=attribute.name, schema=attribute.schema)
            except ValidationError as exc:
                errors.append(exc)

        for rel_schema in self._schema.relationships:
            self._relationships.append(rel_schema.name)

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_relationship_default"
            if hasattr(self, f"generate_{rel_schema.name}"):
                generator_method_name = f"generate_{rel_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    rel_schema.name,
                    await generator_method(
                        db=db, name=rel_schema.name, schema=rel_schema, data=fields.get(rel_schema.name, None)
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

        # Check if any post processor have been defined
        # A processor can be used for example to assigne a default value
        for name in self._attributes + self._relationships:
            if hasattr(self, f"process_{name}"):
                await getattr(self, f"process_{name}")(db=db)

    async def _generate_relationship_default(
        self,
        name: str,  # pylint: disable=unused-argument
        schema: RelationshipSchema,
        data: Any,
        db: InfrahubDatabase,
    ) -> RelationshipManager:
        rm = await RelationshipManager.init(
            db=db,
            data=data,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
        )

        return rm

    async def _generate_attribute_default(
        self,
        name: str,
        schema: AttributeSchema,
        data: Any,
        db: InfrahubDatabase,  # pylint: disable=unused-argument
    ) -> BaseAttribute:
        attr_class = ATTRIBUTE_TYPES[schema.kind].get_infrahub_class()
        attr = attr_class(
            data=data,
            name=name,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
            source=self._source,
            owner=self._owner,
        )
        return attr

    async def process_label(self, db: Optional[InfrahubDatabase] = None):  # pylint: disable=unused-argument
        # If there label and name are both defined for this node
        #  if label is not define, we'll automatically populate it with a human friendy vesion of name
        # pylint: disable=no-member
        if not self.id and hasattr(self, "label") and hasattr(self, "name"):
            if self.label.value is None and self.name.value:
                self.label.value = " ".join([word.title() for word in self.name.value.split("_")])

    async def new(self, db: InfrahubDatabase, id: Optional[str] = None, **kwargs) -> Self:
        if id and not is_valid_uuid(id):
            raise ValidationError({"id": f"{id} is not a valid UUID"})
        if id:
            query = await NodeCheckIDQuery.init(db=db, node_id=id)
            if await query.count(db=db):
                raise ValidationError({"id": f"{id} is already in use"})

        await self._process_fields(db=db, fields=kwargs)

        self.id = id or str(UUIDT())

        return self

    async def load(
        self,
        db: InfrahubDatabase,
        id: Optional[str] = None,
        db_id: Optional[str] = None,
        updated_at: Union[Timestamp, str] = None,
        **kwargs,
    ) -> Self:
        self.id = id
        self.db_id = db_id
        self._existing = True

        if updated_at:
            self._updated_at = Timestamp(updated_at)

        await self._process_fields(db=db, fields=kwargs)
        return self

    async def _create(self, db: InfrahubDatabase, at: Optional[Timestamp] = None):
        create_at = Timestamp(at)

        query = await NodeCreateAllQuery.init(db=db, node=self, at=create_at)
        await query.execute(db=db)

        _, self.db_id = query.get_self_ids()
        self._at = create_at
        self._updated_at = create_at
        self._existing = True

        new_ids = query.get_ids()

        # Go over the list of Attribute and assign the new IDs one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            attr.id, attr.db_id = new_ids[name]
            attr.at = create_at

        # Go over the list of relationships and assign the new IDs one by one
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            for rel in relm._relationships:
                identifier = f"{rel.schema.identifier}::{rel.peer_id}"
                rel.id, rel.db_id = new_ids[identifier]

        return True

    async def _update(
        self,
        db: InfrahubDatabase,
        at: Optional[Timestamp] = None,
    ):
        """Update the node in the database if needed."""

        update_at = Timestamp(at)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            await attr.save(at=update_at, db=db)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel: RelationshipManager = getattr(self, name)
            await rel.save(at=update_at, db=db)

    async def save(
        self,
        db: InfrahubDatabase,
        at: Optional[Timestamp] = None,
    ) -> Self:
        """Create or Update the Node in the database."""

        save_at = Timestamp(at)

        if self._existing:
            await self._update(at=save_at, db=db)
            return self

        await self._create(at=save_at, db=db)
        return self

    async def delete(self, db: InfrahubDatabase, at: Optional[Timestamp] = None):
        """Delete the Node in the database."""

        delete_at = Timestamp(at)

        # Ensure the node can be safely deleted first TODO
        #  - Check if there is a relationship pointing to it that is mandatory
        #  - Check if some nodes must be deleted too CASCADE (TODO)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            await attr.delete(at=delete_at, db=db)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel: RelationshipManager = getattr(self, name)
            await rel.delete(at=delete_at, db=db)

        # Need to check if there are some unidirectional relationship as well
        # For example, if we delete a tag, we must check the permissions and update all the relationships pointing at it
        branch = self.get_branch_based_on_support_type()

        # Update the relationship to the branch itself
        query = await NodeGetListQuery.init(
            db=db, schema=self._schema, filters={"id": self.id}, branch=self._branch, at=delete_at
        )
        await query.execute(db=db)
        result = query.get_result()

        if result.get("rb.branch") == branch.name:
            await update_relationships_to([result.get("rb_id")], to=delete_at, db=db)

        query = await NodeDeleteQuery.init(db=db, node=self, at=delete_at)
        await query.execute(db=db)

    async def to_graphql(
        self, db: InfrahubDatabase, fields: Optional[dict] = None, related_node_ids: Optional[set] = None
    ) -> dict:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """

        response = {"id": self.id, "type": self.get_kind()}

        if related_node_ids is not None:
            related_node_ids.add(self.id)

        FIELD_NAME_TO_EXCLUDE = ["id"] + self._schema.relationship_names

        if fields and isinstance(fields, dict):
            field_names = [field_name for field_name in fields.keys() if field_name not in FIELD_NAME_TO_EXCLUDE]
        else:
            field_names = self._schema.attribute_names + ["__typename", "display_label"]

        for field_name in field_names:
            if field_name == "__typename":
                response[field_name] = self.get_kind()
                continue

            if field_name == "display_label":
                response[field_name] = await self.render_display_label(db=db)
                continue

            if field_name == "_updated_at":
                if self._updated_at:
                    response[field_name] = await self._updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            field = getattr(self, field_name, None)

            if not field:
                response[field_name] = None
                continue

            if fields and isinstance(fields, dict):
                response[field_name] = await field.to_graphql(
                    db=db, fields=fields.get(field_name), related_node_ids=related_node_ids
                )
            else:
                response[field_name] = await field.to_graphql(db=db)

        return response

    async def from_graphql(self, data: dict, db: InfrahubDatabase) -> bool:
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
                rel: RelationshipManager = getattr(self, key)
                changed |= await rel.update(db=db, data=value)

        return changed

    async def render_display_label(self, db: InfrahubDatabase):  # pylint: disable=unused-argument
        if not self._schema.display_labels:
            return repr(self)

        display_elements = []
        for item in self._schema.display_labels:
            item_elements = item.split("__")
            if len(item_elements) != 2:
                raise ValidationError("Display Label can only have one level")

            if item_elements[0] not in self._schema.attribute_names:
                raise ValidationError("Only Attribute can be used in Display Label")

            attr = getattr(self, item_elements[0])
            display_elements.append(str(getattr(attr, item_elements[1])))

        display_label = " ".join(display_elements)
        if display_label.strip() == "":
            return repr(self)
        return display_label.strip()
