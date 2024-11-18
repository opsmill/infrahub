from __future__ import annotations

from typing import Any

from graphene import BigInt, Boolean, DateTime, Field, InputObjectType, Int, List, ObjectType, String
from graphene.types.generic import GenericScalar

from infrahub.core import registry

from .enums import BranchRelativePermissionDecision
from .interface import InfrahubInterface


class GenericPoolInput(InputObjectType):
    id = String(required=True)
    identifier = String(required=False)
    data = GenericScalar(required=False)


class RelatedNodeInput(InputObjectType):
    id = String(required=False)
    hfid = Field(List(of_type=String), required=False)
    kind = String(required=False)  # Only used to resolve hfid of a related node on a generic relationship, see #4649
    from_pool = Field(GenericPoolInput, required=False)
    _relation__is_visible = Boolean(required=False)
    _relation__is_protected = Boolean(required=False)
    _relation__owner = String(required=False)
    _relation__source = String(required=False)


class IPAddressPoolInput(GenericPoolInput):
    prefixlen = Int(required=False)


class PrefixPoolInput(GenericPoolInput):
    size = Int(required=False)
    member_type = String(required=False)
    prefix_type = String(required=False)


class RelatedIPAddressNodeInput(InputObjectType):
    id = String(required=False)
    from_pool = Field(IPAddressPoolInput, required=False)
    _relation__is_visible = Boolean(required=False)
    _relation__is_protected = Boolean(required=False)
    _relation__owner = String(required=False)
    _relation__source = String(required=False)


class RelatedPrefixNodeInput(InputObjectType):
    id = String(required=False)
    hfid = Field(List(of_type=String), required=False)
    from_pool = Field(PrefixPoolInput, required=False)
    _relation__is_visible = Boolean(required=False)
    _relation__is_protected = Boolean(required=False)
    _relation__owner = String(required=False)
    _relation__source = String(required=False)


class PermissionType(ObjectType):
    update_value = Field(BranchRelativePermissionDecision, required=False)


class AttributeInterface(InfrahubInterface):
    is_default = Field(Boolean)
    is_inherited = Field(Boolean)
    is_protected = Field(Boolean)
    is_visible = Field(Boolean)
    updated_at = Field(DateTime)
    # Since source and owner are using a Type that is generated dynamically
    # these 2 fields will be dynamically inserted when we generate the GraphQL Schema
    # source = Field("DataSource")
    # owner = Field("DataOwner")


class BaseAttribute(ObjectType):
    id = Field(String)
    is_from_profile = Field(Boolean)
    permissions = Field(PermissionType, required=False)

    @classmethod
    def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
        super().__init_subclass__(**kwargs)
        registry.default_graphql_type[cls.__name__] = cls


class TextAttributeType(BaseAttribute):
    value = Field(String)

    class Meta:
        description = "Attribute of type Text"
        name = "TextAttribute"
        interfaces = {AttributeInterface}


class DropdownFields(ObjectType):
    value = Field(String)
    label = Field(String)
    color = Field(String)
    description = Field(String)


class DropdownType(BaseAttribute, DropdownFields):
    class Meta:
        description = "Attribute of type Dropdown"
        name = "Dropdown"
        interfaces = {AttributeInterface}


class IPHostType(BaseAttribute):
    value = Field(String)
    ip = Field(String)
    hostmask = Field(String)
    netmask = Field(String)
    prefixlen = Field(Int)
    version = Field(Int)
    with_hostmask = Field(String)
    with_netmask = Field(String)

    class Meta:
        description = "Attribute of type IPHost"
        name = "IPHost"
        interfaces = {AttributeInterface}


class IPNetworkType(BaseAttribute):
    value = Field(String)
    broadcast_address = Field(String)
    hostmask = Field(String)
    netmask = Field(String)
    prefixlen = Field(Int)
    num_addresses = Field(Int)
    version = Field(Int)
    with_hostmask = Field(String)
    with_netmask = Field(String)

    class Meta:
        description = "Attribute of type IPNetwork"
        name = "IPNetwork"
        interfaces = {AttributeInterface}


class MacAddressType(BaseAttribute):
    value = Field(String)
    oui = Field(String)
    ei = Field(String)
    version = Field(Int)
    binary = Field(String)
    eui48 = Field(String)
    eui64 = Field(String)
    bare = Field(String, description="Format without delimiters")
    dot_notation = Field(String, description="Format often used by Cisco devices")
    semicolon_notation = Field(String, description="Format used by UNIX based systems")
    split_notation = Field(String, description="Format used by PostgreSQL")

    class Meta:
        description = "Attribute of type MacAddress"
        name = "MacAddress"
        interfaces = {AttributeInterface}


class NumberAttributeType(BaseAttribute):
    value = Field(BigInt)

    class Meta:
        description = "Attribute of type Number"
        name = "NumberAttribute"
        interfaces = {AttributeInterface}


class CheckboxAttributeType(BaseAttribute):
    value = Field(Boolean)

    class Meta:
        description = "Attribute of type Checkbox"
        name = "CheckboxAttribute"
        interfaces = {AttributeInterface}


class StrAttributeType(BaseAttribute):
    value = Field(String)

    class Meta:
        description = "Attribute of type String"
        name = "StrAttribute"
        interfaces = {AttributeInterface}


class IntAttributeType(BaseAttribute):
    value = Field(Int)

    class Meta:
        description = "Attribute of type Integer"
        name = "IntAttribute"
        interfaces = {AttributeInterface}


class BoolAttributeType(BaseAttribute):
    value = Field(Boolean)

    class Meta:
        description = "Attribute of type Boolean"
        name = "BoolAttribute"
        interfaces = {AttributeInterface}


class ListAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type List"
        name = "ListAttribute"
        interfaces = {AttributeInterface}


class JSONAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type JSON"
        name = "JSONAttribute"
        interfaces = {AttributeInterface}


class AnyAttributeType(BaseAttribute):
    value = Field(GenericScalar)

    class Meta:
        description = "Attribute of type GenericScalar"
        name = "AnyAttribute"
        interfaces = {AttributeInterface}
