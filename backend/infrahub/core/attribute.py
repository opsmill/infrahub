from __future__ import annotations

import ipaddress
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, Union

import ujson
from infrahub_sdk import UUIDT
from infrahub_sdk.utils import is_valid_url
from pydantic.v1 import BaseModel, Field

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import NULL_VALUE, AttributeDBNodeType, BranchSupportType, RelationshipStatus
from infrahub.core.property import (
    FlagPropertyMixin,
    NodePropertyData,
    NodePropertyMixin,
    ValuePropertyData,
)
from infrahub.core.query.attribute import (
    AttributeGetQuery,
    AttributeUpdateFlagQuery,
    AttributeUpdateNodePropertyQuery,
    AttributeUpdateValueQuery,
)
from infrahub.core.query.node import AttributeFromDB, NodeListGetAttributeQuery
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import add_relationship, update_relationships_to
from infrahub.exceptions import ValidationError
from infrahub.helpers import hash_password

from .constants.relationship_label import RELATIONSHIP_TO_NODE_LABEL, RELATIONSHIP_TO_VALUE_LABEL

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin,c-extension-no-member


class AttributeCreateData(BaseModel):
    uuid: str
    name: str
    type: str
    branch: str
    branch_level: int
    branch_support: str
    status: str
    content: Dict[str, Any]
    is_default: bool
    is_protected: bool
    is_visible: bool
    source_prop: List[ValuePropertyData] = Field(default_factory=list)
    owner_prop: List[NodePropertyData] = Field(default_factory=list)
    node_type: AttributeDBNodeType = AttributeDBNodeType.DEFAULT


