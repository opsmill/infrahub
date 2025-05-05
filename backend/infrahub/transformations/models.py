from pydantic import BaseModel, Field


class TransformPythonData(BaseModel):
    """Sent to run a Python transform."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    data: dict = Field(..., description="Input data for the template")
    branch: str = Field(..., description="The branch to target")
    transform_location: str = Field(..., description="Location of the transform within the repository")
    commit: str = Field(..., description="The commit id to use when generating the artifact")
    convert_query_response: bool = Field(
        ..., description="Define if the GraphQL query respose should be converted into InfrahubNode objects"
    )
    timeout: int = Field(..., description="The timeout value to use when generating the artifact")


class TransformJinjaTemplateData(BaseModel):
    """Sent to trigger the checks for a repository to be executed."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    data: dict = Field(..., description="Input data for the template")
    branch: str = Field(..., description="The branch to target")
    template_location: str = Field(..., description="Location of the template within the repository")
    commit: str = Field(..., description="The commit id to use when rendering the template")
    timeout: int = Field(..., description="The timeout value to use when rendering the template")
