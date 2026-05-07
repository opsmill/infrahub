from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from infrahub.computed_attribute.graphql_queries.computed_attribute_fetch_transform import (
    ComputedAttributeFetchTransform,
)
from infrahub.core.graphql_query.node_id_query import NodeIDQuery

TRANSFORM_QUERY = (Path(__file__).parent / "transform_fetch.gql").read_text()


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

    def get_variables(self) -> dict[str, Any]:
        if _is_uuid(self.transform_id):
            return {"transform_ids": [self.transform_id], "transform_name": None}
        return {"transform_ids": None, "transform_name": self.transform_id}

    def render_query(self) -> str:
        return TRANSFORM_QUERY

    def parse_response(self, response: dict[str, Any]) -> TransformNode | None:
        try:
            typed = ComputedAttributeFetchTransform.model_validate(response)
        except ValidationError:
            return None
        edges = typed.core_transform_python.edges
        if not edges:
            return None
        node = edges[0].node
        if node is None:
            return None
        repo = node.repository.node if node.repository else None
        query_node = node.query.node if node.query else None
        if (
            node.id
            and node.file_path
            and node.file_path.value is not None
            and node.class_name
            and node.class_name.value is not None
            and node.timeout
            and node.timeout.value is not None
            and node.convert_query_response
            and node.convert_query_response.value is not None
            and repo
            and repo.id
            and repo.typename__
            and repo.name
            and repo.name.value is not None
            and query_node
            and query_node.id
        ):
            return TransformNode(
                id=node.id,
                file_path=node.file_path.value,
                class_name=node.class_name.value,
                timeout=node.timeout.value,
                convert_query_response=node.convert_query_response.value,
                repository_id=repo.id,
                repository_typename=repo.typename__,
                repository_name=repo.name.value,
                query_id=query_node.id,
            )
        return None
