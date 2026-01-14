from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.graphql import graphql_query
from tests.helpers.test_app import TestInfrahubApp


class TestQueryOrder(TestInfrahubApp):
    async def test_query_default_order(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, session_admin, client
    ) -> None:
        for i in range(5, 0, -1):
            node = await Node.init(db=db, schema="BuiltinTag")
            await node.new(db=db, name=f"tag-{i}")
            await node.save(db=db)

        for disable_order in [True, False, None]:
            variables = {"order": {"disable": disable_order}} if disable_order is not None else {"order": None}

            query = """
                query($order: OrderInput) {
                    BuiltinTag(order: $order) {
                        edges {
                            node {
                                name { value }
                            }
                        }
                    }
                }
            """

            res = await graphql_query(query=query, db=db, branch=default_branch, variables=variables)

            node_names = [edge["node"]["name"]["value"] for edge in res.data["BuiltinTag"]["edges"]]
            if disable_order is True:
                node_names = sorted(node_names)
            assert node_names == [f"tag-{i}" for i in range(1, 6)]
