from typing import Optional

from pydantic import BaseModel


class BranchCreateModel(BaseModel):
    name: str
    id: Optional[str] = None
    description: str = ""
    origin_branch: str = "main"
    branched_from: Optional[str] = None
    sync_with_git: bool = True
    is_isolated: bool = True
