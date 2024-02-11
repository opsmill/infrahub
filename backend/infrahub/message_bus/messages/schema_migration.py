from __future__ import annotations

from typing import List

from pydantic import Field

from infrahub.message_bus import InfrahubResponseData


class SchemaMigrationResponseData(InfrahubResponseData):
    errors: List[str] = Field(default_factory=list)
