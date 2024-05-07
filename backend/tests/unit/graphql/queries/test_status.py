from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.components import ComponentType
from infrahub.core.registry import registry
from infrahub.services import InfrahubServices
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_query

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_status_query(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None):
    cache = MemoryCache()
    bus = BusRecorder()
    service = InfrahubServices(cache=cache, database=db, component_type=ComponentType.API_SERVER, message_bus=bus)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    await service.component.initialize(service=service)
    await service.component.refresh_heartbeat()
    await service.component.refresh_schema_hash()
    response = await graphql_query(query=STATUS_QUERY, db=db, branch=default_branch, service=service)
    assert not response.errors
    assert response.data
    status = response.data["InfrahubStatus"]
    assert status["summary"]["schema_hash_synced"]
    nodes = status["workers"]["edges"]
    assert len(nodes) == 1
    assert nodes[0]["node"]["active"]
    assert nodes[0]["node"]["id"] == WORKER_IDENTITY
    assert nodes[0]["node"]["schema_hash"] == schema_branch.get_hash()


STATUS_QUERY = """
query InfrahubStatus {
  InfrahubStatus {
    workers {
      edges {
        node {
          active
          id
          schema_hash
        }
      }
    }
    summary {
      schema_hash_synced
    }
  }
}
"""
