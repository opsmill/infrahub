from pydantic import BaseModel, ConfigDict, Field

from infrahub_sdk.node import InfrahubNode


class RepositoryData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    repository: InfrahubNode = Field(..., description="InfrahubNode representing a Repository")
    branches: dict[str, str] = Field(
        ..., description="Dictionary with the name of the branch as the key and the active commit id as the value"
    )
