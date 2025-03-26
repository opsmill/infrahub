from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RequestGeneratorRun(BaseModel):
    """Runs a generator."""

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator definition")
    generator_instance: str | None = Field(
        default=None, description="The id of the generator instance if it previously existed"
    )
    commit: str = Field(..., description="The commit to target")
    repository_id: str = Field(..., description="The unique ID of the Repository")
    repository_name: str = Field(..., description="The name of the Repository")
    repository_kind: str = Field(..., description="The kind of the Repository")
    branch_name: str = Field(..., description="The branch where the check is run")
    target_id: str = Field(..., description="The ID of the target object for this generator")
    target_name: str = Field(..., description="Name of the generator target")
    query: str = Field(..., description="The name of the query to use when collecting data")
    variables: dict = Field(..., description="Input variables when running the generator")


class RequestGeneratorDefinitionRun(BaseModel):
    """Sent to trigger a Generator to run on a specific branch."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator Definition")
    branch: str = Field(..., description="The branch to target")
    target_members: list[str] = Field(default_factory=list, description="List of targets to run the generator for")


class ProposedChangeGeneratorDefinition(BaseModel):
    definition_id: str
    definition_name: str
    query_name: str
    convert_query_response: bool
    query_models: list[str]
    repository_id: str
    class_name: str
    file_path: str
    parameters: dict
    group_id: str
