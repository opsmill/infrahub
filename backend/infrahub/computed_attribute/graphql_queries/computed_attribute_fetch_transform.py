from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ComputedAttributeFetchTransform(BaseModel):
    core_transform_python: "ComputedAttributeFetchTransformCoreTransformPython" = Field(
        alias="CoreTransformPython"
    )


class ComputedAttributeFetchTransformCoreTransformPython(BaseModel):
    edges: list["ComputedAttributeFetchTransformCoreTransformPythonEdges"]


class ComputedAttributeFetchTransformCoreTransformPythonEdges(BaseModel):
    node: Optional["ComputedAttributeFetchTransformCoreTransformPythonEdgesNode"]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNode(BaseModel):
    id: str
    file_path: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeFilePath"
    ]
    class_name: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeClassName"
    ]
    timeout: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeTimeout"
    ]
    convert_query_response: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeConvertQueryResponse"
    ]
    repository: "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository"
    query: "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery"


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeFilePath(BaseModel):
    value: Optional[str]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeClassName(BaseModel):
    value: Optional[str]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeTimeout(BaseModel):
    value: Optional[Any]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeConvertQueryResponse(
    BaseModel
):
    value: Optional[bool]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository(BaseModel):
    node: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode"
    ]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode(
    BaseModel
):
    typename__: Literal[
        "CoreGenericRepository", "CoreReadOnlyRepository", "CoreRepository"
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeName"
    ]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNodeName(
    BaseModel
):
    value: Optional[str]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery(BaseModel):
    node: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode"
    ]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode(BaseModel):
    id: str
    name: Optional[
        "ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNodeName"
    ]


class ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNodeName(
    BaseModel
):
    value: Optional[str]


ComputedAttributeFetchTransform.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPython.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdges.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNode.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepository.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeRepositoryNode.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQuery.model_rebuild()
ComputedAttributeFetchTransformCoreTransformPythonEdgesNodeQueryNode.model_rebuild()
