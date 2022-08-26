from __future__ import annotations

from infrahub.core import get_branch, registry
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

from ..attribute import Any, BaseAttribute, Boolean, Integer, String
from ..relationship import RelationshipManager
from ..utils import update_relationships_to
from .base import BaseNode, BaseNodeMeta, BaseNodeOptions
from .query import NodeCreateQuery, NodeDeleteQuery, NodeGetListQuery

"""
Type of Nodes
 - Core node, wo/ branch : Branch, MergeRequest, Comment
 - Core node, w/ branch : Repository, RFile, GQLQuery, Permission, Account, Groups, Schema
 - Location Node : Location,
 - Select Node : Status, Role, Manufacturer etc ..
 -
"""

# TODO Move this mapping into the registry with auto-registration
ATTRIBUTES_MAPPING = {
    "Any": Any,
    "String": String,
    "Integer": Integer,
    "Boolean": Boolean,
}


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

    def __init__(self, schema: NodeSchema, branch=None, at=None):

        if isinstance(schema, NodeSchema):
            self._schema = schema
        elif isinstance(schema, str):
            # TODO need to raise a proper exception for this, right now it will raise a generic ValueError
            self._schema = registry.get_schema(schema, branch=branch)
        else:
            raise ValueError(f"Invalid schema provided {schema}")

        self._branch = get_branch(branch) if self._schema.branch else None
        self._at = Timestamp(at)

        self.id = None
        self.db_id = None

        self._attributes = []
        self._relationships = []

    def _process_fields(self, fields):

        errors = []
        # Validate input
        for field_name in fields.keys():
            if field_name not in self._schema.valid_input_names:
                errors.append(ValidationError({field_name: f"{field_name} is not a valid input for {self.get_kind()}"}))

        # Check if all mandatory attributes have been provided
        for mandatory_attr in self._schema.mandatory_attribute_names:
            if mandatory_attr not in fields.keys():
                errors.append(ValidationError({mandatory_attr: f"{mandatory_attr} is mandatory for {self.get_kind()}"}))

        # If the object is new, we need to ensure that all mandatory relationships have been provided too
        if not self.id:
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
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        for rel_schema in self._schema.relationships:
            self._relationships.append(rel_schema.name)

            try:
                setattr(
                    self,
                    rel_schema.name,
                    RelationshipManager(
                        data=fields.get(rel_schema.name, None),
                        name=rel_schema.name,
                        schema=rel_schema,
                        branch=self._branch,
                        at=self._at,
                        node=self,
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

    def new(self, **kwargs):

        self._process_fields(kwargs)
        return self

    def load(self, id: str = None, db_id: int = None, **kwargs):

        self.id = id
        self.db_id = db_id
        self._process_fields(kwargs)
        return self

    def _create(self, at: Timestamp = None):

        create_at = Timestamp(at)

        query = NodeCreateQuery(node=self, at=create_at)
        query.execute()
        self.id, self.db_id = query.get_new_ids()
        self.at = create_at

        # Go over the list of Attribute and create them one by one
        for name in self._attributes:

            attr = getattr(self, name)
            # Handle LocalAttribute attributes
            if issubclass(attr.__class__, BaseAttribute):
                attr.save(at=create_at)

        # Go over the list of relationships and create them one by one
        for name in self._relationships:

            rel = getattr(self, name)
            rel.save(at=create_at)

        return True

    def _update(self, at: Timestamp = None):
        """Update the node in the database if needed."""

        update_at = Timestamp(at)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr = getattr(self, name)
            attr.save(at=update_at)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            attr = getattr(self, name)
            attr.save(at=update_at)

    def save(self, at: Timestamp = None):
        """Create or Update the Node in the database."""

        save_at = Timestamp(at)

        if self.id:
            self._update(at=save_at)
            return self

        self._create(at=save_at)
        return self

    def delete(self, at: Timestamp = None):
        """Delete the Node in the database."""

        delete_at = Timestamp(at)

        # Ensure the node can be safely deleted first TODO
        #  - Check if there is a relationship pointing to it that is mandatory
        #  - Check if some nodes must be deleted too CASCADE (TODO)

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr = getattr(self, name)
            attr.delete(at=delete_at)

        # Go over the list of relationships and update them one by one
        for name in self._relationships:
            rel = getattr(self, name)
            rel.delete(at=delete_at)

        # Need to check if there are some unidirectional relationship as well
        # For example, if we delete a tag, we must check the permissions and update all the relationships pointing at it

        # Update the relationship to the branch itself
        query = NodeGetListQuery(
            schema=self._schema, filters={"id": self.id}, branch=self._branch, at=delete_at
        ).execute()
        result = query.get_result()

        if result.get("br").get("name") == self._branch.name:
            update_relationships_to([result.get("rb").id], to=delete_at)

        delete_query = NodeDeleteQuery(node=self, at=delete_at).execute()

    def to_graphql(self, fields: dict = None) -> dict:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """

        response = {"id": self.id}

        for field_name in fields.keys():

            if field_name in ["id"] or field_name in self._schema.relationship_names:
                continue

            field = getattr(self, field_name)

            if not field:
                response[field_name] = None
                continue

            response[field_name] = field.to_graphql(fields=fields[field_name])

        return response

    def from_graphql(self, data: dict) -> bool:
        """Update object from a GraphQL payload."""

        changed = False

        for key, value in data.items():
            # For now, we only extract the value of the local attributes.
            if key in self._attributes and isinstance(value, dict) and "value" in value:
                attr = getattr(self, key)
                if attr.value != value.get("value"):
                    attr.value = value.get("value")
                    changed = True

            if key in self._relationships:
                rel = getattr(self, key)
                changed = rel.update(value)

        return changed
