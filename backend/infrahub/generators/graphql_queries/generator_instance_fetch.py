from __future__ import annotations

from pydantic import BaseModel, Field


class GeneratorInstanceFetch(BaseModel):
    core_generator_instance: GeneratorInstanceFetchCoreGeneratorInstance = Field(alias="CoreGeneratorInstance")


class GeneratorInstanceFetchCoreGeneratorInstance(BaseModel):
    edges: list[GeneratorInstanceFetchCoreGeneratorInstanceEdges]


class GeneratorInstanceFetchCoreGeneratorInstanceEdges(BaseModel):
    node: GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode | None


class GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode(BaseModel):
    id: str
    status: GeneratorInstanceFetchCoreGeneratorInstanceEdgesNodeStatus | None


class GeneratorInstanceFetchCoreGeneratorInstanceEdgesNodeStatus(BaseModel):
    value: str | None


GeneratorInstanceFetch.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstance.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstanceEdges.model_rebuild()
GeneratorInstanceFetchCoreGeneratorInstanceEdgesNode.model_rebuild()
