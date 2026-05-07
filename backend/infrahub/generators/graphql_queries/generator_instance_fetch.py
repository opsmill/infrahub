from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GeneratorInstanceFetch(BaseModel):
    core_generator_instance: "GeneratorInstanceFetchCoreGeneratorInstance" = Field(
        alias="CoreGeneratorInstance"
    )


class GeneratorInstanceFetchCoreGeneratorInstance(BaseModel):
    edges: list["GeneratorInstanceFetchCoreGeneratorInstanceEdges"]


class GeneratorInstanceFetchCoreGeneratorInstanceEdges(BaseModel):
    node: Optional["GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode"]


class GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode(BaseModel):
    id: str
    status: Optional["GeneratorInstanceFetchCoreGeneratorInstanceEdgesNodeStatus"]


class GeneratorInstanceFetchCoreGeneratorInstanceEdgesNodeStatus(BaseModel):
    value: Optional[str]


GeneratorInstanceFetch.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstance.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstanceEdges.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode.model_rebuild()
