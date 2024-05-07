from typing import Optional

from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.types import ProposedChangeGeneratorDefinition


class CheckGeneratorRun(InfrahubMessage):
    """A check that runs a generator."""

    generator_definition: ProposedChangeGeneratorDefinition = Field(..., description="The Generator definition")
    generator_instance: Optional[str] = Field(
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
    validator_id: str = Field(..., description="The ID of the validator")
