from __future__ import annotations

from typing import Set, List, Dict, Any, Union, TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import update_relationships_to, add_relationship
from infrahub.exceptions import ValidationError

from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.core.query.attribute import (
    AttributeGetQuery,
    AttributeUpdateValueQuery,
    AttributeCreateQuery,
    AttributeUpdateFlagQuery,
    AttributeUpdateNodePropertyQuery,
)
from infrahub.core.constants import RelationshipStatus

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import AttributeSchema


class BaseAttribute:

    type = None

    _rel_to_node_label: str = "HAS_ATTRIBUTE"
    _rel_to_value_label: str = "HAS_VALUE"

    _node_properties: list[str] = ["source", "owner"]

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
        is_visible: bool = None,
        is_protected: bool = None,
        source: Union[Node, str] = None,
        owner: Union[Node, str] = None,
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

        self.source = source
        self.owner = owner

        self.value = None

        if data is not None and isinstance(data, dict):
            self.value = data.get("value", None)

            fields_to_extract_from_data = ["id", "db_id", "is_visible", "is_protected", "source", "owner"]
            for field_name in fields_to_extract_from_data:
                setattr(self, field_name, data.get(field_name, None))

            if not self.updated_at and "updated_at" in data:
                self.updated_at = Timestamp(data.get("updated_at"))

        elif data is not None:
            self.value = data

        if self.value is not None and not self.validate(self.value):
            raise ValidationError({self.name: f"{self.name} is not of type {self.get_kind()}"})

        # Assign default values
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
    def source(self):
        return self._get_node_property("source")

    @source.setter
    def source(self, value):
        self._set_node_property("source", value)

    @property
    def owner(self):
        return self._get_node_property("owner")

    @owner.setter
    def owner(self, value):
        self._set_node_property("owner", value)

    def _get_node_property(self, name: str) -> Node:
        """Return the node attribute.
        If the node is already present in cache, serve from the cache
        If the node is not present, query it on the fly using the node_id
        """
        if getattr(self, f"_{name}") is None:
            self._retrieve_node_property(name)

        return getattr(self, f"_{name}", None)

    def _set_node_property(self, name: str, value: Union[Node, str]):
        """Set the value of the node_property.
        If the value is a string, we assume it's an ID and we'll save it to query it later (if needed)
        If the value is a Node, we save the node and we extract the ID
        if the value is None, we just initialize the 2 variables."""

        if isinstance(value, str):
            setattr(self, f"{name}_id", value)
            setattr(self, f"_{name}", None)
        elif isinstance(value, dict) and "id" in value:
            setattr(self, f"{name}_id", value["id"])
            setattr(self, f"_{name}", None)
        elif hasattr(value, "_schema"):
            setattr(self, f"_{name}", value)
            setattr(self, f"{name}_id", value.id)
        elif value is None:
            setattr(self, f"_{name}", None)
            setattr(self, f"{name}_id", None)
        else:
            raise ValueError("Unable to process the node property")

    def _retrieve_node_property(self, name: str):
        """Query the node associated with this node_property from the database."""
        from infrahub.core.manager import NodeManager

        node = NodeManager.get_one(getattr(self, f"{name}_id"), branch=self.branch, at=self.at)
        setattr(self, f"_{name}", node)
        if node:
            setattr(self, f"{name}_id", node.id)

    def save(self, at: Timestamp = None):
        """Create or Update the Attribute in the database."""

        save_at = Timestamp(at)

        if self.id:
            return self._update(at=save_at)

        return self._create(at=save_at)

    def delete(self, at: Timestamp = None) -> bool:

        delete_at = Timestamp(at)

        query = AttributeGetQuery(attr=self).execute()
        results = query.get_results()

        if not results:
            return False

        properties_to_delete = []

        # Check all the relationship and update the one that are in the same branch
        rel_ids_to_update = set()
        for result in results:
            properties_to_delete.append((result.get("r2").type, result.get("ap").id))

            add_relationship(
                src_node_id=self.db_id,
                dst_node_id=result.get("ap").id,
                rel_type=result.get("r2").type,
                branch_name=self.branch.name,
                at=delete_at,
                status=RelationshipStatus.DELETED,
            )

            for rel in result.get_rels():
                if rel.get("branch") == self.branch.name:
                    rel_ids_to_update.add(rel.id)

        if rel_ids_to_update:
            update_relationships_to(ids=list(rel_ids_to_update), to=delete_at)

        add_relationship(
            src_node_id=self.node.db_id,
            dst_node_id=self.db_id,
            rel_type="HAS_ATTRIBUTE",
            branch_name=self.branch.name,
            at=delete_at,
            status=RelationshipStatus.DELETED,
        )

        return True

    def _create(self, at: Timestamp = None) -> bool:

        create_at = Timestamp(at)

        query = AttributeCreateQuery(attr=self, branch=self.branch, at=create_at).execute()

        self.id, self.db_id = query.get_new_ids()
        self.at = create_at

        return True

    def _update(self, at: Timestamp = None) -> bool:
        """Update the attribute in the database.

        Get the current value
         - If the value is the same, do nothing
         - If the value is inherited and is different, raise error (for now just ignore)
         - If the value is different, create new node and update relationship

        """

        update_at = Timestamp(at)

        # Validate if the value is still correct, will raise a ValidationError if not
        self.validate(self.value)

        query = NodeListGetAttributeQuery(
            ids=[self.node.id], fields={self.name: True}, branch=self.branch, at=update_at, include_source=True
        ).execute()
        current_attr = query.get_result_by_id_and_name(self.node.id, self.name)

        # ---------- Update the Value ----------
        current_value = current_attr.get("av").get("value")
        if current_value == "NULL":
            current_value = None

        if current_value != self.value:
            # Create the new AttributeValue and update the existing relationship
            AttributeUpdateValueQuery(attr=self, at=update_at).execute()

            # TODO check that everything went well
            rel = current_attr.get("r2")
            if rel.get("branch") == self.branch.name:
                update_relationships_to([rel.id], to=update_at)

        # ---------- Update the Flags ----------
        SUPPORTED_FLAGS = (
            ("is_visible", "isv", "rel_isv"),
            ("is_protected", "isp", "rel_isp"),
        )

        for flag_name, node_name, rel_name in SUPPORTED_FLAGS:
            if current_attr.get(node_name).get("value") != getattr(self, flag_name):
                AttributeUpdateFlagQuery(attr=self, at=update_at, flag_name=flag_name).execute()

                rel = current_attr.get(rel_name)
                if rel.get("branch") == self.branch.name:
                    update_relationships_to([rel.id], to=update_at)

        # ---------- Update the Node Properties ----------
        for prop in self._node_properties:
            if (
                getattr(self, f"{prop}_id")
                and current_attr.get(
                    prop,
                )
                and current_attr.get(prop).id != getattr(self, f"{prop}_id")
            ):
                AttributeUpdateNodePropertyQuery(
                    attr=self, at=update_at, prop_name=prop, prop_id=getattr(self, f"{prop}_id")
                ).execute()

                rel = current_attr.get(f"rel_{prop}")
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
