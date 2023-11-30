from typing import List, Optional

from pydantic import BaseModel


class SerializedAttribute(BaseModel):
    name: str
    value: Optional[str]


class SerializedRelationship(BaseModel):
    name: str
    linked_ids: List[str]


class SerializedNode(BaseModel):
    id: str
    display_label: Optional[str]
    namespace: str
    name: str
    attributes: List[SerializedAttribute]
    relationships: List[SerializedRelationship]
