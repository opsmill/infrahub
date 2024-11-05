from typing import TypedDict


class RelationshipMergeDict(TypedDict):
    peer_id: str
    name: str
    action: str


class AttributeMergeDict(TypedDict):
    name: str
    action: str


class NodeMergeDict(TypedDict):
    uuid: str
    action: str
    attributes: list[AttributeMergeDict]
    relationships: list[RelationshipMergeDict]


class PropertyMergeDict(TypedDict):
    property_type: str
    action: str
    value: str | bool | int | float | None


class AttributePropertyMergeDict(TypedDict):
    node_uuid: str
    attribute_name: str
    properties: list[PropertyMergeDict]


class RelationshipPropertyMergeDict(TypedDict):
    node_uuid: str
    relationship_id: str
    peer_uuid: str
    properties: list[PropertyMergeDict]
