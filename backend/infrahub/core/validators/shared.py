from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class SchemaViolation(BaseModel):
    node_id: str
    node_kind: str
    display_label: str


class SchemaValidator(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the validator")

    async def run_validate(self, db: InfrahubDatabase, branch: Branch) -> List[SchemaViolation]:
        raise NotImplementedError
