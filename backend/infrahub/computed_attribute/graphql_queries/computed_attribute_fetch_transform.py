from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ComputedAttributeFetchTransform(BaseModel):
    core_transform_python: ComputedAttributeFetchTransformCoreTransformPython = Field(alias="CoreTransformPython")


class ComputedAttributeFetchTransformCoreTransformPython(BaseModel):
    edges: list[ComputedAttributeFetchTransformCoreTransformPythonEdges]


class ComputedAttributeFetchTransformCoreTransformPythonEdges(BaseModel):
    node: ComputedAttributeFetchTransformCoreTransformPythonEdgesNode | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNode(BaseModel):
    id: str
    file_path: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeFilePath | None
    class_name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeClassName | None
    timeout: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeTimeout | None
    convert_query_response: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeConvertQueryResponse | None
    repository: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository
    query: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeFilePath(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeClassName(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeTimeout(BaseModel):
    value: Any | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeConvertQueryResponse(BaseModel):
    value: bool | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository(BaseModel):
    node: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode(BaseModel):
    typename__: Literal["CoreGenericRepository", "CoreReadOnlyRepository", "CoreRepository"] = Field(alias="__typename")
    id: str | None
    name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeName | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeName(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery(BaseModel):
    node: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode(BaseModel):
    id: str
    name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNodeName | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNodeName(BaseModel):
    value: str | None


ComputedAttributeFetchTransform.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPython.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdges.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNode.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode.model_rebuild()
