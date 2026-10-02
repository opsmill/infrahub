from dataclasses import dataclass
from typing import Any

from graphql import ExecutionResult

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
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
mutation CreateNumberPool($name: String!) {
  CoreNumberPoolCreate(
    data: {
      name: {value: $name},
      node: {value: "TestingTicket"},
      node_attribute: {value: "ticket_id"},
      %s
    }
  ) {
    ok
    object { id start_range { value } end_range { value } ranges { count } }
  }
}
"""


@dataclass
class BoundsCase:
    name: str
    bounds: str


async def execute(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def create_pool(db: InfrahubDatabase, branch: Branch, name: str, bounds: str) -> str:
    result = await execute(
        db=db, branch=branch, source=CREATE_NUMBER_POOL_WITH_BOUNDS % bounds, variables={"name": name}
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


async def shorthand(db: InfrahubDatabase, pool_id: str) -> tuple[int | None, int | None]:
    pool = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
    return pool.start_range.value, pool.end_range.value
