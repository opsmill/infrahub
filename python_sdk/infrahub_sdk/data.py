from typing import Dict

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from infrahub_sdk.node import InfrahubNode


class RepositoryData(pydantic.BaseModel):
    repository: InfrahubNode = pydantic.Field(..., description="InfrahubNode representing a Repository")
    branches: Dict[str, str] = pydantic.Field(
        ..., description="Dictionary with the name of the branch as the key and the active commit id as the value"
    )

    class Config:
        arbitrary_types_allowed = True
