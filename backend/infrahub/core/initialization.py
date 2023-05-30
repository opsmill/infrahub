import logging

from neo4j import AsyncSession

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import SchemaManager
from infrahub.core.models import NodeSchema as NodeSchemaModel
from infrahub.core.models import RelationshipSchema as RelationshipSchemaModel
from infrahub.core.node import Node
from infrahub.core.root import Root
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.exceptions import DatabaseError

LOGGER = logging.getLogger("infrahub")


async def initialization(session: AsyncSession):
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
    # Load all existing branches into the registry
    # ---------------------------------------------------
    branches = await Branch.get_list(session=session)
    for branch in branches:
        registry.branch[branch.name] = branch

    # ---------------------------------------------------
    # Load all schema in the database into the registry
    #  ... Unless the schema has been initialized already
    # ---------------------------------------------------
    if not registry.schema:
        registry.schema = SchemaManager()
        schema = SchemaRoot(**internal_schema)
        registry.schema.register_schema(schema=schema)

        for branch in branches:
            await registry.schema.load_schema_from_db(session=session, branch=branch)

    # ---------------------------------------------------
    # Load internal models into the registry
    # ---------------------------------------------------

    registry.node["Node"] = Node
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
    default_branch = Branch(
        name=config.SETTINGS.main.default_branch,
        status="OPEN",
        description="Default Branch",
        hierarchy_level=1,
        is_default=True,
        is_data_only=False,
    )
    await default_branch.save(session=session)
    registry.branch[default_branch.name] = default_branch

    LOGGER.info(f"Created default branch : {default_branch.name}")

    return default_branch


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

    criticality_schema = registry.get_schema(name="Criticality")
    for level in CRITICALITY_LEVELS:
        obj = await Node.init(session=session, schema=criticality_schema)
        await obj.new(session=session, name=level[0], level=level[1])
        await obj.save(session=session)

    # ----
    group_schema = registry.get_schema(name="Group")
    account_schema = registry.get_schema(name="Account")
    admin_grp = await Node.init(session=session, schema=group_schema)
    await admin_grp.new(session=session, name="admin")
    await admin_grp.save(session=session)
    # default_grp = obj = Node(group_schema).new(name="default").save()

    obj = await Node.init(session=session, schema=account_schema)
    await obj.new(
        session=session,
        name="admin",
        type="User",
        password=config.SETTINGS.security.initial_admin_password,
        groups=[admin_grp],
    )
    await obj.save(session=session)
    LOGGER.info(f"Created Account: {obj.name.value}")

    # # FIXME Remove these hardcoded Token Value
    # token = AccountToken.init(token=obj.name.value)
    # token.save()
    # obj.add_token(token)

    # admin_grp.add_account(obj)

    # obj = Account.init(name="default", type="USER")
    # obj.save()
    # LOGGER.debug(f"Created Account: {obj.name.value}")

    # token = AccountToken.init(token=obj.name.value)
    # token.save()
    # obj.add_token(token)

    # default_grp.add_account(obj)
