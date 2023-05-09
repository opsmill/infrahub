from typing import Dict, Optional

from pydantic import BaseModel


class BranchData(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_data_only: bool
    is_default: bool
    origin_branch: Optional[str]
    branched_from: str


class RepositoryData(BaseModel):
    id: str
    name: str
    location: str
    branches: Dict[str, str]
