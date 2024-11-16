from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants.infrahubkind import STANDARDGROUP
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.services import services
from tests.helpers.graphql import graphql_query
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class TestNodeWithTypeNameAttr(TestInfrahubApp):
    # See #4381 for more details.
    async def test_node_with_type_name_attr(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
    ):
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Node",
                    "namespace": "Infra",
                    "display_labels": ["type__value"],
                    "attributes": [{"name": "type", "kind": "Text", "optional": False}],
                }
            ],
        }

        schema_root = SchemaRoot(**schema)  # type: ignore
        await load_schema(db, schema=schema_root)
        node = await Node.init(schema="InfraNode", db=db)
        await node.new(db=db, type="test_type")
        await node.save(db=db)

        group = await Node.init(schema=STANDARDGROUP, db=db)
        await group.new(db=db, name="test_group", members=[node])
        await group.save(db=db)

        query = """
            query {
              CoreStandardGroup {
                edges {
                  node {
                    members {
                      edges {
                        node {
                          display_label
                        }
                      }
                    }
                  }
                }
              }
            }
        """

        result = await graphql_query(query=query, db=db, service=services.service, branch=default_branch)
        assert result.errors is None
        assert result.data is not None
        assert (
            result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["edges"][0]["node"]["display_label"]
            == "test_type"
        )
