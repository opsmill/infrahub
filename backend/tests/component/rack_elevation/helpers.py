from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.graphql.error_formatter import format_graphql_errors
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

KINDS_QUERY = """
query {
  RackElevationKinds { kind role }
}
"""

ELEVATION_QUERY = """
query ($rack: String!, $label_by: String, $color_by: String) {
  RackElevation(rack: $rack, label_by: $label_by, color_by: $color_by) {
    rack { id kind display_label u_height used_units utilization total_weight }
    items {
      id kind display_label label color type_id type_display_label
      placement position face u_height full_depth weight
    }
  }
}
"""

PLACE_MUTATION = """
mutation ($item: String!, $rack: String!, $position: Int, $face: RackFace) {
  RackElevationPlace(item: $item, rack: $rack, position: $position, face: $face) {
    ok
    item { id position face placement }
  }
}
"""

RACK_TOTALS_QUERY = """
query {
  LocationRack {
    edges {
      node {
        name { value }
        rack_used_units { value }
        rack_utilization { value }
        rack_total_weight { value }
      }
    }
  }
}
"""


class RunGraphQL:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def __call__(
        self,
        branch: Branch,
        document: str,
        variables: dict[str, Any] | None = None,
        at: Timestamp | None = None,
    ) -> ExecutionResult:
        branch.update_schema_hash()
        service = await InfrahubServices.new(event=MemoryInfrahubEvent())
        gql_params = await prepare_graphql_params(db=self.db, branch=branch, at=at, service=service)
        return await graphql(
            schema=gql_params.schema,
            source=document,
            context_value=gql_params.context,
            root_value=None,
            variable_values=variables or {},
        )


def formatted_errors(result: ExecutionResult) -> list[dict[str, Any]]:
    assert result.errors is not None
    return [dict(error) for error in format_graphql_errors(result.errors)]
