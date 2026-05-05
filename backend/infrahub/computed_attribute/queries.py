from __future__ import annotations

import uuid
from typing import Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel, ConfigDict

from infrahub.core.query.node_query import NodeIDQuery


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


class ComputedAttributeNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "ComputedAttributeFetchNodeIDs"


class TransformNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    file_path: str
    class_name: str
    timeout: int
    convert_query_response: bool
    repository_id: str
    repository_typename: str
    repository_name: str
    query_id: str


class ComputedAttributeTransformQuery(BaseModel):
    query_name: ClassVar[str] = "ComputedAttributeFetchTransform"
    transform_id: str

    def render_query(self) -> str:
        query = Query(
            name=self.query_name,
            query={
                "CoreTransformPython": {
                    "@filters": {"ids": [self.transform_id]}
                    if _is_uuid(self.transform_id)
                    else {"name__value": self.transform_id},
                    "edges": {
                        "node": {
                            "id": None,
                            "file_path": {"value": None},
                            "class_name": {"value": None},
                            "timeout": {"value": None},
                            "convert_query_response": {"value": None},
                            "repository": {
                                "node": {
                                    "id": None,
                                    "__typename": None,
                                    "name": {"value": None},
                                }
                            },
                            "query": {
                                "node": {
                                    "id": None,
                                }
                            },
                        }
                    },
                }
            },
        )
        return query.render()

    def parse_response(self, response: dict[str, Any]) -> TransformNode | None:
        if kind_payload := response.get("CoreTransformPython"):
            edges = kind_payload.get("edges", [])
            if not edges:
                return None
            node = edges[0].get("node", {})
            repo_node = (node.get("repository") or {}).get("node") or {}
            query_node = (node.get("query") or {}).get("node") or {}
            node_id = node.get("id")
            file_path = (node.get("file_path") or {}).get("value")
            class_name = (node.get("class_name") or {}).get("value")
            timeout = (node.get("timeout") or {}).get("value")
            convert_query_response = (node.get("convert_query_response") or {}).get("value")
            repository_id = repo_node.get("id")
            repository_typename = repo_node.get("__typename")
            repository_name = (repo_node.get("name") or {}).get("value")
            query_id = query_node.get("id")
            if (
                node_id is not None
                and file_path is not None
                and class_name is not None
                and timeout is not None
                and convert_query_response is not None
                and repository_id is not None
                and repository_typename is not None
                and repository_name is not None
                and query_id is not None
            ):
                return TransformNode(
                    id=node_id,
                    file_path=file_path,
                    class_name=class_name,
                    timeout=timeout,
                    convert_query_response=convert_query_response,
                    repository_id=repository_id,
                    repository_typename=repository_typename,
                    repository_name=repository_name,
                    query_id=query_id,
                )
        return None
