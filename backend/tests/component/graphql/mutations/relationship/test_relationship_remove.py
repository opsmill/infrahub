from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestRelationshipRemoveMandatory:
    @pytest.fixture
    async def mandatory_schemas(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        node_group_schema: None,
        data_schema: None,
    ) -> SchemaBranch:
        schema = SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(
                    name="Label",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
                ),
                NodeSchema(
                    name="Item",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
                    relationships=[
                        RelationshipSchema(
                            name="labels", peer="TestLabel", cardinality=RelationshipCardinality.MANY, optional=False
                        )
                    ],
                ),
                NodeSchema(
                    name="Category",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
                ),
                NodeSchema(
                    name="Product",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
                    relationships=[
                        RelationshipSchema(
                            name="categories",
                            peer="TestCategory",
                            cardinality=RelationshipCardinality.MANY,
                            optional=False,
                        )
                    ],
                ),
            ],
        )
        return registry.schema.register_schema(schema=schema, branch=default_branch.name)

    async def test_rejected(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        mandatory_schemas: SchemaBranch,
    ) -> None:
        """RelationshipRemove that would leave an optional=False relationship with zero peers must be rejected."""
        label_schema = mandatory_schemas.get_node(name="TestLabel")
        item_schema = mandatory_schemas.get_node(name="TestItem")

        label = await Node.init(db=db, schema=label_schema, branch=default_branch)
        await label.new(db=db, name="label-one")
        await label.save(db=db)

        node = await Node.init(db=db, schema=item_schema, branch=default_branch)
        await node.new(db=db, name="subject-item", labels=[label])
        await node.save(db=db)

        query = """
        mutation RelationshipRemove($id: String!, $node_id: String!) {
            RelationshipRemove(data: {
                id: $id,
                name: "labels",
                nodes: [{id: $node_id}],
            }) {
                ok
            }
        }
        """

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": node.id, "node_id": label.id},
        )

        assert result.errors
        assert result.errors[0].message == "'labels' is a mandatory relationship and cannot be fully removed at name"

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        remaining = await refreshed.get_relationship("labels").get_relationships(db=db)
        assert len(remaining) == 1
        assert remaining[0].peer_id == label.id

    async def test_partial_allowed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        mandatory_schemas: SchemaBranch,
    ) -> None:
        """RelationshipRemove that leaves at least one peer on an optional=False relationship must succeed."""
        category_schema = mandatory_schemas.get_node(name="TestCategory")
        product_schema = mandatory_schemas.get_node(name="TestProduct")

        cat1 = await Node.init(db=db, schema=category_schema, branch=default_branch)
        await cat1.new(db=db, name="category-1")
        await cat1.save(db=db)

        cat2 = await Node.init(db=db, schema=category_schema, branch=default_branch)
        await cat2.new(db=db, name="category-2")
        await cat2.save(db=db)

        node = await Node.init(db=db, schema=product_schema, branch=default_branch)
        await node.new(db=db, name="main-product", categories=[cat1, cat2])
        await node.save(db=db)

        query = """
        mutation RelationshipRemove($id: String!, $node_id: String!) {
            RelationshipRemove(data: {
                id: $id,
                name: "categories",
                nodes: [{id: $node_id}],
            }) {
                ok
            }
        }
        """

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": node.id, "node_id": cat1.id},
        )

        assert result.errors is None

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        remaining = await refreshed.get_relationship("categories").get_relationships(db=db)
        assert len(remaining) == 1
        assert remaining[0].peer_id == cat2.id
