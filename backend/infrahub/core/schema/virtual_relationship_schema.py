from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .generated.virtual_relationship_schema import GeneratedVirtualRelationshipSchema

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class VirtualRelationshipSchema(GeneratedVirtualRelationshipSchema):
    _sort_by: list[str] = ["name"]

    @property
    def is_attribute(self) -> bool:
        return False

    @property
    def is_relationship(self) -> bool:
        return False

    @property
    def is_virtual_relationship(self) -> bool:
        return True

    def get_path_segments(self) -> list[str]:
        """Split the path on '__' to get individual relationship name segments."""
        return self.path.split("__")

    def get_peer_schema(self, db: InfrahubDatabase, branch: str | None = None) -> MainSchemaTypes:
        if not self.peer:
            raise ValueError(f"Virtual relationship '{self.name}' has no peer set. Run schema processing first.")
        return db.schema.get(name=self.peer, branch=branch, duplicate=False)

    def to_dict(self) -> dict:
        data = self.model_dump(exclude_unset=True, exclude_none=True)
        for field_name, value in data.items():
            if isinstance(value, Enum):
                data[field_name] = value.value
        return data