class BaseAttribute(FlagPropertyMixin, NodePropertyMixin):
    type: Optional[Union[Type, Tuple[Type]]] = None

    _rel_to_node_label: str = RELATIONSHIP_TO_NODE_LABEL
    _rel_to_value_label: str = RELATIONSHIP_TO_VALUE_LABEL

    def __init__(
        self,
        name: str,
        schema: AttributeSchema,
        branch: Branch,
        at: Timestamp,
        node: Node,
        id: Optional[str] = None,
        db_id: Optional[str] = None,
        data: Optional[Union[dict, str, AttributeFromDB]] = None,
        updated_at: Optional[Union[Timestamp, str]] = None,
        is_default: bool = False,
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
        self.is_default = is_default

        self._init_node_property_mixin(kwargs)
        self._init_flag_property_mixin(kwargs)

        self.value = None

        if isinstance(data, AttributeFromDB):
            self.load_from_db(data=data)

        elif isinstance(data, dict):
            self.value = data.get("value")

            if "is_default" in data:
                self.is_default = data.get("is_default")

            fields_to_extract_from_data = ["id"] + self._flag_properties + self._node_properties
            for field_name in fields_to_extract_from_data:
                setattr(self, field_name, data.get(field_name, None))

            if not self.updated_at and "updated_at" in data:
                self.updated_at = Timestamp(data.get("updated_at"))
        else:
            self.value = data

        # Assign default values
        if self.value is None and self.schema.default_value is not None:
            self.value = self.schema.default_value
            self.is_default = True

        if self.value is not None:
            self.validate(value=self.value, name=self.name, schema=self.schema)

        if self.is_enum and self.value:
            self.value = self.schema.convert_value_to_enum(self.value)

        if self.is_protected is None:
            self.is_protected = False

        if self.is_visible is None:
            self.is_visible = True

    @property
    def is_enum(self) -> bool:
        return bool(self.schema.enum)

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Returns:
            Branch:
        """
        if self.schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self.branch

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry.attribute[cls.__name__] = cls

    def get_kind(self) -> str:
        return self.schema.kind

    def get_value(self) -> Any:
        if isinstance(self.value, Enum):
            return self.value.value
        return self.value

    def set_default_value(self) -> None:
        self.value = self.schema.default_value
        if self.is_enum and self.value:
            self.value = self.schema.convert_value_to_enum(self.value)

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
        value_to_check = value
        if schema.enum and isinstance(value, Enum):
            value_to_check = value.value
        if not isinstance(value_to_check, cls.type):  # pylint: disable=isinstance-second-argument-not-valid-type
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
                raise ValidationError({name: f"{value} must be conform with the regex: {schema.regex!r}"})

        if schema.min_length:
            if len(value) < schema.min_length:
                raise ValidationError({name: f"{value} must have a minimum length of {schema.min_length!r}"})

        if schema.max_length:
            if len(value) > schema.max_length:
                raise ValidationError({name: f"{value} must have a maximum length of {schema.max_length!r}"})

        if schema.enum:
            try:
                schema.convert_value_to_enum(value)
            except ValueError as exc:
                raise ValidationError({name: f"{value} must be one of {schema.enum!r}"}) from exc

    def to_db(self) -> Dict[str, Any]:
        """Return the properties of the AttributeValue node in Dict format."""
        data: Dict[str, Any] = {"is_default": self.is_default}
        if self.value is None:
            data["value"] = NULL_VALUE
        else:
            data["value"] = self.serialize_value()

        return data

    def load_from_db(self, data: AttributeFromDB) -> None:
        self.value = self.value_from_db(data=data)
        self.is_default = data.is_default

        self.id = data.attr_uuid
        self.db_id = data.attr_id

        for prop_name in self._flag_properties:
            if prop_name in data.flag_properties:
                setattr(self, prop_name, data.flag_properties[prop_name])

        for prop_name in self._node_properties:
            if prop_name in data.node_properties:
                setattr(self, prop_name, data.node_properties[prop_name].uuid)

        if not self.updated_at and data.updated_at:
            self.updated_at = Timestamp(data.updated_at)

    def value_from_db(self, data: AttributeFromDB) -> Any:
        if data.value == NULL_VALUE:
            return None
        return self.deserialize_value(data=data)

    def serialize_value(self) -> Any:
        """Serialize the value before storing it in the database."""
        if isinstance(self.value, Enum):
            return self.value.value
        return self.value

    def deserialize_value(self, data: AttributeFromDB) -> Any:
        """Deserialize the value coming from the database."""
        return data.value

    async def save(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> bool:
        """Create or Update the Attribute in the database."""

        save_at = Timestamp(at)

        if not self.id:
            return False

        return await self._update(at=save_at, db=db)

    async def delete(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> bool:
        if not self.db_id:
            return False

        delete_at = Timestamp(at)

        query = await AttributeGetQuery.init(db=db, attr=self)
        await query.execute(db=db)
        results = query.get_results()

        if not results:
            return False

        properties_to_delete = []
        branch = self.get_branch_based_on_support_type()

        # Check all the relationship and update the one that are in the same branch
        rel_ids_to_update = set()
        for result in results:
            properties_to_delete.append((result.get_rel("r2").type, result.get_node("ap").element_id))

            await add_relationship(
                src_node_id=self.db_id,
                dst_node_id=result.get_node("ap").element_id,
                rel_type=result.get_rel("r2").type,
                branch_name=branch.name,
                branch_level=branch.hierarchy_level,
                at=delete_at,
                status=RelationshipStatus.DELETED,
                db=db,
            )

            for rel in result.get_rels():
                if rel.get("branch") == branch.name:
                    rel_ids_to_update.add(rel.element_id)

        if rel_ids_to_update:
            await update_relationships_to(ids=list(rel_ids_to_update), to=delete_at, db=db)

        await add_relationship(
            src_node_id=self.node.db_id,
            dst_node_id=self.db_id,
            rel_type="HAS_ATTRIBUTE",
            branch_name=branch.name,
            branch_level=branch.hierarchy_level,
            at=delete_at,
            status=RelationshipStatus.DELETED,
            db=db,
        )

        return True

    async def _update(self, db: InfrahubDatabase, at: Optional[Timestamp] = None) -> bool:
        """Update the attribute in the database.

        Get the current value
         - If the value is the same, do nothing
         - If the value is inherited and is different, raise error (for now just ignore)
         - If the value is different, create new node and update relationship

        """

        update_at = Timestamp(at)

        # Validate if the value is still correct, will raise a ValidationError if not
        self.validate(value=self.value, name=self.name, schema=self.schema)

        # Check if the current value is still the default one
        if (
            self.is_default
            and (self.schema.default_value is not None and self.schema.default_value != self.value)
            or (self.schema.default_value is None and self.value is not None)
        ):
            self.is_default = False

        query = await NodeListGetAttributeQuery.init(
            db=db,
            ids=[self.node.id],
            fields={self.name: True},
            branch=self.branch,
            at=update_at,
            include_source=True,
            include_owner=True,
        )
        await query.execute(db=db)
        current_attr_data, current_attr_result = query.get_result_by_id_and_name(self.node.id, self.name)

        branch = self.get_branch_based_on_support_type()

        # ---------- Update the Value ----------
        if current_attr_data.content != self.to_db():
            # Create the new AttributeValue and update the existing relationship
            query = await AttributeUpdateValueQuery.init(db=db, attr=self, at=update_at)
            await query.execute(db=db)

            # TODO check that everything went well
            rel = current_attr_result.get_rel("r2")
            if rel.get("branch") == branch.name:
                await update_relationships_to([rel.element_id], to=update_at, db=db)

        # ---------- Update the Flags ----------
        SUPPORTED_FLAGS = (
            ("is_visible", "isv", "rel_isv"),
            ("is_protected", "isp", "rel_isp"),
        )

        for flag_name, _, rel_name in SUPPORTED_FLAGS:
            if current_attr_data.flag_properties[flag_name] != getattr(self, flag_name):
                query = await AttributeUpdateFlagQuery.init(db=db, attr=self, at=update_at, flag_name=flag_name)
                await query.execute(db=db)

                rel = current_attr_result.get(rel_name)
                if rel.get("branch") == branch.name:
                    await update_relationships_to([rel.element_id], to=update_at, db=db)

        # ---------- Update the Node Properties ----------
        for prop_name in self._node_properties:
            if getattr(self, f"{prop_name}_id") and not (
                prop_name in current_attr_data.node_properties
                and current_attr_data.node_properties[prop_name].uuid == getattr(self, f"{prop_name}_id")
            ):
                query = await AttributeUpdateNodePropertyQuery.init(
                    db=db, attr=self, at=update_at, prop_name=prop_name, prop_id=getattr(self, f"{prop_name}_id")
                )
                await query.execute(db=db)

                rel = current_attr_result.get(f"rel_{prop_name}")
                if rel and rel.get("branch") == branch.name:
                    await update_relationships_to([rel.element_id], to=update_at, db=db)

        return True

    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: Optional[dict] = None,
        related_node_ids: Optional[set] = None,
        filter_sensitive: bool = False,
    ) -> dict:
        """Generate GraphQL Payload for this attribute."""
        # pylint: disable=too-many-branches

        response: dict[str, Any] = {
            "id": self.id,
        }

        if fields and isinstance(fields, dict):
            field_names = fields.keys()
        else:
            # REMOVED updated_at for now, need to investigate further how it's being used today
            field_names = ["__typename", "value"] + self._node_properties + self._flag_properties

        for field_name in field_names:
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
                node_attr = await node_attr_getter(db=db)
                if not node_attr:
                    response[field_name] = None
                elif fields and isinstance(fields, dict):
                    response[field_name] = await node_attr.to_graphql(
                        db=db, fields=fields[field_name], related_node_ids=related_node_ids
                    )
                else:
                    response[field_name] = await node_attr.to_graphql(
                        db=db,
                        fields={"id": None, "display_label": None, "__typename": None},
                        related_node_ids=related_node_ids,
                    )
                continue

            if field_name.startswith("_"):
                field = getattr(self, field_name[1:])
            else:
                field = getattr(self, field_name)

            if field_name == "value" and isinstance(field, Enum):
                if config.SETTINGS.experimental_features.graphql_enums:
                    field = field.name
                else:
                    field = field.value
            if isinstance(field, str):
                response[field_name] = self._filter_sensitive(value=field, filter_sensitive=filter_sensitive)
            elif isinstance(field, (int, bool, dict, list)):
                response[field_name] = field

        return response

    def _filter_sensitive(self, value: str, filter_sensitive: bool) -> str:
        if filter_sensitive and self.schema.kind in ["HashedPassword", "Password"]:
            return "***"

        return value

    async def from_graphql(self, data: dict) -> bool:
        """Update attr from GraphQL payload"""

        changed = False

        if "value" in data:
            if self.is_enum:
                value_to_set = self.schema.convert_value_to_enum(data["value"])
            else:
                value_to_set = data["value"]
            if value_to_set != self.value:
                self.value = value_to_set
                changed = True

        if "is_default" in data and not self.is_default:
            self.is_default = True
            changed = True

            if "value" not in data:
                self.set_default_value()

        if "is_protected" in data and data["is_protected"] != self.is_protected:
            self.is_protected = data["is_protected"]
            changed = True
        if "is_visible" in data and data["is_visible"] != self.is_visible:
            self.is_visible = data["is_visible"]
            changed = True

        if "source" in data and data["source"] != self.source_id:
            self.source = data["source"]
            changed = True
        if "owner" in data and data["owner"] != self.owner_id:
            self.owner = data["owner"]
            changed = True

        return changed

    def get_db_node_type(self):
        return AttributeDBNodeType.DEFAULT

    def get_create_data(self) -> AttributeCreateData:
        # pylint: disable=no-member
        branch = self.get_branch_based_on_support_type()
        data = AttributeCreateData(
            node_type=self.get_db_node_type(),
            uuid=str(UUIDT()),
            name=self.name,
            type=self.get_kind(),
            branch=branch.name,
            status="active",
            branch_level=self.branch.hierarchy_level,
            branch_support=self.schema.branch.value,
            content=self.to_db(),
            is_default=self.is_default,
            is_protected=self.is_protected,
            is_visible=self.is_visible,
        )
        if self.source_id:
            data.source_prop.append(NodePropertyData(name="source", peer_id=self.source_id))

        if self.owner_id:
            data.owner_prop.append(NodePropertyData(name="owner", peer_id=self.owner_id))

        return data


class AnyAttribute(BaseAttribute):
    type = Any

    @classmethod
    def validate_format(cls, value: Any, name: str, schema: AttributeSchema) -> None:
        pass


class String(BaseAttribute):
    type = str


class HashedPassword(BaseAttribute):
    type = str

    def serialize_value(self) -> str:
        """Serialize the value before storing it in the database."""
        return hash_password(str(self.value))


class Integer(BaseAttribute):
    type = int


class Boolean(BaseAttribute):
    type = bool


class Dropdown(BaseAttribute):
    type = str

    @property
    def color(self) -> str:
        """Return the color for the current value"""
        if self.schema.choices:
            selected = [choice for choice in self.schema.choices if choice.name == self.value]
            if selected and selected[0].color:
                return selected[0].color

        return ""

    @property
    def description(self) -> str:
        """Return the description for the current value"""
        if self.schema.choices:
            selected = [choice for choice in self.schema.choices if choice.name == self.value]
            if selected and selected[0].description:
                return selected[0].description

        return ""

    @property
    def label(self) -> str:
        """Return the label for the current value"""
        if self.schema.choices:
            selected = [choice for choice in self.schema.choices if choice.name == self.value]
            if selected and selected[0].label:
                return selected[0].label

        return ""

    @classmethod
    def validate_content(cls, value: Any, name: str, schema: AttributeSchema) -> None:
        """Validate the content of the dropdown."""
        super().validate_content(value=value, name=name, schema=schema)
        values = [choice.name for choice in schema.choices]
        if value not in values:
            raise ValidationError({name: f"{value} must be one of {', '.join(sorted(values))!r}"})


class URL(BaseAttribute):
    type = str

    @classmethod
    def validate_format(cls, value: Any, name: str, schema: AttributeSchema) -> None:
        super().validate_format(value=value, name=name, schema=schema)

        if not is_valid_url(value):
            raise ValidationError({name: f"{value} is not a valid {schema.kind}"})


class IPNetwork(BaseAttribute):
    type = str

    @property
    def obj(self) -> Union[ipaddress.IPv4Network, ipaddress.IPv6Network]:
        """Return an ipaddress interface object."""
        if not self.value:
            raise ValueError("value for IPNetwork must be defined")
        return ipaddress.ip_network(str(self.value))

    @property
    def broadcast_address(self) -> Optional[str]:
        """Return the broadcast address of the ip network."""
        if not self.value:
            return None
        return str(self.obj.broadcast_address)

    @property
    def hostmask(self) -> Optional[str]:
        """Return the hostmask of the ip network."""
        if not self.value:
            return None
        return str(self.obj.hostmask)

    @property
    def netmask(self) -> Optional[str]:
        """Return the netmask of the ip network."""
        if not self.value:
            return None
        return str(self.obj.netmask)

    @property
    def network_address(self) -> Optional[str]:
        """Return the netmask of the ip network."""
        if not self.value:
            return None
        return str(self.obj.network_address)

    @property
    def network_address_integer(self) -> int:
        """Return the network address of the ip network in integer format."""
        return int(self.obj.network_address)

    @property
    def network_address_binary(self) -> str:
        """Return the network address of the ip network in binary format."""
        binary_value = bin(self.network_address_integer)[2:]
        return binary_value.zfill(self.obj.max_prefixlen)

    @property
    def prefixlen(self) -> Optional[int]:
        """Return the prefix length the ip network."""
        if not self.value:
            return None
        return ipaddress.ip_network(str(self.value)).prefixlen

    @property
    def num_addresses(self) -> Optional[int]:
        """Return the number of possible addresses in the ip network."""
        if not self.value:
            return None
        return ipaddress.ip_network(str(self.value)).num_addresses

    @property
    def version(self) -> Optional[int]:
        """Return the IP version of the ip network."""
        if not self.value:
            return None
        return ipaddress.ip_network(str(self.value)).version

    @property
    def with_hostmask(self) -> Optional[str]:
        """Return the network ip and the associated hostmask of the ip network."""
        if not self.value:
            return None
        return ipaddress.ip_network(str(self.value)).with_hostmask

    @property
    def with_netmask(self) -> Optional[str]:
        """Return the network ip and the associated netmask of the ip network."""
        if not self.value:
            return None
        return ipaddress.ip_network(str(self.value)).with_netmask

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
        super().validate_format(value=value, name=name, schema=schema)

        try:
            ipaddress.ip_network(value)
        except ValueError as exc:
            raise ValidationError({name: f"{value} is not a valid {schema.kind}"}) from exc

    def serialize_value(self) -> str:
        """Serialize the value before storing it in the database."""

        return ipaddress.ip_network(str(self.value)).with_prefixlen

    def get_db_node_type(self):
        if self.value is not None:
            return AttributeDBNodeType.IPNETWORK
        return AttributeDBNodeType.DEFAULT

    def to_db(self) -> Dict[str, Any]:
        data = super().to_db()

        if self.value is not None:
            data["version"] = self.version
            data["binary_address"] = self.network_address_binary
            data["prefixlen"] = self.prefixlen
            # data["num_addresses"] = self.num_addresses

        return data


class IPHost(BaseAttribute):
    type = str

    @property
    def obj(self) -> Union[ipaddress.IPv4Interface, ipaddress.IPv6Interface]:
        """Return the ip adress without a prefix or subnet mask."""
        if not self.value:
            raise ValueError("value for IPHost must be defined")
        return ipaddress.ip_interface(str(self.value))

    @property
    def ip(self) -> Optional[str]:
        """Return the ip adress without a prefix or subnet mask."""
        if not self.value:
            return None
        return str(self.obj.ip)

    @property
    def hostmask(self) -> Optional[str]:
        """Return the hostmask of the ip address."""
        if not self.value:
            return None
        return str(self.obj.hostmask)

    @property
    def netmask(self) -> Optional[str]:
        """Return the netmask of the ip address."""
        if not self.value:
            return None
        return str(self.obj.netmask)

    @property
    def network(self) -> Optional[str]:
        """Return the network encapsuling the ip address."""
        if not self.value:
            return None
        return str(self.obj.network)

    @property
    def prefixlen(self) -> Optional[int]:
        """Return the prefix length of the ip address."""
        if not self.value:
            return None
        return self.obj.network.prefixlen

    @property
    def version(self) -> Optional[int]:
        """Return the IP version of the ip address."""
        if not self.value:
            return None
        return self.obj.version

    @property
    def with_hostmask(self) -> Optional[str]:
        """Return the ip address and the associated hostmask of the ip address."""
        if not self.value:
            return None
        return self.obj.with_hostmask

    @property
    def with_netmask(self) -> Optional[str]:
        """Return the ip address and the associated netmask of the ip address."""
        if not self.value:
            return None
        return self.obj.with_netmask

    @property
    def ip_integer(self) -> int:
        """Return the ip address in binary format."""
        return int(self.obj)

    @property
    def ip_binary(self) -> str:
        """Return the ip address in binary format."""
        binary_ip = bin(self.ip_integer)[2:]
        return binary_ip.zfill(self.obj.max_prefixlen)

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
        super().validate_format(value=value, name=name, schema=schema)

        try:
            ipaddress.ip_interface(value)
        except ValueError as exc:
            raise ValidationError({name: f"{value} is not a valid {schema.kind}"}) from exc

    def serialize_value(self) -> str:
        """Serialize the value before storing it in the database."""

        return ipaddress.ip_interface(str(self.value)).with_prefixlen

    def get_db_node_type(self):
        if self.value is not None:
            return AttributeDBNodeType.IPHOST
        return AttributeDBNodeType.DEFAULT

    def to_db(self) -> Dict[str, Any]:
        data = super().to_db()

        if self.value is not None:
            data["version"] = self.version
            data["binary_address"] = self.ip_binary
            data["prefixlen"] = self.prefixlen

        return data


class ListAttribute(BaseAttribute):
    type = list

    def serialize_value(self) -> str:
        """Serialize the value before storing it in the database."""
        return ujson.dumps(self.value)

    def deserialize_value(self, data: AttributeFromDB) -> Any:
        """Deserialize the value (potentially) coming from the database."""
        if isinstance(data.value, (str, bytes)):
            return ujson.loads(data.value)
        return data.value


class JSONAttribute(BaseAttribute):
    type = (dict, list)

    def serialize_value(self) -> str:
        """Serialize the value before storing it in the database."""
        return ujson.dumps(self.value)

    def deserialize_value(self, data: AttributeFromDB) -> Any:
        """Deserialize the value (potentially) coming from the database."""
        if data.value and isinstance(data.value, (str, bytes)):
            return ujson.loads(data.value)
        return data.value
