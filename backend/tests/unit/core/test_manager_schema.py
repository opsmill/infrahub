from deepdiff import DeepDiff

from infrahub.core import registry
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

# class SchemaRegistryBranch:
#     def __init__(self, cache: Dict, name: Optional[str] = None, data: Optional[Dict[str, int]] = None):
#         self._cache: Dict[int, Union[NodeSchema, GenericSchema]] = cache
#         self.name: str = name
#         self.nodes: Dict[str, int] = {}
#         self.generics: Dict[str, int] = {}

#         if data:
#             self.nodes = data.get("nodes", {})
#         if data:
#             self.generics = data.get("generics", {})

#     def __hash__(self):
#         return hash(tuple(self.nodes.items()) + tuple(self.generics.items()))

#     def to_dict(self):
#         # TODO need to implement a flag to return the real objects if needed
#         return {"nodes": self.nodes, "generics": self.generics}

#     def diff(self, obj: SchemaRegistryBranch):
#         return DeepDiff(self.to_dict(), obj.to_dict(), ignore_order=True)

#     def copy(self, name: Optional[str] = None):
#         return self.__class__(name=name, data=copy.copy(self.to_dict()), cache=self._cache)

#     def set(self, name: str, schema: Union[NodeSchema, GenericSchema, GroupSchema]) -> int:
#         schema_hash = hash(schema)
#         if schema_hash not in self._cache:
#             self._cache[schema_hash] = schema

#         if "Node" in schema.__class__.__name__:
#             self.nodes[name] = schema_hash
#         elif "Generic" in schema.__class__.__name__:
#             self.generics[name] = schema_hash

#         return schema_hash

#     def get(self, name: str):
#         key = None
#         if name in self.nodes:
#             key = self.nodes[name]
#         elif name in self.generics:
#             key = self.generics[name]

#         if key:
#             return self._cache[key]

#         raise ValueError(f"Unable to find the schema '{name}' for the branch {self.name} in the registry")

#     def get_all(self):
#         return {self._cache[cache_key].kind: self._cache[cache_key] for cache_key in list(self.nodes.values()) + list(self.generics.values())}

#     def load(self, schema: SchemaRoot):
#         for item in schema.nodes + schema.generics:
#             self.set(name=item.kind, schema=item)

#         for node_extension in schema.extensions.nodes:
#             node = self.get(name=node_extension.kind)

#             for item in node_extension.attributes:
#                 node.attributes.append(item)
#             for item in node_extension.relationships:
#                 node.relationships.append(item)

#         return True

#     def process(self):
#         self.calculate_inheritance()

#         # Generate the filters for all nodes, at the NodeSchema and at the relationships level.
#         for node_name in self.nodes:
#             node_schema = self.get(name=node_name)
#             new_node = node_schema.duplicate()
#             new_node.filters = self.generate_filters(schema=new_node, top_level=True, include_relationships=True)

#             for rel in new_node.relationships:
#                 peer_schema = self.get(name=rel.peer)
#                 if not peer_schema:
#                     continue

#                 rel.filters = self.generate_filters(schema=peer_schema, top_level=False, include_relationships=False)
#             self.set(name=node_name, schema=new_node)

#     def calculate_inheritance(self) -> None:
#         """Extend all the nodes with the attributes and relationships
#         from the Interface objects defined in inherited_from.
#         """

#         # For all node_schema, add the attributes & relationships from the generic / interface
#         for name, node_hash in self.nodes.items():
#             node = self._cache[node_hash]
#             if not node.inherit_from:
#                 continue

#             new_node = node.duplicate()
#             for generic_kind in node.inherit_from:
#                 if generic_kind not in self.generics.keys():
#                     # TODO add a proper exception for all schema related issue
#                     raise ValueError(f"{node.kind} Unable to find the generic {generic_kind}")

#                 new_node.inherit_from_interface(interface=self.get(name=generic_kind))

#             self.set(name=name, schema=new_node)

#     @staticmethod
#     def generate_filters(
#         schema: NodeSchema, top_level: bool = False, include_relationships: bool = False
#     ) -> List[FilterSchema]:
#         """Generate the FilterSchema for a given NodeSchema object."""

#         filters = []

#         if top_level:
#             filters.append(FilterSchema(name="ids", kind=FilterSchemaKind.LIST))

#         else:
#             filters.append(FilterSchema(name="id", kind=FilterSchemaKind.TEXT))

