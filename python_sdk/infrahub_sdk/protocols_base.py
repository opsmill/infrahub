from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, Union, runtime_checkable

if TYPE_CHECKING:
    import ipaddress

    from infrahub_sdk.schema import MainSchemaTypes


@runtime_checkable
class RelatedNode(Protocol): ...


@runtime_checkable
class RelatedNodeSync(Protocol): ...


@runtime_checkable
class Attribute(Protocol):
    name: str
    id: Optional[str]

    is_default: Optional[bool]
    is_from_profile: Optional[bool]
    is_inherited: Optional[bool]
    updated_at: Optional[str]
    is_visible: Optional[bool]
    is_protected: Optional[bool]


class String(Attribute):
    value: str


class StringOptional(Attribute):
    value: Optional[str]


class Integer(Attribute):
    value: int


class IntegerOptional(Attribute):
    value: Optional[int]


class Boolean(Attribute):
    value: bool


class BooleanOptional(Attribute):
    value: Optional[bool]


class DateTime(Attribute):
    value: str


class DateTimeOptional(Attribute):
    value: Optional[str]


class Enum(Attribute):
    value: str


class EnumOptional(Attribute):
    value: Optional[str]


class URL(Attribute):
    value: str


class URLOptional(Attribute):
    value: Optional[str]


class Dropdown(Attribute):
    value: str


class DropdownOptional(Attribute):
    value: Optional[str]


class IPNetwork(Attribute):
    value: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


class IPNetworkOptional(Attribute):
    value: Optional[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]


class IPHost(Attribute):
    value: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


class IPHostOptional(Attribute):
    value: Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]


class HashedPassword(Attribute):
    value: str


class HashedPasswordOptional(Attribute):
    value: Any


class JSONAttribute(Attribute):
    value: Any


class JSONAttributeOptional(Attribute):
    value: Optional[Any]


class ListAttribute(Attribute):
    value: list[Any]


class ListAttributeOptional(Attribute):
    value: Optional[list[Any]]


@runtime_checkable
class CoreNodeBase(Protocol):
    _schema: MainSchemaTypes
    id: str
    display_label: Optional[str]

    @property
    def hfid(self) -> Optional[list[str]]: ...

    @property
    def hfid_str(self) -> Optional[str]: ...

    def get_human_friendly_id_as_string(self, include_kind: bool = False) -> Optional[str]: ...

    def get_kind(self) -> str: ...

    def is_ip_prefix(self) -> bool: ...

    def is_ip_address(self) -> bool: ...

    def is_resource_pool(self) -> bool: ...

    def get_raw_graphql_data(self) -> Optional[dict]: ...

    def validate_filters(self, filters: Optional[dict[str, Any]] = None) -> bool: ...

    def extract(self, params: dict[str, str]) -> dict[str, Any]: ...


@runtime_checkable
class CoreNode(CoreNodeBase, Protocol):
    async def save(self, allow_upsert: bool = False, update_group_context: Optional[bool] = None) -> None: ...

    async def delete(self) -> None: ...

    async def update(self, do_full_update: bool) -> None: ...

    async def create(self, allow_upsert: bool = False) -> None: ...

    async def add_relationships(self, relation_to_update: str, related_nodes: list[str]) -> None: ...

    async def remove_relationships(self, relation_to_update: str, related_nodes: list[str]) -> None: ...


@runtime_checkable
class CoreNodeSync(CoreNodeBase, Protocol):
    def save(self, allow_upsert: bool = False, update_group_context: Optional[bool] = None) -> None: ...

    def delete(self) -> None: ...

    def update(self, do_full_update: bool) -> None: ...

    def create(self, allow_upsert: bool = False) -> None: ...

    def add_relationships(self, relation_to_update: str, related_nodes: list[str]) -> None: ...

    def remove_relationships(self, relation_to_update: str, related_nodes: list[str]) -> None: ...
