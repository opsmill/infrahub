from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class TransformPythonData(InfrahubMessage):
    """Sent to run a Python transform."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    data: dict = Field(..., description="Input data for the template")
    branch: str = Field(..., description="The branch to target")
    transform_location: str = Field(..., description="Location of the transform within the repository")
    commit: str = Field(..., description="The commit id to use when rendering the template")
