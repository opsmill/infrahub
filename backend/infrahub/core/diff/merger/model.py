from typing_extensions import TypedDict


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
