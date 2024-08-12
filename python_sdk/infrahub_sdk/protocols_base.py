from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


class RelatedNode(Protocol): ...


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
    value: str


class IPNetworkOptional(Attribute):
    value: Optional[str]


class IPHost(Attribute):
    value: str


class IPHostOptional(Attribute):
    value: Optional[str]


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


class CoreNodeBase(Protocol):
    id: str
    display_label: Optional[str]
    hfid: Optional[list[str]]
    hfid_str: Optional[str]


class CoreNode(CoreNodeBase, Protocol):
    def get_kind(self) -> str: ...

    async def save(self) -> None: ...

    async def update(self, do_full_update: bool) -> None: ...


class CoreNodeSync(CoreNodeBase, Protocol):
    id: str
    display_label: Optional[str]
    hfid: Optional[list[str]]
    hfid_str: Optional[str]

    def get_kind(self) -> str: ...

    def save(self) -> None: ...

    def update(self, do_full_update: bool) -> None: ...
