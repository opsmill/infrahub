from typing import Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel

from infrahub.git.models import GitRepoNode


class GitRepositoryNodeQuery(BaseModel):
    query_name: ClassVar[str] = "GitFetchRepositories"

    def render_query(self) -> str:
        query = Query(
            name=self.query_name,
            query={
                "CoreRepository": {
                    "edges": {
                        "node": {
                            "id": None,
                            "name": {"value": None},
                            "location": {"value": None},
                        }
                    }
                }
            },
        )
        return query.render()

    def parse_response(self, response: dict[str, Any]) -> list[GitRepoNode]:
        result: list[GitRepoNode] = []
        if kind_payload := response.get("CoreRepository"):
            for edge in kind_payload.get("edges", []):
                if node := edge.get("node"):
                    node_id = node.get("id")
                    name = (node.get("name") or {}).get("value")
                    location = (node.get("location") or {}).get("value")
                    if node_id and name and location:
                        result.append(GitRepoNode(id=node_id, name=name, location=location))
        return result
