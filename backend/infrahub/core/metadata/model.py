from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import MetadataOptions

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp


@dataclass(frozen=True)
class MetadataQueryOptions:
    node_level: MetadataOptions = MetadataOptions.NONE
    attribute_level: MetadataOptions = MetadataOptions.NONE
    relationship_level: MetadataOptions = MetadataOptions.NONE

    def __or__(self, other: MetadataQueryOptions) -> MetadataQueryOptions:
        return MetadataQueryOptions(
            node_level=self.node_level | other.node_level,
            attribute_level=self.attribute_level | other.attribute_level,
            relationship_level=self.relationship_level | other.relationship_level,
        )


@dataclass
class MetadataInfo:
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None
