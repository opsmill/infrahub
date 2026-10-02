from dataclasses import dataclass

CREATE_NUMBER_POOL = """
mutation CreateNumberPool(
    $name: String!,
    $node: String!,
    $node_attribute: String!,
    $start_range: BigInt!,
    $end_range: BigInt!
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
    object { id start_range { value } end_range { value } }
  }
}
"""


UNKNOWN_RANGE_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


@dataclass
class BoundsCase:
    name: str
    bounds: str
