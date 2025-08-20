from pydantic import BaseModel, Field


class RequestDiffUpdate(BaseModel):
    """
    Request diff to be updated.

    If the message only include a branch_name, it is assumed to be for updating the diff that tracks
    the lifetime changes of a branch
    """

    branch_name: str = Field(..., description="The branch associated with the diff")
    name: str | None = None
    from_time: str | None = None
    to_time: str | None = None
