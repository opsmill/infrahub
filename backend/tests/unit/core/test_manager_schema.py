from deepdiff import DeepDiff

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import SchemaManager, SchemaRegistryBranch
from infrahub.core.schema import (
    FilterSchemaKind,
    GenericSchema,
    GroupSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)

# -----------------------------------------------------------------
# SchemaRegistryBranch
# -----------------------------------------------------------------


async def test_schema_branch_set():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    schema_branch = SchemaRegistryBranch(cache={}, name="test")

    schema_branch.set(name="schema1", schema=schema)
    assert hash(schema) in schema_branch._cache
    assert len(schema_branch._cache) == 1

    schema_branch.set(name="schema2", schema=schema)
    assert len(schema_branch._cache) == 1


async def test_schema_branch_get(default_branch: Branch):
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    schema_branch = SchemaRegistryBranch(cache={}, name="test")

    schema_branch.set(name="schema1", schema=schema)
    assert len(schema_branch._cache) == 1

    schema11 = schema_branch.get(name="schema1")
    assert schema11 == schema


async def test_schema_branch_load_schema():
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "level", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            }
        ],
        "generics": [
            {
                "name": "generic_interface",
                "kind": "GenericInterface",
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text"},
                ],
            },
        ],
        "groups": [
            {
                "name": "generic_group",
                "kind": "GenericGroup",
            },
        ],
    }

    schema_branch = SchemaRegistryBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))

    assert isinstance(schema_branch.get(name="Criticality"), NodeSchema)
    assert isinstance(schema_branch.get(name="GenericGroup"), GroupSchema)
    assert isinstance(schema_branch.get(name="GenericInterface"), GenericSchema)


async def test_schema_branch_process_filters(
    session, reset_registry, default_branch: Branch, register_internal_models_schema
):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "label": "Tags", "optional": True, "cardinality": "many"},
                    {
                        "name": "primary_tag",
                        "peer": "Tag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "tag",
                "kind": "Tag",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ]
    }

    schema_branch = SchemaRegistryBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    schema_branch.process_filters()

    assert len(schema_branch.nodes) == 2
    criticality_dict = schema_branch.get("Criticality").dict()

    expected_filters = [
        {"name": "ids", "kind": FilterSchemaKind.LIST, "enum": None, "object_kind": None, "description": None},
        {
            "name": "level__value",
            "kind": FilterSchemaKind.NUMBER,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "name__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
    ]

    assert not DeepDiff(criticality_dict["filters"], expected_filters, ignore_order=True)


async def test_schema_branch_copy(session, reset_registry, default_branch: Branch, register_internal_models_schema):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "label": "Tags", "optional": True, "cardinality": "many"},
                    {
                        "name": "primary_tag",
                        "peer": "Tag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "tag",
                "kind": "Tag",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ]
    }

    schema_branch = SchemaRegistryBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    new_schema = schema_branch.duplicate()

    assert id(new_schema.nodes) != id(schema_branch.nodes)
    assert hash(new_schema) == hash(schema_branch)

    new_schema.process()
    assert hash(new_schema) != hash(schema_branch)


async def test_schema_branch_diff(session, reset_registry, default_branch: Branch, register_internal_models_schema):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "label": "Tags", "optional": True, "cardinality": "many"},
                    {
                        "name": "primary_tag",
                        "peer": "Tag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "tag",
                "kind": "Tag",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ]
    }

    schema_branch = SchemaRegistryBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    new_schema = schema_branch.duplicate()

    node = new_schema.get(name="Criticality")
    node.attributes[0].unique = False
    new_schema.set(name="Criticality", schema=node)

    diff = schema_branch.diff(obj=new_schema)

    assert diff["values_changed"]["root['nodes']['Criticality']"]


# -----------------------------------------------------------------
# SchemaManager
# -----------------------------------------------------------------
async def test_schema_manager_set():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)
    manager = SchemaManager()

    manager.set(name="schema1", schema=schema)
    assert hash(schema) in manager._cache
    assert len(manager._cache) == 1

    manager.set(name="schema2", schema=schema)
    assert len(manager._cache) == 1


async def test_schema_manager_get(default_branch: Branch):
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    manager = SchemaManager()

    manager.set(name="schema1", schema=schema)
    assert len(manager._cache) == 1

    schema11 = manager.get(name="schema1")
    assert schema11 == schema


# -----------------------------------------------------------------


async def test_load_node_to_db_node_schema(session, default_branch: Branch):
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
    }
    node = NodeSchema(**SCHEMA)

    await registry.schema.load_node_to_db(node=node, session=session, branch=default_branch)

    results = await SchemaManager.query(
        schema="NodeSchema", filters={"kind__value": "Criticality"}, branch=default_branch, session=session
    )
    assert len(results) == 1


async def test_load_node_to_db_generic_schema(session, default_branch):
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "generic_interface",
        "kind": "GenericInterface",
        "attributes": [
            {"name": "my_generic_name", "kind": "Text"},
        ],
    }
    node = GenericSchema(**SCHEMA)
    await registry.schema.load_node_to_db(node=node, session=session, branch=default_branch)

    results = await SchemaManager.query(
        schema="GenericSchema", filters={"kind__value": "GenericInterface"}, branch=default_branch, session=session
    )
    assert len(results) == 1


