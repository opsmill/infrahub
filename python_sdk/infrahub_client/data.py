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


class CheckData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    repository: str
    file_path: str
    class_name: str
    query: str
    timeout: Optional[int]
    rebase: Optional[bool]


class TransformPythonData(BaseModel):
    id: Optional[str]
    name: str
    description: Optional[str]
    repository: str
    file_path: str
    class_name: str
    query: str
    url: str
    timeout: Optional[int]
    rebase: Optional[bool]
