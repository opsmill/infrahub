from dataclasses import dataclass
from typing import Any

from infrahub.core.timestamp import Timestamp


@dataclass
class MetadataInfo:
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None


class MetadataBase:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._metadata_info: MetadataInfo = MetadataInfo()

    def set_created_at(self, value: Timestamp | None) -> None:
        self._metadata_info.created_at = value

    def set_created_by(self, value: str | None) -> None:
        self._metadata_info.created_by = value

    def set_updated_at(self, value: Timestamp | None) -> None:
        self._metadata_info.updated_at = value

    def set_updated_by(self, value: str | None) -> None:
        self._metadata_info.updated_by = value

    def get_created_at(self) -> Timestamp | None:
        return self._metadata_info.created_at

    def get_created_by(self) -> str | None:
        return self._metadata_info.created_by

    def get_updated_at(self) -> Timestamp | None:
        return self._metadata_info.updated_at

    def get_updated_by(self) -> str | None:
        return self._metadata_info.updated_by
