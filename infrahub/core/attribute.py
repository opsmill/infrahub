from __future__ import annotations

from typing import Set, List, Dict, Any, Union, TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to
from infrahub.exceptions import ValidationError

from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.query.attribute import (
    AttributeDeleteQuery,
    AttributeGetQuery,
    AttributeGetValueQuery,
    AttributeCreateNewValueQuery,
    AttributeCreateQuery,
    AttributeUpdateFlagsQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import AttributeSchema


class BaseAttribute:

    type = None

    _rel_to_node_label: str = "HAS_ATTRIBUTE"
    _rel_to_value_label: str = "HAS_VALUE"

    def get_kind(self) -> str:
        return self.schema.kind

    def __init__(
        self,
        name: str,
        schema: AttributeSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        id: str = None,
        db_id: int = None,
        data: Union[dict, str] = None,
        updated_at: Union[Timestamp, str] = None,
        source: Node = None,
        source_id: str = None,
        owner: Node = None,
        owner_id: str = None,
        is_visible: bool = None,
        is_protected: bool = None,
        *args,
        **kwargs,
    ):

        self.id = id
        self.db_id = db_id

        self.updated_at = updated_at
        self.name = name
        self.node = node
        self.schema = schema
        self.branch = branch
        self.at = at

        self.is_visible = is_visible
        self.is_protected = is_protected

        # Source and Owner
        self._source = source
        self.source_id = source_id

        if not self.source_id and self._source:
            self.source_id = self._source.id

        self._owner = owner
        self.owner_id = owner_id

        if not self.owner_id and self._owner:
            self.owner_id = self._owner.id

        self.value = None

        if data is not None and isinstance(data, dict):
            self.value = data.get("value", None)

            fields_to_extract_from_data = ["id", "db_id", "is_visible", "is_protected"]
            for field_name in fields_to_extract_from_data:
                if not getattr(self, field_name):
                    setattr(self, field_name, data.get(field_name, None))

            # TODO will need to revisit that before commit
            if "source" in data:
                if isinstance(data["source"], str):
                    self.source_id = data["source"]
                    self._source = None
                elif isinstance(data["source"], dict) and "id" in data["source"]:
                    self.source_id = data["source"]["id"]
                    self._source = None
                else:
                    raise ValidationError({self.name: f"Unable to process 'source' : '{data['source']}'"})

            # TODO will need to revisit that too before commit
            #  .. or at least remove the code duplicate with the previous section
            if "owner" in data:
                if isinstance(data["owner"], str):
                    self.owner_id = data["owner"]
                    self._owner = None
                elif isinstance(data["owner"], dict) and "id" in data["owner"]:
                    self.owner_id = data["owner"]["id"]
                    self._owner = None
                else:
                    raise ValidationError({self.name: f"Unable to process 'owner' : '{data['owner']}'"})

            if not self.updated_at and "updated_at" in data:
                self.updated_at = Timestamp(data.get("updated_at"))

        elif data is not None:
            self.value = data

        if self.value is not None and not self.validate(self.value):
            raise ValidationError({self.name: f"{self.name} is not of type {self.get_kind()}"})

        if self.value is None and self.schema.default_value is not None:
            self.value = self.schema.default_value

        if self.is_protected is None:
            self.is_protected = False

        if self.is_visible is None:
            self.is_visible = True

    @classmethod
    def validate(cls, value) -> bool:
        return True if isinstance(value, cls.type) else False

    @property
    def source(self) -> Node:
        """Return the Source of the attribute."""
        if self._source is None:
            self._get_source()

        if self._source and not self.source_id:
            self.source_id = self._source.id

        return self._source if self._source else None

    def _get_source(self):
        from infrahub.core.manager import NodeManager

        self._source = NodeManager.get_one(self.source_id, branch=self.branch, at=self.at)
        self.source_id = self._source.id

    @property
    def owner(self) -> Node:
        """Return the Owner of the attribute."""
        if self._owner is None:
            self._get_owner()

        if self._owner and not self.owner_id:
            self.owner_id = self._owner.id

        return self._owner if self._owner else None

    def _get_owner(self):
        from infrahub.core.manager import NodeManager

        self._owner = NodeManager.get_one(self.owner_id, branch=self.branch, at=self.at)
        self.owner_id = self._owner.id

    def save(self, at: Timestamp = None):
        """Create or Update the Attribute in the database."""

        save_at = Timestamp(at)

        if self.id:
            return self._update(at=save_at)

        return self._create(at=save_at)

    def delete(self, at: Timestamp = None) -> bool:

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

    def _create(self, at: Timestamp = None) -> bool:

        create_at = Timestamp(at)

        query = AttributeCreateQuery(attr=self, branch=self.branch, at=create_at).execute()

        self.id, self.db_id = query.get_new_ids()
        self.at = create_at

        return True

    def _update(self, at: Timestamp = None) -> bool:
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

        # query = AttributeGetValueQuery(attr=self).execute()
        query = NodeListGetAttributeQuery(
            ids=[self.node.id], fields={self.name: True}, branch=self.branch, at=update_at
        ).execute()
        current_attr = query.get_result_by_id_and_name(self.node.id, self.name)

        if current_attr.get("av").get("value") != self.value:
            # Create the new AttributeValue and update the existing relationship
            query_create = AttributeCreateNewValueQuery(attr=self, at=update_at).execute()

            # TODO check that everything went well
            rel = current_attr.get("r2")
            if rel.get("branch") == self.branch.name:
                update_relationships_to([rel.id], to=update_at)

        SUPPORTED_FLAGS = (
            ("is_visible", "isv", "r4"),
            ("is_protected", "isp", "r5"),
        )

        for flag_name, node_name, rel_name in SUPPORTED_FLAGS:
            if current_attr.get(node_name).get("value") != getattr(self, flag_name):
                query_create = AttributeUpdateFlagsQuery(attr=self, at=update_at, flag_name=flag_name).execute()

                rel = current_attr.get(rel_name)
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
    ) -> Set[List[str], Dict, int]:
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

    def to_graphql(self, fields: dict = None) -> dict:
        """Generate GraphQL Payload for this attribute."""

        response = {"id": self.id}

        for field_name in fields.keys():

            if field_name == "updated_at":
                if self.updated_at:
                    response[field_name] = self.updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            if field_name in ["source", "owner"]:
                response[field_name] = getattr(self, field_name).to_graphql(fields=fields[field_name])
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
