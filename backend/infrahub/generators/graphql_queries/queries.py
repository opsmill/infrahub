from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from infrahub.generators.graphql_queries.generator_instance_fetch import GeneratorInstanceFetch
from infrahub.generators.models import GeneratorInstanceNode

GENERATOR_INSTANCE_QUERY = (Path(__file__).parent / "generator_instance_fetch.gql").read_text()


class GeneratorInstanceQuery(BaseModel):
    query_name: ClassVar[str] = "GeneratorInstanceFetch"
    definition_id: str
    object_id: str

    def render_query(self) -> str:
        return GENERATOR_INSTANCE_QUERY

    def get_variables(self) -> dict[str, str]:
        return {"definition_id": self.definition_id, "object_id": self.object_id}

    def parse_response(self, response: dict[str, Any]) -> list[GeneratorInstanceNode]:
        typed = GeneratorInstanceFetch.model_validate(response)
        result = []
        for edge in typed.core_generator_instance.edges:
            node = edge.node
            if node and node.id and node.status and node.status.value is not None:
                result.append(GeneratorInstanceNode(id=node.id, status=node.status.value))
        return result
