from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.core import registry
from infrahub.core.constants import HashableModelState, RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.submitted_ids.repository import SchemaElementRepository
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

KIND = "IdqueryWidget"


@dataclass
class IdSetup:
    node_id: str
    name_attr_id: str
    tags_rel_id: str
    serial_attr_id: str
    color_attr_id: str
    data_node_id: str
    unknown_id: str


class TestSchemaElementIdsQuery:
    @pytest.fixture(scope="class")
    async def ids(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_internal_models_schema_scope_class: SchemaBranch,
    ) -> IdSetup:
        schema = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Idquery",
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="serial", kind="Text", optional=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="tags",
                            peer="IdqueryWidget",
                            optional=True,
                            cardinality=RelationshipCardinality.MANY,
                        ),
                    ],
                ),
            ],
        )
        main = default_branch_scope_class
        main_schema = registry.schema.register_schema(schema=schema, branch=main.name)
        await registry.schema.load_schema_to_db(schema=main_schema, db=db, branch=main, limit=[KIND], at=Timestamp())
        widget = main_schema.get_node(name=KIND, duplicate=False)
        node_id = widget.get_id()
        name_attr_id = widget.get_attribute(name="name").get_id()
        tags_rel_id = widget.get_relationship(name="tags").get_id()
        serial_attr_id = widget.get_attribute(name="serial").get_id()

        branch1 = await create_branch(branch_name="branch1", db=db)
        branch_schema = registry.schema.get_schema_branch(name=branch1.name)
        branch_schema.get(name=KIND, duplicate=False).attributes.append(
            AttributeSchema(name="color", kind="Text", optional=True)
        )
        branch_schema.process()
        await registry.schema.update_schema_branch(
            schema=branch_schema, db=db, branch=branch1, diff=main_schema.diff(other=branch_schema), at=Timestamp()
        )
        color_attr_id = branch_schema.get(name=KIND, duplicate=False).get_attribute(name="color").get_id()

        removed_schema = main_schema.duplicate()
        removed_schema.get(name=KIND, duplicate=False).get_attribute(name="serial").state = HashableModelState.ABSENT
        await registry.schema.update_schema_branch(
            schema=removed_schema, db=db, branch=main, diff=main_schema.diff(other=removed_schema), at=Timestamp()
        )

        data_node = await Node.init(db=db, schema=KIND, branch=main)
        await data_node.new(db=db, name="w1")
        await data_node.save(db=db)

        await db.execute_query(query="CREATE (:Node:SchemaAttribute {uuid: $id})", params={"id": name_attr_id})

        return IdSetup(
            node_id=node_id,
            name_attr_id=name_attr_id,
            tags_rel_id=tags_rel_id,
            serial_attr_id=serial_attr_id,
            color_attr_id=color_attr_id,
            data_node_id=data_node.get_id(),
            unknown_id=str(uuid4()),
        )

    async def test_returns_schema_vertices_from_any_branch_and_time(self, db: InfrahubDatabase, ids: IdSetup) -> None:
        found = await SchemaElementRepository(db=db).get_existing_ids(
            [
                ids.node_id,
                ids.name_attr_id,
                ids.tags_rel_id,
                ids.serial_attr_id,
                ids.color_attr_id,
                ids.data_node_id,
                ids.unknown_id,
            ]
        )
        assert found == {ids.node_id, ids.name_attr_id, ids.tags_rel_id, ids.serial_attr_id, ids.color_attr_id}

    @pytest.mark.usefixtures("query_limit_of_one")
    async def test_returns_every_match_when_the_matches_span_several_pages(
        self, db: InfrahubDatabase, ids: IdSetup
    ) -> None:
        found = await SchemaElementRepository(db=db).get_existing_ids(
            [ids.node_id, ids.name_attr_id, ids.tags_rel_id, ids.serial_attr_id, ids.color_attr_id, ids.unknown_id]
        )
        assert found == {ids.node_id, ids.name_attr_id, ids.tags_rel_id, ids.serial_attr_id, ids.color_attr_id}

    async def test_empty_input_returns_empty_set(self, db: InfrahubDatabase, ids: IdSetup) -> None:
        assert await SchemaElementRepository(db=db).get_existing_ids([]) == set()
