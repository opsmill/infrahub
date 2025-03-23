from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m023_duplicate_inherited_schema_fields import Migration023
from infrahub.core.models import HashableModelDiff, SchemaDiff
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.database import InfrahubDatabase


class TestDeleteInheritedSchemaFields:
    async def test(self, db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema) -> None:
        # create the schema on main
        schema_root = SchemaRoot(
            generics=[
                GenericSchema(
                    namespace="Testing",
                    name="Generic",
                    attributes=[
                        AttributeSchema(
                            name="generic_attr_text",
                            kind="Text",
                            optional=True,
                        )
                    ],
                    relationships=[RelationshipSchema(name="generic_rel_one", peer="TestingThing")],
                )
            ],
            nodes=[
                NodeSchema(
                    namespace="Testing",
                    name="Thing",
                    attributes=[AttributeSchema(name="value", kind="Text", optional=True)],
                ),
                NodeSchema(
                    namespace="Testing",
                    name="SpecificOne",
                    inherit_from=["TestingGeneric"],
                ),
                NodeSchema(
                    namespace="Testing",
                    name="SpecificTwo",
                    inherit_from=["TestingGeneric"],
                ),
            ],
        )
        main_schema_branch = registry.schema.register_schema(schema=schema_root)
        await registry.schema.load_schema_to_db(db=db, schema=main_schema_branch)

        # create a few TestingThings for later
        thing_ids = []
        for i in range(4):
            thing = await Node.init(db=db, branch=default_branch, schema="TestingThing")
            await thing.new(db=db, value=str(i))
            await thing.save(db=db)
            thing_ids.append(thing.get_id())

        # create the duplicative inherited schema fields
        attribute_schema = registry.schema.get_node_schema(name="SchemaAttribute", duplicate=False)
        relationship_schema = registry.schema.get_node_schema(name="SchemaRelationship", duplicate=False)

        # explicitly add the duplicate inherited relationships
        for schema_kind in ["TestingSpecificOne", "TestingSpecificTwo"]:
            node_schema = main_schema_branch.get(schema_kind)
            node_schema_instance = await NodeManager.get_one(db=db, branch=default_branch, id=node_schema.id)
            attr = node_schema.get_attribute("generic_attr_text")
            new_attr = await registry.schema.create_attribute_in_db(
                db=db, branch=default_branch, schema=attribute_schema, parent=node_schema_instance, item=attr
            )
            attr.id = new_attr.id
            rel = node_schema.get_relationship("generic_rel_one")
            new_rel = await registry.schema.create_relationship_in_db(
                db=db, branch=default_branch, schema=relationship_schema, parent=node_schema_instance, item=rel
            )
            rel.id = new_rel.id
            main_schema_branch.set(name=schema_kind, schema=node_schema)

        # override generic attr on default branch
        node_schema_with_override = main_schema_branch.get("TestingSpecificOne")
        attr_to_override = node_schema_with_override.get_attribute("generic_attr_text")
        attr_to_override.default_value = "the default"
        attr_to_override.inherited = False
        # override generic rel on default branch
        rel_to_override = node_schema_with_override.get_relationship("generic_rel_one")
        rel_to_override.max_count = 10
        rel_to_override.inherited = False
        main_schema_branch.set(name="TestingSpecificOne", schema=node_schema_with_override)
        schema_diff = SchemaDiff(
            changed={
                "TestingSpecificOne": HashableModelDiff(
                    changed={
                        "attributes": HashableModelDiff(
                            changed={
                                "generic_attr_text": HashableModelDiff(
                                    changed={"id": None, "inherited": None, "default_value": None}
                                )
                            }
                        ),
                        "relationships": HashableModelDiff(
                            changed={
                                "generic_rel_one": HashableModelDiff(
                                    changed={"id": None, "inherited": None, "max_count": None}
                                )
                            }
                        ),
                    }
                )
            }
        )

        await registry.schema.update_schema_branch(
            schema=main_schema_branch, db=db, branch=default_branch, diff=schema_diff
        )

        branch = await create_branch(db=db, branch_name="branch2")
        branch_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)

        # override generic attr on a branch
        node_schema_with_override = branch_schema_branch.get("TestingSpecificTwo")
        attr_to_override = node_schema_with_override.get_attribute("generic_attr_text")
        attr_to_override.default_value = "the default two"
        attr_to_override.inherited = False
        # override generic rel on a branch
        attr_to_override = node_schema_with_override.get_relationship("generic_rel_one")
        attr_to_override.max_count = 20
        attr_to_override.inherited = False
        branch_schema_branch.set(name="TestingSpecificTwo", schema=node_schema_with_override)
        # add a new generic field on a branch
        generic_schema_with_new_field = branch_schema_branch.get("TestingGeneric")
        new_attribute = AttributeSchema(name="generic_attr_num", kind="Number", optional=True)
        generic_schema_with_new_field.attributes.append(new_attribute)
        branch_schema_branch.set(name="TestingGeneric", schema=generic_schema_with_new_field)
        branch_schema_branch.process()
        schema_diff = SchemaDiff(
            changed={
                "TestingGeneric": HashableModelDiff(
                    changed={
                        "attributes": HashableModelDiff(
                            added={"generic_attr_num": None},
                        )
                    }
                ),
                "TestingSpecificTwo": HashableModelDiff(
                    changed={
                        "attributes": HashableModelDiff(
                            changed={
                                "generic_attr_text": HashableModelDiff(
                                    changed={"id": None, "inherited": None, "default_value": None}
                                )
                            }
                        ),
                        "relationships": HashableModelDiff(
                            changed={
                                "generic_rel_one": HashableModelDiff(
                                    changed={"id": None, "inherited": None, "max_count": None}
                                )
                            }
                        ),
                    }
                ),
            }
        )
        await registry.schema.update_schema_branch(schema=branch_schema_branch, db=db, branch=branch, diff=schema_diff)

        # explicitly add the duplicate inherited relationships on the branch
        for schema_kind in ["TestingSpecificOne", "TestingSpecificTwo"]:
            node_schema = branch_schema_branch.get(schema_kind)
            node_schema_instance = await NodeManager.get_one(db=db, branch=branch, id=node_schema.id)
            attr = node_schema.get_attribute("generic_attr_num")
            new_attr = await registry.schema.create_attribute_in_db(
                db=db, branch=branch, schema=attribute_schema, parent=node_schema_instance, item=attr
            )
            attr.id = new_attr.id
            branch_schema_branch.set(name=schema_kind, schema=node_schema)

        # create objects on default branch and branch
        main_specific_one = await Node.init(db=db, branch=default_branch, schema="TestingSpecificOne")
        await main_specific_one.new(db=db, generic_attr_text="main_specific_one", generic_rel_one=thing_ids[0])
        await main_specific_one.save(db=db)
        main_specific_two = await Node.init(db=db, branch=default_branch, schema="TestingSpecificTwo")
        await main_specific_two.new(db=db, generic_attr_text="main_specific_two", generic_rel_one=thing_ids[1])
        await main_specific_two.save(db=db)
        branch_specific_one = await Node.init(db=db, branch=branch, schema="TestingSpecificOne")
        await branch_specific_one.new(
            db=db, generic_attr_text="branch_specific_one", generic_attr_num=1, generic_rel_one=thing_ids[2]
        )
        await branch_specific_one.save(db=db)
        branch_specific_two = await Node.init(db=db, branch=branch, schema="TestingSpecificTwo")
        await branch_specific_two.new(
            db=db, generic_attr_text="branch_specific_two", generic_attr_num=2, generic_rel_one=thing_ids[3]
        )
        await branch_specific_two.save(db=db)

        # run the migration
        migration = Migration023()
        await migration.execute(db=db)
        await migration.validate_migration(db=db)

        # refresh the schema and validate on default branch
        refreshed_main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        generic_schema = refreshed_main_schema_branch.get_generic(name="TestingGeneric", duplicate=False)
        generic_attr_text = generic_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.inherited is False
        assert generic_attr_text.default_value is None
        assert generic_attr_text.id
        generic_rel_one = generic_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.max_count == 0
        assert generic_rel_one.inherited is False
        assert generic_rel_one.id
        specific_one_schema = refreshed_main_schema_branch.get_node(name="TestingSpecificOne", duplicate=False)
        generic_attr_text = specific_one_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.default_value == "the default"
        assert generic_attr_text.inherited is False
        assert generic_attr_text.id
        generic_rel_one = specific_one_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.max_count == 10
        assert generic_rel_one.inherited is False
        assert generic_rel_one.id
        assert "generic_attr_num" not in specific_one_schema.attribute_names
        specific_two_schema = refreshed_main_schema_branch.get_node(name="TestingSpecificTwo", duplicate=False)
        generic_attr_text = specific_two_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.default_value is None
        assert generic_attr_text.inherited is True
        assert not generic_attr_text.id
        generic_rel_one = specific_two_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.inherited is True
        assert generic_rel_one.max_count == 0
        assert generic_rel_one.id is None
        assert "generic_attr_num" not in specific_two_schema.attribute_names

        # refresh the schema and validate on other branch
        refreshed_branch_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = refreshed_branch_schema_branch.get_generic(name="TestingGeneric", duplicate=False)
        generic_attr_text = generic_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.inherited is False
        assert generic_attr_text.default_value is None
        assert generic_attr_text.id
        generic_rel_one = generic_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.max_count == 0
        assert generic_rel_one.inherited is False
        assert generic_rel_one.id
        specific_one_schema = refreshed_branch_schema_branch.get_node(name="TestingSpecificOne", duplicate=False)
        generic_attr_text = specific_one_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.default_value == "the default"
        assert generic_attr_text.inherited is False
        assert generic_attr_text.id
        generic_attr_num = specific_one_schema.get_attribute(name="generic_attr_num")
        assert generic_attr_num.default_value is None
        assert generic_attr_num.inherited is True
        assert not generic_attr_num.id
        generic_rel_one = specific_one_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.inherited is False
        assert generic_rel_one.max_count == 10
        assert generic_rel_one.id
        specific_two_schema = refreshed_branch_schema_branch.get_node(name="TestingSpecificTwo", duplicate=False)
        generic_attr_text = specific_two_schema.get_attribute(name="generic_attr_text")
        assert generic_attr_text.default_value == "the default two"
        assert generic_attr_text.inherited is False
        assert generic_attr_text.id
        generic_attr_num = specific_two_schema.get_attribute(name="generic_attr_num")
        assert generic_attr_num.default_value is None
        assert generic_attr_num.inherited is True
        assert not generic_attr_num.id
        generic_rel_one = specific_two_schema.get_relationship(name="generic_rel_one")
        assert generic_rel_one.inherited is False
        assert generic_rel_one.max_count == 20
        assert generic_rel_one.id

        # retrieve the instances and validate
        retrieved_main_specific_one = await NodeManager.get_one(db=db, branch=default_branch, id=main_specific_one.id)
        assert retrieved_main_specific_one.generic_attr_text.value == "main_specific_one"
        rels = await retrieved_main_specific_one.generic_rel_one.get_relationships(db=db)
        assert len(rels) == 1
        assert rels[0].peer_id == thing_ids[0]
        retrieved_main_specific_two = await NodeManager.get_one(db=db, branch=default_branch, id=main_specific_two.id)
        assert retrieved_main_specific_two.generic_attr_text.value == "main_specific_two"
        rels = await retrieved_main_specific_two.generic_rel_one.get_relationships(db=db)
        assert len(rels) == 1
        assert rels[0].peer_id == thing_ids[1]
        retrieved_branch_specific_one = await NodeManager.get_one(db=db, branch=branch, id=branch_specific_one.id)
        assert retrieved_branch_specific_one.generic_attr_text.value == "branch_specific_one"
        assert retrieved_branch_specific_one.generic_attr_num.value == 1
        rels = await retrieved_branch_specific_one.generic_rel_one.get_relationships(db=db)
        assert len(rels) == 1
        assert rels[0].peer_id == thing_ids[2]
        retrieved_branch_specific_two = await NodeManager.get_one(db=db, branch=branch, id=branch_specific_two.id)
        assert retrieved_branch_specific_two.generic_attr_text.value == "branch_specific_two"
        assert retrieved_branch_specific_two.generic_attr_num.value == 2
        rels = await retrieved_branch_specific_two.generic_rel_one.get_relationships(db=db)
        assert len(rels) == 1
        assert rels[0].peer_id == thing_ids[3]