#         for attr in schema.attributes:
#             if attr.kind in ["Text", "String"]:
#                 filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.TEXT)
#             elif attr.kind in ["Number", "Integer"]:
#                 filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.NUMBER)
#             elif attr.kind in ["Boolean", "Checkbox"]:
#                 filter = FilterSchema(name=f"{attr.name}__value", kind=FilterSchemaKind.BOOLEAN)
#             else:
#                 continue

#             if attr.enum:
#                 filter.enum = attr.enum

#             filters.append(filter)

#         if not include_relationships:
#             return filters

#         for rel in schema.relationships:
#             if rel.kind in ["Attribute", "Parent"]:
#                 filters.append(FilterSchema(name=f"{rel.name}__id", kind=FilterSchemaKind.OBJECT, object_kind=rel.peer))

#         return filters

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


async def test_schema_branch_get(default_branch):
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


async def test_schema_branch_process_filters(session, reset_registry, default_branch, register_internal_models_schema):
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
    schema_branch = SchemaRegistryBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    schema_branch.process()

    assert len(schema_branch.nodes) == 2
    assert len(schema_branch.generics) == 1
    assert len(schema_branch.groups) == 1

    schema_criticality = schema_branch.get("Criticality")

    assert not DeepDiff(
        schema1.nodes[0].dict(exclude={"filters", "relationships"}),
        schema_criticality.dict(exclude={"filters", "relationships"}),
        ignore_order=True,
    )
    assert not DeepDiff(
        schema1.generics[0].dict(exclude={"filters"}),
        schema_branch.get("GenericInterface").dict(exclude={"filters"}),
        ignore_order=True,
    )

    assert not DeepDiff(
        schema1.groups[0].dict(exclude={"filters"}),
        schema_branch.get("GenericGroup").dict(exclude={"filters"}),
        ignore_order=True,
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

    breakpoint()

    assert not DeepDiff(criticality_dict["filters"], expected_filters, ignore_order=True)
    assert not DeepDiff(criticality_dict["relationships"], expected_relationships, ignore_order=True)


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


async def test_schema_manager_get(default_branch):
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


# async def test_load_node_to_db_node_schema(session, default_branch):
#     schema = SchemaRoot(**internal_schema)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     SCHEMA = {
#         "name": "criticality",
#         "kind": "Criticality",
#         "default_filter": "name__value",
#         "attributes": [
#             {"name": "name", "kind": "Text", "unique": True},
#             {"name": "level", "kind": "Number"},
#             {"name": "color", "kind": "Text", "default_value": "#444444"},
#             {"name": "description", "kind": "Text", "optional": True},
#         ],
#     }
#     node = NodeSchema(**SCHEMA)
#     await SchemaManager.load_node_to_db(node=node, session=session)

#     assert True


# async def test_load_node_to_db_generic_schema(session, default_branch):
#     schema = SchemaRoot(**internal_schema)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     SCHEMA = {
#         "name": "generic_interface",
#         "kind": "GenericInterface",
#         "attributes": [
#             {"name": "my_generic_name", "kind": "Text"},
#         ],
#     }
#     node = GenericSchema(**SCHEMA)
#     await SchemaManager.load_node_to_db(node=node, session=session)

#     assert True


# async def test_load_node_to_db_group_schema(session, default_branch):
#     schema = SchemaRoot(**internal_schema)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     SCHEMA = {
#         "name": "generic_group",
#         "kind": "GenericGroup",
#     }

#     node = GroupSchema(**SCHEMA)
#     await SchemaManager.load_node_to_db(node=node, session=session)

#     assert True


# async def test_load_schema_to_db_internal_models(session, default_branch):
#     schema = SchemaRoot(**internal_schema)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     await SchemaManager.load_schema_to_db(schema=schema, session=session)

#     node_schema = registry.get_schema(name="NodeSchema")
#     results = await SchemaManager.query(schema=node_schema, session=session)
#     assert len(results) > 1


# async def test_load_schema_to_db_core_models(session, default_branch, register_internal_models_schema):
#     schema = SchemaRoot(**core_models)
#     await SchemaManager.register_schema_to_registry(schema=schema)

#     await SchemaManager.load_schema_to_db(schema=schema, session=session)

#     node_schema = registry.get_schema(name="GenericSchema")
#     results = await SchemaManager.query(schema=node_schema, session=session)
#     assert len(results) > 1


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


async def test_load_schema_from_db(session, reset_registry, default_branch, register_internal_models_schema):
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
