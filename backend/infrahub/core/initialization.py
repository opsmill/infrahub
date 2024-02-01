from typing import List, Optional

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.node import Node
from infrahub.core.root import Root
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema_manager import SchemaManager
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import DatabaseError
from infrahub.log import get_logger
from infrahub.storage import InfrahubObjectStorage

log = get_logger()


async def get_root_node(db: InfrahubDatabase, initialize: bool = False) -> Root:
    roots = await Root.get_list(db=db)
    if len(roots) == 0 and not initialize:
        raise DatabaseError(
            "The Database hasn't been initialized for Infrahub, please run 'infrahub db init' or 'infrahub server start' to initialize the database."
        )

    if len(roots) == 0:
        await first_time_initialization(db=db)
        roots = await Root.get_list(db=db)

    elif len(roots) > 1:
        raise DatabaseError("The Database is corrupted, more than 1 root node found.")

    return roots[0]


async def initialization(db: InfrahubDatabase):
    if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
        session = await db.session()
        await session.run(query="SET DATABASE SETTING 'log.level' TO 'INFO'")
        await session.run(query="SET DATABASE SETTING 'log.to_stderr' TO 'true'")
        await session.run(query="STORAGE MODE IN_MEMORY_ANALYTICAL")

    # ---------------------------------------------------
    # Initialize the database and Load the Root node
    # ---------------------------------------------------
    async with lock.registry.initialization():
        log.debug("Checking Root Node")

        root = await get_root_node(db=db, initialize=True)
        registry.id = root.uuid

    # ---------------------------------------------------
    # Initialize the Storage Driver
    # ---------------------------------------------------
    registry.storage = await InfrahubObjectStorage.init(settings=config.SETTINGS.storage)

    # ---------------------------------------------------
    # Load all existing branches into the registry
    # ---------------------------------------------------
    branches: List[Branch] = await Branch.get_list(db=db)
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

        # Import the default branch
        default_branch: Branch = registry.branch[config.SETTINGS.main.default_branch]
        hash_in_db = default_branch.schema_hash.main
        await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        if default_branch.update_schema_hash():
            log.warning(
                f"New schema detected after pulling the schema from the db :"
                f" {hash_in_db!r} >> {default_branch.schema_hash.main!r}",
                branch=default_branch.name,
            )

        for branch in branches:
            if branch.name in [default_branch.name, GLOBAL_BRANCH_NAME]:
                continue

            hash_in_db = branch.schema_hash.main
            log.info("Importing schema", branch=branch.name)
            await registry.schema.load_schema(db=db, branch=branch)

            if branch.update_schema_hash():
                log.warning(
                    f"New schema detected after pulling the schema from the db :"
                    f" {hash_in_db!r} >> {branch.schema_hash.main!r}",
                    branch=branch.name,
                )

    # ---------------------------------------------------
    # Load internal models into the registry
    # ---------------------------------------------------

    registry.node["Node"] = Node

    # ---------------------------------------------------
    # Load all existing Groups into the registry
    # ---------------------------------------------------
    # group_schema = await registry.schema.get(db=db, name="Group")
    # groups = await NodeManager.query(group_schema, db=db)
    # for group in groups:
    #     registry.node_group[group.name.value] = group

    # groups = AttrGroup.get_list()
    # for group in groups:
    #     registry.attr_group[group.name.value] = group


async def create_root_node(db: InfrahubDatabase) -> Root:
    root = Root(graph_version=GRAPH_VERSION)
    await root.save(db=db)
    log.info(f"Generated instance ID : {root.uuid} (v{GRAPH_VERSION})")

    registry.id = root.id

    return root


async def create_default_branch(db: InfrahubDatabase) -> Branch:
    branch = Branch(
        name=config.SETTINGS.main.default_branch,
        status="OPEN",
        description="Default Branch",
        hierarchy_level=1,
        is_default=True,
        is_data_only=False,
    )
    await branch.save(db=db)
    registry.branch[branch.name] = branch

    log.info("Created default branch", branch=branch.name)

    return branch


async def create_global_branch(db: InfrahubDatabase) -> Branch:
    branch = Branch(
        name=GLOBAL_BRANCH_NAME,
        status="OPEN",
        description="Global Branch",
        hierarchy_level=1,
        is_global=True,
        is_data_only=False,
    )
    await branch.save(db=db)
    registry.branch[branch.name] = branch

    log.info("Created global branch", branch=branch.name)

    return branch


async def create_branch(
    branch_name: str, db: InfrahubDatabase, description: str = "", at: Optional[str] = None
) -> Branch:
    """Create a new Branch, currently all the branches are based on Main

    Because all branches are based on main, the hierarchy_level of hardcoded to 2."""
    description = description or f"Branch {branch_name}"
    branch = Branch(
        name=branch_name,
        status="OPEN",
        hierarchy_level=2,
        description=description,
        is_default=False,
        created_at=at,
        branched_from=at,
    )

    origin_schema = registry.schema.get_schema_branch(name=branch.origin_branch)
    new_schema = origin_schema.duplicate(name=branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=new_schema)

    branch.update_schema_hash()
    await branch.save(db=db)
    registry.branch[branch.name] = branch

    log.info("Created branch", branch=branch.name)

    return branch


async def first_time_initialization(db: InfrahubDatabase):
    # --------------------------------------------------
    # Create the default Branch
    # --------------------------------------------------
    await create_root_node(db=db)
    default_branch = await create_default_branch(db=db)
    await create_global_branch(db=db)

    # --------------------------------------------------
    # Load the internal and core schema in the database
    # --------------------------------------------------
    registry.schema = SchemaManager()
    schema = SchemaRoot(**internal_schema)
    schema_branch = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, db=db)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    log.info("Created the Schema in the database")

    # --------------------------------------------------
    # Create Default Users and Groups
    # --------------------------------------------------
    token_schema = registry.schema.get(name=InfrahubKind.ACCOUNTTOKEN)
    obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await obj.new(
        db=db,
        name="admin",
        type="User",
        role="admin",
        password=config.SETTINGS.security.initial_admin_password,
        # groups=[admin_grp],
    )
    await obj.save(db=db)
    log.info(f"Created Account: {obj.name.value}", account_name=obj.name.value)

    if config.SETTINGS.security.initial_admin_token:
        token = await Node.init(db=db, schema=token_schema)
        await token.new(
            db=db,
            token=config.SETTINGS.security.initial_admin_token,
            account=obj,
        )
        await token.save(db=db)
