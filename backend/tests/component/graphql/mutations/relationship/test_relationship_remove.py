from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
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


REMOVE_QUERY = """
mutation RelationshipRemove($id: String!, $name: String!, $node_id: String!) {
    RelationshipRemove(data: {
        id: $id,
        name: $name,
        nodes: [{id: $node_id}],
    }) {
        ok
    }
}
"""


def _named_node(name: str, relationships: list[RelationshipSchema]) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
        relationships=relationships,
    )


@pytest.fixture
async def component_schemas(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    schema = SchemaRoot(
        version="1.0",
        nodes=[
            _named_node(
                name="Rack",
                relationships=[
                    RelationshipSchema(
                        name="slots",
                        peer="TestSlot",
                        kind=RelationshipKind.COMPONENT,
                        identifier="rack__slot",
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    )
                ],
            ),
            _named_node(
                name="Slot",
                relationships=[
                    RelationshipSchema(
                        name="rack",
                        peer="TestRack",
                        kind=RelationshipKind.PARENT,
                        identifier="rack__slot",
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    )
                ],
            ),
            _named_node(
                name="Shelf",
                relationships=[
                    RelationshipSchema(
                        name="boxes",
                        peer="TestBox",
                        kind=RelationshipKind.COMPONENT,
                        identifier="shelf__box",
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    )
                ],
            ),
            _named_node(
                name="Box",
                relationships=[
                    RelationshipSchema(
                        name="shelf",
                        peer="TestShelf",
                        identifier="shelf__box",
                        cardinality=RelationshipCardinality.ONE,
                        optional=True,
                    )
                ],
            ),
        ],
    )
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def _create(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=schema.get_node(name=kind), branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def test_relationship_remove_refuses_only_a_peer_left_without_its_mandatory_peer(
    db: InfrahubDatabase, default_branch: Branch, component_schemas: SchemaBranch
) -> None:
    rack = await _create(db=db, branch=default_branch, schema=component_schemas, kind="TestRack", name="rack-1")
    slot = await _create(
        db=db, branch=default_branch, schema=component_schemas, kind="TestSlot", name="slot-1", rack=rack
    )
    shelf = await _create(db=db, branch=default_branch, schema=component_schemas, kind="TestShelf", name="shelf-1")
    box = await _create(
        db=db, branch=default_branch, schema=component_schemas, kind="TestBox", name="box-1", shelf=shelf
    )
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    mandatory_result = await graphql(
        schema=gql_params.schema,
        source=REMOVE_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": rack.id, "name": "slots", "node_id": slot.id},
    )
    optional_result = await graphql(
        schema=gql_params.schema,
        source=REMOVE_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": shelf.id, "name": "boxes", "node_id": box.id},
    )

    assert mandatory_result.errors
    assert mandatory_result.errors[0].message == (
        f"'{slot.id}' 'TestSlot' can't be removed from 'slots': its mandatory relationship 'rack' would be left empty"
    )
    refreshed_rack = await NodeManager.get_one(db=db, id=rack.id, branch=default_branch)
    assert [rel.peer_id for rel in await refreshed_rack.get_relationship("slots").get_relationships(db=db)] == [slot.id]
    refreshed_slot = await NodeManager.get_one(db=db, id=slot.id, branch=default_branch)
    assert await refreshed_slot.get_relationship("rack").get_peer_id(db=db) == rack.id

    assert optional_result.errors is None
    refreshed_shelf = await NodeManager.get_one(db=db, id=shelf.id, branch=default_branch)
    assert await refreshed_shelf.get_relationship("boxes").get_relationships(db=db) == []
    refreshed_box = await NodeManager.get_one(db=db, id=box.id, branch=default_branch)
    assert await refreshed_box.get_relationship("shelf").get_peer_id(db=db) is None


async def _remove(db: InfrahubDatabase, branch: Branch, source_id: str, name: str, peer_id: str) -> Any:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=REMOVE_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": source_id, "name": name, "node_id": peer_id},
    )


async def test_relationship_remove_refuses_a_hierarchy_child_whose_parent_is_mandatory(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    europe = hierarchical_location_data["europe"]
    paris = hierarchical_location_data["paris"]
    site_schema = registry.schema.get_node_schema(name="LocationSite", branch=default_branch, duplicate=False)
    assert site_schema.get_relationship(name="parent").optional is False
    assert (
        site_schema.get_relationship(name="parent").identifier
        == site_schema.get_relationship(name="children").identifier
    )

    result = await _remove(db=db, branch=default_branch, source_id=europe.id, name="children", peer_id=paris.id)

    assert result.errors
    assert result.errors[0].message == (
        f"'{paris.id}' 'LocationSite' can't be removed from 'children': its mandatory relationship 'parent' would be left empty"
    )
    refreshed_paris = await NodeManager.get_one(db=db, id=paris.id, branch=default_branch)
    assert await refreshed_paris.get_relationship("parent").get_peer_id(db=db) == europe.id


@pytest.fixture
async def optional_parent_hierarchy_schemas(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    schema = SchemaRoot(
        version="1.0",
        generics=[
            GenericSchema(
                name="Zone",
                namespace="Test",
                hierarchical=True,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            )
        ],
        nodes=[
            NodeSchema(
                name="Region", namespace="Test", inherit_from=["TestZone"], parent="TestZone", children="TestZone"
            )
        ],
    )
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def test_relationship_remove_accepts_a_hierarchy_child_whose_parent_is_optional(
    db: InfrahubDatabase, default_branch: Branch, optional_parent_hierarchy_schemas: SchemaBranch
) -> None:
    europe = await _create(
        db=db, branch=default_branch, schema=optional_parent_hierarchy_schemas, kind="TestRegion", name="europe"
    )
    west = await _create(
        db=db,
        branch=default_branch,
        schema=optional_parent_hierarchy_schemas,
        kind="TestRegion",
        name="west",
        parent=europe,
    )
    region_schema = optional_parent_hierarchy_schemas.get_node(name="TestRegion")
    assert region_schema.get_relationship(name="parent").optional is True
    assert region_schema.get_relationship(name="children").optional is True

    result = await _remove(db=db, branch=default_branch, source_id=europe.id, name="children", peer_id=west.id)

    assert result.errors is None
    refreshed_west = await NodeManager.get_one(db=db, id=west.id, branch=default_branch)
    assert await refreshed_west.get_relationship("parent").get_peer_id(db=db) is None


@pytest.fixture
async def directed_schemas(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    schema = SchemaRoot(
        version="1.0",
        generics=[
            GenericSchema(
                name="Staff",
                namespace="Test",
                relationships=[
                    RelationshipSchema(
                        name="reports",
                        peer="TestEmployee",
                        identifier="staff__manager",
                        direction=RelationshipDirection.INBOUND,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    )
                ],
            )
        ],
        nodes=[
            NodeSchema(
                name="Director",
                namespace="Test",
                inherit_from=["TestStaff"],
                attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
            ),
            NodeSchema(
                name="Employee",
                namespace="Test",
                inherit_from=["TestStaff"],
                attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
                relationships=[
                    RelationshipSchema(
                        name="manager",
                        peer="TestStaff",
                        identifier="staff__manager",
                        direction=RelationshipDirection.OUTBOUND,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    )
                ],
            ),
            _named_node(
                name="Owner",
                relationships=[
                    RelationshipSchema(
                        name="items",
                        peer="TestAsset",
                        identifier="owner__asset",
                        direction=RelationshipDirection.OUTBOUND,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    )
                ],
            ),
            _named_node(
                name="Asset",
                relationships=[
                    RelationshipSchema(
                        name="owner",
                        peer="TestOwner",
                        identifier="owner__asset",
                        direction=RelationshipDirection.INBOUND,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    )
                ],
            ),
        ],
    )
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def test_relationship_remove_refuses_a_peer_declaring_both_directions_whose_mirrored_side_is_mandatory(
    db: InfrahubDatabase, default_branch: Branch, directed_schemas: SchemaBranch
) -> None:
    director = await _create(db=db, branch=default_branch, schema=directed_schemas, kind="TestDirector", name="boss")
    employee = await _create(
        db=db, branch=default_branch, schema=directed_schemas, kind="TestEmployee", name="employee", manager=director
    )
    employee_schema = directed_schemas.get_node(name="TestEmployee")
    assert employee_schema.get_relationship(name="manager").identifier == "staff__manager"
    assert employee_schema.get_relationship(name="reports").identifier == "staff__manager"

    result = await _remove(db=db, branch=default_branch, source_id=director.id, name="reports", peer_id=employee.id)

    assert result.errors
    assert result.errors[0].message == (
        f"'{employee.id}' 'TestEmployee' can't be removed from 'reports': its mandatory relationship 'manager' would be left empty"
    )
    refreshed_employee = await NodeManager.get_one(db=db, id=employee.id, branch=default_branch)
    assert await refreshed_employee.get_relationship("manager").get_peer_id(db=db) == director.id


async def test_relationship_remove_refuses_a_peer_whose_mirrored_inbound_side_is_mandatory(
    db: InfrahubDatabase, default_branch: Branch, directed_schemas: SchemaBranch
) -> None:
    owner = await _create(db=db, branch=default_branch, schema=directed_schemas, kind="TestOwner", name="owner-1")
    asset = await _create(
        db=db, branch=default_branch, schema=directed_schemas, kind="TestAsset", name="asset-1", owner=owner
    )

    result = await _remove(db=db, branch=default_branch, source_id=owner.id, name="items", peer_id=asset.id)

    assert result.errors
    assert result.errors[0].message == (
        f"'{asset.id}' 'TestAsset' can't be removed from 'items': its mandatory relationship 'owner' would be left empty"
    )
    refreshed_asset = await NodeManager.get_one(db=db, id=asset.id, branch=default_branch)
    assert await refreshed_asset.get_relationship("owner").get_peer_id(db=db) == owner.id
