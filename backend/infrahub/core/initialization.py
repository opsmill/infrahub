import logging

from neo4j import AsyncSession

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import SchemaManager
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.models import infrastructure_models

LOGGER = logging.getLogger("infrahub")


async def initialization(session: AsyncSession):
    # pylint: disable=import-outside-toplevel

    # ---------------------------------------------------
    # Load all existing branches into the registry
    # ---------------------------------------------------
    branches = await Branch.get_list(session=session)
    for branch in branches:
        registry.branch[branch.name] = branch

    # ---------------------------------------------------
    # Load all schema in the database into the registry
    # ---------------------------------------------------
    schema = SchemaRoot(**internal_schema)
    await SchemaManager.register_schema_to_registry(schema)

    schema = await SchemaManager.load_schema_from_db(session=session)
    await SchemaManager.register_schema_to_registry(schema=schema)

    # ---------------------------------------------------
    # Load internal models into the registry
    # ---------------------------------------------------
    from infrahub.core.node import Node

    registry.node["Node"] = Node

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


async def create_default_branch(session: AsyncSession) -> Branch:
    default_branch = Branch(
        name=config.SETTINGS.main.default_branch,
        status="OPEN",
        description="Default Branch",
        is_default=True,
        is_data_only=False,
    )
    await default_branch.save(session=session)
    registry.branch[default_branch.name] = default_branch

    LOGGER.info(f"Created default branch : {default_branch.name}")

    return default_branch


async def create_branch(branch_name: str, session: AsyncSession) -> Branch:
    branch = Branch(name=branch_name, status="OPEN", description=f"Branch {branch_name}", is_default=False)
    await branch.save(session=session)
    registry.branch[branch.name] = branch

    LOGGER.info(f"Created branch : {branch.name}")

    return branch


async def first_time_initialization(session: AsyncSession, load_infrastructure_models: bool = True):
    # pylint: disable=import-outside-toplevel
    from infrahub.core.node import Node

    # --------------------------------------------------
    # Create the default Branch
    # --------------------------------------------------
    await create_default_branch(session=session)

    # --------------------------------------------------
    # Load the internal schema in the database
    # --------------------------------------------------
    schema = SchemaRoot(**internal_schema)
    schema.extend_nodes_with_interfaces()
    await SchemaManager.register_schema_to_registry(schema)
    await SchemaManager.load_schema_to_db(schema, session=session)
    LOGGER.info("Created the internal Schema in the database")

    # --------------------------------------------------
    # Load the schema for the common models in the database
    # --------------------------------------------------
    schema = SchemaRoot(**core_models)
    schema.extend_nodes_with_interfaces()
    await SchemaManager.register_schema_to_registry(schema)
    await SchemaManager.load_schema_to_db(schema, session=session)
    LOGGER.info("Created the core models in the database")

    if load_infrastructure_models:
        schema = SchemaRoot(**infrastructure_models)
        schema.extend_nodes_with_interfaces()
        await SchemaManager.register_schema_to_registry(schema)
        await SchemaManager.load_schema_to_db(schema, session=session)
        LOGGER.info("Created the infrastructure models in the database")

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
    await obj.new(session=session, name="admin", type="User", groups=[admin_grp])
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