async def test_load_node_to_db_group_schema(session, default_branch: Branch):
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "generic_group",
        "kind": "GenericGroup",
    }

    node = GroupSchema(**SCHEMA)
    await registry.schema.load_node_to_db(node=node, session=session, branch=default_branch)

    results = await SchemaManager.query(
        schema="GroupSchema", filters={"kind__value": "GenericGroup"}, branch=default_branch, session=session
    )
    assert len(results) == 1


# async def test_load_schema_to_db_internal_models(session, default_branch):
#     schema = SchemaRoot(**internal_schema)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     await SchemaManager.load_schema_to_db(schema=schema, session=session)

#     node_schema = registry.get_schema(name="NodeSchema")
#     results = await SchemaManager.query(schema=node_schema, session=session)
#     assert len(results) > 1


async def test_load_schema_to_db_core_models(session, default_branch: Branch, register_internal_models_schema):
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, session=session)

    node_schema = registry.get_schema(name="GenericSchema")
    results = await registry.schema.query(schema=node_schema, session=session)
    assert len(results) > 1


# async def test_load_schema_to_db_simple_01(
#     session, default_branch, register_core_models_schema, schema_file_infra_simple_01
# ):
#     schema = SchemaRoot(**schema_file_infra_simple_01)

#     schema.extend_nodes_with_interfaces()
#     await SchemaManager.register_schema_to_registry(schema)
#     await SchemaManager.load_schema_to_db(schema=schema, session=session)

#     assert True


# async def test_load_schema_to_db_w_generics_01(
#     session, default_branch, register_core_models_schema, schema_file_infra_w_generics_01
# ):
#     schema = SchemaRoot(**schema_file_infra_w_generics_01)

#     schema.extend_nodes_with_interfaces()
#     await SchemaManager.register_schema_to_registry(schema)
#     await SchemaManager.load_schema_to_db(schema=schema, session=session)

#     assert True


async def test_load_schema_from_db(session, reset_registry, default_branch: Branch, register_internal_models_schema):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {"name": "tags", "peer": "Tag", "label": "Tags", "optional": True, "cardinality": "many"},
                    {
                        "name": "primary_tag",
                        "peer": "Tag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "tag",
                "kind": "Tag",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
        "generics": [
            {
                "name": "generic_interface",
                "kind": "GenericInterface",
                "label": "Generic Interface",
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String"},
                ],
            },
        ],
        "groups": [
            {
                "name": "generic_group",
                "kind": "GenericGroup",
            },
        ],
    }
    schema1 = SchemaRoot(**FULL_SCHEMA)
    registry.schema.load_schema_to_db(schema=schema1, session=session)
    schema2 = await registry.schema.load_schema_from_db(session=session)

    assert len(schema2.nodes) == 2
    assert len(schema2.generics) == 1
    assert len(schema2.groups) == 1

    schema_criticality = [node for node in schema2.nodes if node.kind == "Criticality"][0]

    assert not DeepDiff(
        schema1.nodes[0].dict(exclude={"filters", "relationships"}),
        schema_criticality.dict(exclude={"filters", "relationships"}),
        ignore_order=True,
    )
    assert not DeepDiff(
        schema1.generics[0].dict(exclude={"filters"}), schema2.generics[0].dict(exclude={"filters"}), ignore_order=True
    )

    assert not DeepDiff(
        schema1.groups[0].dict(exclude={"filters"}), schema2.groups[0].dict(exclude={"filters"}), ignore_order=True
    )

    criticality_dict = schema_criticality.dict()

    expected_filters = [
        {"name": "ids", "kind": FilterSchemaKind.LIST, "enum": None, "object_kind": None, "description": None},
        {
            "name": "level__value",
            "kind": FilterSchemaKind.NUMBER,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "name__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
    ]

    expected_relationships = [
        {
            "name": "tags",
            "peer": "Tag",
            "label": "Tags",
            "kind": "Generic",
            "description": None,
            "identifier": "criticality__tag",
            "inherited": False,
            "cardinality": "many",
            "branch": True,
            "optional": True,
            "filters": [
                {"name": "id", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
                {
                    "name": "description__value",
                    "kind": FilterSchemaKind.TEXT,
                    "enum": None,
                    "object_kind": None,
                    "description": None,
                },
                {
                    "name": "name__value",
                    "kind": FilterSchemaKind.TEXT,
                    "enum": None,
                    "object_kind": None,
                    "description": None,
                },
            ],
        },
        {
            "name": "primary_tag",
            "peer": "Tag",
            "label": "Primary Tag",
            "kind": "Generic",
            "description": None,
            "identifier": "primary_tag__criticality",
            "inherited": False,
            "cardinality": "one",
            "branch": True,
            "optional": True,
            "filters": [
                {"name": "id", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
                {
                    "name": "description__value",
                    "kind": FilterSchemaKind.TEXT,
                    "enum": None,
                    "object_kind": None,
                    "description": None,
                },
                {
                    "name": "name__value",
                    "kind": FilterSchemaKind.TEXT,
                    "enum": None,
                    "object_kind": None,
                    "description": None,
                },
            ],
        },
    ]

    assert not DeepDiff(criticality_dict["filters"], expected_filters, ignore_order=True)
    assert not DeepDiff(criticality_dict["relationships"], expected_relationships, ignore_order=True)
