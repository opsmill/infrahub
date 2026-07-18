from __future__ import annotations

from typing import Annotated, Any, Literal

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
    node: (
        Annotated[
            ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreGenericRepository
            | ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepository
            | ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepository,
            Field(discriminator="typename__"),
        ]
        | None
    )


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreGenericRepository(BaseModel):
    typename__: Literal["CoreGenericRepository"] = Field(alias="__typename")
    id: str | None
    name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreGenericRepositoryName | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreGenericRepositoryName(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepository(BaseModel):
    typename__: Literal["CoreReadOnlyRepository"] = Field(alias="__typename")
    id: str
    name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepositoryName | None
    commit: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepositoryCommit | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepositoryName(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepositoryCommit(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepository(BaseModel):
    typename__: Literal["CoreRepository"] = Field(alias="__typename")
    id: str
    name: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepositoryName | None
    commit: ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepositoryCommit | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepositoryName(BaseModel):
    value: str | None


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepositoryCommit(BaseModel):
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
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreGenericRepository.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreReadOnlyRepository.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeCoreRepository.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode.model_rebuild()
