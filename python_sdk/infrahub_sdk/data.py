from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from infrahub_sdk.node import InfrahubNode


class RepositoryBranchInfo(BaseModel):
    internal_status: str


class RepositoryData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    repository: InfrahubNode = Field(..., description="InfrahubNode representing a Repository")
    branches: dict[str, str] = Field(
        ..., description="Dictionary with the name of the branch as the key and the active commit id as the value"
    )

    branch_info: dict[str, RepositoryBranchInfo] = Field(default_factory=dict)

    def get_staging_branch(self) -> Optional[str]:
        for branch, info in self.branch_info.items():  # pylint: disable=no-member
            if info.internal_status == "staging":
                return branch
        return None
