from dataclasses import dataclass

from infrahub.core.timestamp import Timestamp


@dataclass
class MetadataInfo:
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None
