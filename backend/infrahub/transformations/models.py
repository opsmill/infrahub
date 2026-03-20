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


class TransformAIData(BaseModel):
    """Sent to run an AI-powered transform using Claude API."""

    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the repository")
    repository_kind: str = Field(..., description="The kind of the repository")
    data: dict = Field(..., description="Input data for the AI transform")
    branch: str = Field(..., description="The branch to target")
    prompt_template_path: str = Field(..., description="Path to the prompt template within the repository")
    commit: str = Field(..., description="The commit id to use when generating the report")
    model: str = Field(..., description="Claude model to use for generation")
    temperature: float = Field(..., description="Temperature for Claude API (0.0-1.0)")
    max_tokens: int = Field(..., description="Maximum tokens for Claude API response")
    output_format: str = Field(..., description="Output format: markdown or csv")
    timeout: int = Field(..., description="The timeout value to use when generating the report")
    result_kind: str | None = Field(default=None, description="Schema kind for the result FileObject")
