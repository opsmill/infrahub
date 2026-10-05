from dataclasses import dataclass
from typing import Any

from graphql import ExecutionResult

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.graphql import graphql

CREATE_NUMBER_POOL = """
mutation CreateNumberPool(
    $name: String!,
    $node: String!,
    $node_attribute: String!,
    $start_range: BigInt,
    $end_range: BigInt
  ) {
  CoreNumberPoolCreate(
    data: {
      name: {value: $name},
      node:{value: $node},
      node_attribute: {value: $node_attribute},
      start_range: {value: $start_range},
      end_range: {value: $end_range}
    }
  ) {
    object {
      display_label
      id
    }
  }
}
"""


UPDATE_NUMBER_POOL = """
mutation UpdateNumberPool(
    $id: String!,
    $name: String,
    $node: String,
    $node_attribute: String,
    $start_range: BigInt,
    $end_range: BigInt
  ) {
  CoreNumberPoolUpdate(
    data: {
      id: $id,
      name: {value: $name},
      node:{value: $node},
      node_attribute: {value: $node_attribute},
      start_range: {value: $start_range},
      end_range: {value: $end_range}
    }
  ) {
    object {
      display_label
      id
      end_range { value }
    }
  }
}
"""


DELETE_NUMBER_POOL = """
mutation DeleteNumberPool(
    $id: String!,
  ) {
  CoreNumberPoolDelete(
    data: {
      id: $id,
    }
  ) {
    ok
  }
}
"""


QUERY_NUMBER_POOL = """
query NumberPool(
    $id: ID!,
  ) {
  CoreNumberPool(
    ids: [$id]
  ) {
    count
  }
}
"""


CREATE_NUMBER_POOL_WITH_BOUNDS = """
mutation CreateNumberPool($data: CoreNumberPoolCreateInput!) {
  CoreNumberPoolCreate(data: $data) {
    ok
    object { id start_range { value } end_range { value } ranges { count } }
  }
}
"""


@dataclass
class BoundsCase:
    name: str
    bounds: dict[str, Any]


def bounds_input(start: int, end: int) -> dict[str, Any]:
    return {"start_range": {"value": start}, "end_range": {"value": end}}


def ticket_pool_input(name: str, bounds: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": {"value": name},
        "node": {"value": "TestingTicket"},
        "node_attribute": {"value": "ticket_id"},
    } | bounds


async def execute(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def create_pool(db: InfrahubDatabase, branch: Branch, name: str, bounds: dict[str, Any]) -> str:
    result = await execute(
        db=db,
        branch=branch,
        source=CREATE_NUMBER_POOL_WITH_BOUNDS,
        variables={"data": ticket_pool_input(name=name, bounds=bounds)},
    )
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPoolCreate"]["object"]["id"]


async def range_bounds(db: InfrahubDatabase, pool_id: str) -> list[tuple[int, int]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return [(pool_range.start.value, pool_range.end.value) for pool_range in ranges]


async def range_details(db: InfrahubDatabase, pool_id: str) -> list[tuple[str, int, int, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return [
        (pool_range.get_id(), pool_range.start.value, pool_range.end.value, pool_range.allocation_weight.value)
        for pool_range in ranges
    ]


async def load_pool(db: InfrahubDatabase, pool_id: str) -> Node:
    return await NodeManager.get_one(db=db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, raise_on_error=True)


async def shorthand(db: InfrahubDatabase, pool_id: str) -> tuple[int | None, int | None]:
    pool = await load_pool(db=db, pool_id=pool_id)
    return pool.start_range.value, pool.end_range.value
