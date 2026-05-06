from typing import Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel

from infrahub.generators.models import GeneratorInstanceNode


class GeneratorInstanceQuery(BaseModel):
    query_name: ClassVar[str] = "GeneratorInstanceFetch"
    definition_id: str
    object_id: str

    def render_query(self) -> str:
        query = Query(
            name=self.query_name,
            query={
                "CoreGeneratorInstance": {
                    "@filters": {
                        "definition__ids": [self.definition_id],
                        "object__ids": [self.object_id],
                    },
                    "edges": {
                        "node": {
                            "id": None,
                            "status": {"value": None},
                        }
                    },
                }
            },
        )
        return query.render()

    def parse_response(self, response: dict[str, Any]) -> list[GeneratorInstanceNode]:
        result: list[GeneratorInstanceNode] = []
        if kind_payload := response.get("CoreGeneratorInstance"):
            for edge in kind_payload.get("edges", []):
                if node := edge.get("node"):
                    node_id = node.get("id")
                    status = (node.get("status") or {}).get("value")
                    if node_id and status is not None:
                        result.append(GeneratorInstanceNode(id=node_id, status=status))
        return result
