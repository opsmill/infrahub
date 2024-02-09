from __future__ import annotations

from typing import List, Union

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "migration.node.attribute_add"


class MigrationNodeAttributeAdd(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    node_schema: Union[NodeSchema, GenericSchema] = Field(..., description="Schema of Node or Generic to update")
    attribute_name: str = Field(..., description="Name of the attribute to add in the schema")


class MigrationNodeAttributeAddResponseData(InfrahubResponseData):
    errors: List[str] = Field(default_factory=list)


class MigrationNodeAttributeAddResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: MigrationNodeAttributeAddResponseData
