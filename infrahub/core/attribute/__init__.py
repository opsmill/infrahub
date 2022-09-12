from __future__ import annotations

from importlib import import_module
from typing import Any

from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to
from infrahub.exceptions import ValidationError

from .query import (
    AttributeDeleteQuery,
    AttributeGetQuery,
    AttributeGetValueQuery,
    LocalAttributeCreateNewValueQuery,
)


class BaseAttribute:

    type = None

    _rel_to_node_label: str = "HAS_ATTRIBUTE"
    _rel_to_value_label: str = "HAS_VALUE"

    query_create_class: str = "LocalAttributeCreateQuery"
    query_attr_value_class: str = "AttributeGetValueQuery"

    def get_kind(self):
        return self.schema.kind

    def __init__(
        self, name, schema, branch, at, node, id=None, db_id=None, data=None, updated_at=None, *args, **kwargs
    ):

        self.id = id
        self.db_id = db_id

        self.updated_at = updated_at
        self.name = name
        self.node = node
        self.schema = schema
        self.branch = branch
        self.at = at

        self.value = None

        if data is not None and isinstance(data, dict):
            self.value = data.get("value", None)

            fields_to_extract_from_data = ["id", "db_id"]
            for field_name in fields_to_extract_from_data:
                if not getattr(self, field_name):
                    setattr(self, field_name, data.get(field_name, None))

            if not self.updated_at and "updated_at" in data:
                self.updated_at = Timestamp(data.get("updated_at"))

        elif data is not None:
            self.value = data

        if self.value is not None and not self.validate(self.value):
            raise ValidationError({self.name: f"{self.name} is not of type {self.get_kind()}"})

        if self.value is None and self.schema.default_value is not None:
            self.value = self.schema.default_value

    @classmethod
    def validate(cls, value):
        return True if isinstance(value, cls.type) else False

    def save(self, at: Timestamp = None):
        """Create or Update the Attribute in the database."""

        save_at = Timestamp(at)

        if self.id:
            return self._update(at=save_at)

        return self._create(at=save_at)

    def delete(self, at: Timestamp = None):

        delete_at = Timestamp(at)

        query = AttributeGetQuery(attr=self).execute()
        result = query.get_result()

        # Check all the relationship and update the one that are in the same branch
        rel_ids_to_update = []
        for rel in result.get_rels():
            if rel.get("branch") == self.branch.name:
                rel_ids_to_update.append(rel.id)

        if rel_ids_to_update:
            update_relationships_to(rel_ids_to_update, to=delete_at)

        AttributeDeleteQuery(attr=self, at=delete_at).execute()

        return True

    def _create(self, at: Timestamp = None):

        create_at = Timestamp(at)

        local_module = import_module("infrahub.core.attribute.query")
        query_create_class = getattr(local_module, self.query_create_class)
        query = query_create_class(attr=self, at=create_at)
        query.execute()

        self.id, self.db_id = query.get_new_ids()
        self.at = create_at

        return True

    def _update(self, at: Timestamp = None):
        """Update the attribute in the database.

        for now we are able to update
        - Value

        Items to consider in the future
        - Owner
        - Visiblity
        - Criticality

        Get the current value
         - If the value is the same, do nothing
         - If the value is inherited and is different, raise error (for now just ignore)
         - If the value is different, create new node and update relationship

        """

        update_at = Timestamp(at)
        # Validate if the value is still correct, will raise a ValidationError if not
        self.validate(self.value)

        query = AttributeGetValueQuery(attr=self).execute()

        if query.get_value() == self.value:
            return False

        # Create the new AttributeValue and update the existing relationship
        query_create = LocalAttributeCreateNewValueQuery(attr=self, at=update_at)
        query_create.execute()

        # TODO check that everything went well
        rel = query.get_relationship()
        if rel.get("branch") == self.branch.name:
            update_relationships_to([rel.id], to=update_at)

        return True

    @classmethod
    def get_query_filter(
        cls,
        name: str,
        filters: dict = None,
        branch=None,
        rels_offset: int = 0,
        include_match: bool = True,
        param_prefix: str = None,
    ):
        """Generate Query String Snippet to filter the right node."""

        query_filters = []
        query_params = {}
        nbr_rels = 0

        param_prefix = param_prefix or f"attr_{name}"

        if not filters:
            return query_filters, query_params, nbr_rels

        for attr_name, value in filters.items():

            query_filter = ""

            # if attr_name not in cls.__fields__.keys():
            #     raise Exception(
            #         f"filter '{attr_name}' is not supported for {cls.__name__}, available option {cls.__fields__.keys()}"
            #     )

            if not isinstance(value, (str, bool, int)):
                raise Exception(f"filter {attr_name}: {value} ({type(value)}) is not supported.")

            # value_filter = f"{value}"
            # if isinstance(value, str):
            #     value_filter = f'"{value}"'

            if include_match:
                query_filter += "MATCH (n)"

            # TODO Validate if filters are valid
            query_filter += "-[r%s:%s]-(i:Attribute { name: $%s_name } )" % (
                rels_offset + 1,
                cls._rel_to_node_label,
                param_prefix,
            )
            query_params[f"{param_prefix}_name"] = name

            query_filter += "-[r%s:HAS_VALUE]-(av { value: $%s_value })" % (rels_offset + 2, param_prefix)
            query_params[f"{param_prefix}_value"] = value

            query_filters.append(query_filter)

        nbr_rels = 2

        return query_filters, query_params, nbr_rels

    def to_graphql(self, fields=None):
        """Generate GraphQL Payload for this attribute."""

        response = {"id": self.id, "_source": None, "_permission": None}

        # if "_source" in fields and self.source:
        #     response["_source"] = self.source.to_graphql(fields=fields["_source"])

        # if "_permission" in fields and self.permission:
        #     response["_permission"] = self.permission.name.lower()

        for field_name in fields.keys():

            if field_name in ["_source", "_permission"]:
                continue

            if field_name == "_updated_at":
                if self.updated_at:
                    response[field_name] = self.updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            if field_name.startswith("_"):
                field = getattr(self, field_name[1:])
            else:
                field = getattr(self, field_name)

            if isinstance(field, (str, int, bool, dict)):
                response[field_name] = field

        return response


class Any(BaseAttribute):

    type = Any

    @classmethod
    def validate(cls, value):
        return True


class String(BaseAttribute):

    type = str


class Integer(BaseAttribute):

    type = int


class Boolean(BaseAttribute):

    type = bool
