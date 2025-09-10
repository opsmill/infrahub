from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RequestGeneratorRun(BaseModel):
    """Runs a generator."""

    generator_definition: GeneratorDefinitionModel = Field(..., description="The Generator definition")
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


class GeneratorDefinitionModel(BaseModel):
    definition_id: str = Field(..., description="The id of the generator definition.")
    definition_name: str = Field(..., description="The name of the generator definition.")
    query_name: str = Field(..., description="The name of the query to use when collecting data.")
    convert_query_response: bool = Field(
        ...,
        description="Decide if the generator should convert the result of the GraphQL query to SDK InfrahubNode objects.",
    )
    class_name: str = Field(..., description="The name of the generator class to run.")
    file_path: str = Field(..., description="The file path of the generator in the repository.")
    group_id: str = Field(..., description="The group to target when running this generator")
    parameters: dict = Field(..., description="The input parameters required to run this check")

    @classmethod
    def from_pc_generator_definition(cls, model: ProposedChangeGeneratorDefinition) -> GeneratorDefinitionModel:
        return GeneratorDefinitionModel(
            definition_id=model.definition_id,
            definition_name=model.definition_name,
            query_name=model.query_name,
            convert_query_response=model.convert_query_response,
            class_name=model.class_name,
            file_path=model.file_path,
            group_id=model.group_id,
            parameters=model.parameters,
        )


class ProposedChangeGeneratorDefinition(GeneratorDefinitionModel):
    query_models: list[str] = Field(..., description="The models to use when collecting data.")
    repository_id: str = Field(..., description="The id of the repository.")
