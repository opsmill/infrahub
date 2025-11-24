from pydantic import BaseModel


class BranchCreateModel(BaseModel):
    name: str
    id: str | None = None
    description: str = ""
    origin_branch: str = "main"
    branched_from: str | None = None
    sync_with_git: bool = True
    is_isolated: bool = True


class BranchCreateModelWithMetaFields(BranchCreateModel):
    created_at: str | None = None
    created_by: str | None = None
