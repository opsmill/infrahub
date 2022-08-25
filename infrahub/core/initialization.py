import logging

import infrahub.config as config
from infrahub.core import get_branch, registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager, SchemaManager
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.models import infrastructure_models

LOGGER = logging.getLogger("infrahub")


def initialization():

    # ---------------------------------------------------
    # Load all existing branches into the registry
    # ---------------------------------------------------
    branches = Branch.get_list()
    for branch in branches:
        registry.branch[branch.name] = branch

    # ---------------------------------------------------
    # Load all schema in the database into the registry
    # ---------------------------------------------------
    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)

    schema = SchemaManager.load_schema_from_db()
    SchemaManager.register_schema_to_registry(schema)

    # ---------------------------------------------------
    # Load internal models into the registry
    # ---------------------------------------------------
    from infrahub.core.node import Node
    from infrahub.core.repository import Repository
    from infrahub.core.rfile import RFile

    registry.node["RFile"] = RFile
    registry.node["Node"] = Node
    registry.node["Repository"] = Repository

    # ---------------------------------------------------
    # Load all existing Groups into the registry
    # ---------------------------------------------------
    group_schema = registry.get_schema("Group")
    groups = NodeManager.query(group_schema)
    for group in groups:
        registry.node_group[group.name.value] = group

    # groups = AttrGroup.get_list()
    # for group in groups:
    #     registry.attr_group[group.name.value] = group


def create_default_branch():

    default_branch = Branch(
        name=config.SETTINGS.main.default_branch, status="OPEN", description="Default Branch", is_default=True
    )
    default_branch.save()
    registry.branch[default_branch.name] = default_branch

    LOGGER.info(f"Created default branch : {default_branch.name}")

    return default_branch


def create_branch(branch_name):

    branch = Branch(name=branch_name, status="OPEN", description=f"Branch {branch_name}", is_default=False)
    branch.save()
    registry.branch[branch.name] = branch

    LOGGER.info(f"Created branch : {branch.name}")

    return branch


def first_time_initialization():

    from infrahub.core.node import Node

    # --------------------------------------------------
    # Create the default Branch
    # --------------------------------------------------
    create_default_branch()

    # --------------------------------------------------
    # Load the internal schema in the database
    # --------------------------------------------------
    schema = SchemaRoot(**internal_schema)
    SchemaManager.register_schema_to_registry(schema)
    SchemaManager.load_schema_to_db(schema)
    LOGGER.info(f"Created the internal Schema in the database")

    # --------------------------------------------------
    # Load the schema for the common models in the database
    # --------------------------------------------------
    schema = SchemaRoot(**core_models)
    SchemaManager.register_schema_to_registry(schema)
    SchemaManager.load_schema_to_db(schema)
    LOGGER.info(f"Created the core models in the database")

    schema = SchemaRoot(**infrastructure_models)
    SchemaManager.register_schema_to_registry(schema)
    SchemaManager.load_schema_to_db(schema)
    LOGGER.info(f"Created the infrastructure models in the database")

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

    criticality_schema = registry.get_schema("Criticality")
    for level in CRITICALITY_LEVELS:
        obj = Node(criticality_schema).new(name=level[0], level=level[1]).save()

    # ----
    group_schema = registry.get_schema("Group")
    account_schema = registry.get_schema("Account")
    admin_grp = obj = Node(group_schema).new(name="admin").save()
    default_grp = obj = Node(group_schema).new(name="default").save()

    obj = Node(account_schema).new(name="admin", type="USER", groups=[admin_grp]).save()
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
