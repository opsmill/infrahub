from typing import Optional

from infrahub.core.constants import FilterSchemaKind
from infrahub.core.models import HashableModel


class FilterSchema(HashableModel):
    name: str
    kind: FilterSchemaKind
    enum: Optional[list] = None
    object_kind: Optional[str] = None
    description: Optional[str] = None

    _sort_by: list[str] = ["name"]
