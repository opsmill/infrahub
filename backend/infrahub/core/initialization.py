import logging

from neo4j import AsyncSession

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.artifact import CoreArtifactDefinition
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.models import NodeSchema as NodeSchemaModel
from infrahub.core.models import RelationshipSchema as RelationshipSchemaModel
from infrahub.core.node import Node
from infrahub.core.root import Root
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema_manager import SchemaManager
from infrahub.exceptions import DatabaseError
from infrahub.storage.local import InfrahubLocalStorage

LOGGER = logging.getLogger("infrahub")


async def initialization(session: AsyncSession):
    if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
        await session.run(query="STORAGE MODE IN_MEMORY_ANALYTICAL")

    # ---------------------------------------------------
    # Load the Root node
    # ---------------------------------------------------
    roots = await Root.get_list(session=session)
    if len(roots) == 0:
        raise DatabaseError("Database hasn't been initialized yet. please run 'infrahub db init'")
    if len(roots) > 1:
        raise DatabaseError("Database is corrupted, more than 1 root node found.")
    registry.id = roots[0].uuid

    # ---------------------------------------------------
    # Initialize the Storage Driver
    # ---------------------------------------------------
    if config.SETTINGS.storage.driver == config.StorageDriver.LOCAL:
        registry.storage = await InfrahubLocalStorage.init(settings=config.SETTINGS.storage.settings)

    # ---------------------------------------------------
    # Load all existing branches into the registry
    # ---------------------------------------------------
    branches = await Branch.get_list(session=session)
    for branch in branches:
        registry.branch[branch.name] = branch

    # ---------------------------------------------------
    # Load all schema in the database into the registry
    #  ... Unless the schema has been initialized already
    # ---------------------------------------------------
    if not registry.schema_has_been_initialized():
        registry.schema = SchemaManager()
        schema = SchemaRoot(**internal_schema)
        registry.schema.register_schema(schema=schema)

        for branch in branches:
            await registry.schema.load_schema_from_db(session=session, branch=branch)

    # ---------------------------------------------------
    # Load internal models into the registry
    # ---------------------------------------------------

    registry.node["Node"] = Node
    registry.node["CoreArtifactDefinition"] = CoreArtifactDefinition
    registry.node["NodeSchema"] = NodeSchemaModel
    registry.node["RelationshipSchema"] = RelationshipSchemaModel

    # ---------------------------------------------------
    # Load all existing Groups into the registry
    # ---------------------------------------------------
    # group_schema = await registry.get_schema(session=session, name="Group")
    # groups = await NodeManager.query(group_schema, session=session)
    # for group in groups:
    #     registry.node_group[group.name.value] = group

    # groups = AttrGroup.get_list()
    # for group in groups:
    #     registry.attr_group[group.name.value] = group


async def create_root_node(session: AsyncSession) -> Root:
    root = Root()
    await root.save(session=session)
    LOGGER.info(f"Generated instance ID : {root.uuid}")

    registry.id = root.id

    return root


async def create_default_branch(session: AsyncSession) -> Branch:
    branch = Branch(
        name=config.SETTINGS.main.default_branch,
        status="OPEN",
        description="Default Branch",
        hierarchy_level=1,
        is_default=True,
        is_data_only=False,
    )
    await branch.save(session=session)
    registry.branch[branch.name] = branch

    LOGGER.info(f"Created default branch : {branch.name}")

    return branch


async def create_global_branch(session: AsyncSession) -> Branch:
    branch = Branch(
        name=GLOBAL_BRANCH_NAME,
        status="OPEN",
        description="Global Branch",
        hierarchy_level=1,
        is_global=True,
        is_data_only=False,
    )
    await branch.save(session=session)
    registry.branch[branch.name] = branch

    LOGGER.info(f"Created global branch : {branch.name}")

    return branch


async def create_branch(branch_name: str, session: AsyncSession, description: str = "") -> Branch:
    """Create a new Branch, currently all the branches are based on Main

    Because all branches are based on main, the hierarchy_level of hardcoded to 2."""
    description = description or f"Branch {branch_name}"
    branch = Branch(name=branch_name, status="OPEN", hierarchy_level=2, description=description, is_default=False)

    origin_schema = registry.schema.get_schema_branch(name=branch.origin_branch)
    new_schema = origin_schema.duplicate(name=branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=new_schema)

    branch.update_schema_hash()
    await branch.save(session=session)
    registry.branch[branch.name] = branch

    LOGGER.info(f"Created branch : {branch.name}")

    return branch


async def first_time_initialization(session: AsyncSession):
    # --------------------------------------------------
    # Create the default Branch
    # --------------------------------------------------
    await create_root_node(session=session)
    default_branch = await create_default_branch(session=session)
    await create_global_branch(session=session)

    # --------------------------------------------------
    # Load the internal and core schema in the database
    # --------------------------------------------------
    registry.schema = SchemaManager()
    schema = SchemaRoot(**internal_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, session=session)

    if default_branch.update_schema_hash():
        await default_branch.save(session=session)

    LOGGER.info("Created the Schema in the database")

    # --------------------------------------------------
    # Create Default Users and Groups
    # --------------------------------------------------
    CRITICALITY_LEVELS = (
        # ("negligible", 1),
        ("low", 2),
        ("medium", 3),
        ("high", 4),
        # ("very high", 5),
        # ("critical", 6),
        # ("very critical", 7),
    )

    criticality_schema = registry.get_schema(name="BuiltinCriticality")
    for level in CRITICALITY_LEVELS:
        obj = await Node.init(session=session, schema=criticality_schema)
        await obj.new(session=session, name=level[0], level=level[1])
        await obj.save(session=session)

    token_schema = registry.get_schema(name="InternalAccountToken")
    # admin_grp = await Node.init(session=session, schema=group_schema)
    # await admin_grp.new(session=session, name="admin")
    # await admin_grp.save(session=session)
    # ----
    # group_schema = registry.get_schema(name="Group")

    # admin_grp = await Node.init(session=session, schema=group_schema)
    # await admin_grp.new(session=session, name="admin")
    # await admin_grp.save(session=session)
    # default_grp = obj = Node(group_schema).new(name="default").save()
    # account_schema = registry.get_schema(name="Account")
    obj = await Node.init(session=session, schema="CoreAccount")
    await obj.new(
        session=session,
        name="admin",
        type="User",
        role="admin",
        password=config.SETTINGS.security.initial_admin_password,
        # groups=[admin_grp],
    )
    await obj.save(session=session)
    LOGGER.info(f"Created Account: {obj.name.value}")

    if config.SETTINGS.security.initial_admin_token:
        token = await Node.init(session=session, schema=token_schema)
        await token.new(
            session=session,
            token=config.SETTINGS.security.initial_admin_token,
            account=obj,
        )
        await token.save(session=session)
