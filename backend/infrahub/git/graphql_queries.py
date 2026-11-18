from typing import Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel

from infrahub.core.constants import InfrahubKind
from infrahub.git.models import GitRepoNode

STORED_USER_CHECK_QUERY = """
query StoredUserCheck($validator_id: ID!, $name: String!) {
  CoreStandardCheck(validator__ids: [$validator_id], name__value: $name, kind__value: "CheckDefinition") {
    edges {
      node {
        id
      }
    }
  }
}
"""


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


class StoredUserCheckQuery(BaseModel):
    """Look up the check that a user check stored in its validator under its name.

    The name is a member's display label, so it is bound as a variable: the SDK writes an inline filter value that
    starts with `$` as a variable reference.
    """

    validator_id: str
    name: str

    def render_query(self) -> str:
        return STORED_USER_CHECK_QUERY

    def variables(self) -> dict[str, str]:
        return {"validator_id": self.validator_id, "name": self.name}

    def parse_response(self, response: dict[str, Any]) -> str | None:
        edges = (response.get(InfrahubKind.STANDARDCHECK) or {}).get("edges") or []
        return edges[0]["node"]["id"] if edges else None
