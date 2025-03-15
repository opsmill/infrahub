from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import typer
from deepdiff import DeepDiff
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client
from rich import print as rprint

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import (
    create_anonymous_role,
    create_default_roles,
    create_super_administrator_role,
    create_super_administrators_group,
    initialize_registry,
)
from infrahub.core.manager import NodeManager
from infrahub.menu.menu import default_menu
from infrahub.menu.models import MenuDict
from infrahub.menu.utils import create_default_menu, get_existing_menu, update_menu
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.local import BusSimulator
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.initialization import (
    setup_blocks,
    setup_deployments,
    setup_task_manager,
    setup_worker_pools,
)

from .db import initialize_internal_schema, migrate_database, update_core_schema

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext
    from infrahub.database import InfrahubDatabase

app = AsyncTyper()


@app.command(name="upgrade")
async def upgrade_cmd(
    ctx: typer.Context,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    check: bool = typer.Option(False, help="Check the state of the system without upgrading."),
) -> None:
    """Upgrade Infrahub to the latest version."""

    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)
    os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    service = await InfrahubServices.new(
        database=dbdriver, message_bus=BusSimulator(), workflow=WorkflowLocalExecution()
    )
    await initialize_registry(db=dbdriver)

    # NOTE add step to validate if the database and the task manager are reachable

    # -------------------------------------------
    # Add pre-upgrade  validation
    # -------------------------------------------

    # -------------------------------------------
    # Upgrade Infrahub Database and Schema
    # -------------------------------------------
    await migrate_database(db=dbdriver, initialize=False, check=check)

    await initialize_internal_schema()
    await update_core_schema(db=dbdriver, service=service, initialize=False)

    # -------------------------------------------
    # Upgrade Internal Objects, generated and managed by Infrahub
    # -------------------------------------------
    await upgrade_menu(db=dbdriver)
    await upgrade_permissions(db=dbdriver)

    # -------------------------------------------
    # Upgrade External system : Task Manager
    # -------------------------------------------
    await setup_task_manager()

    async with get_client(sync_client=False) as client:
        await setup_blocks()
        await setup_worker_pools(client=client)
        await setup_deployments(client=client)
        # await setup_triggers(
        #     client=client,
        #     triggers=builtin_triggers,
        #     trigger_type=TriggerType.BUILTIN,
        # )

    await dbdriver.close()


async def upgrade_menu(db: InfrahubDatabase) -> None:
    menu_nodes = await get_existing_menu(db=db)
    menu_items = await MenuDict.from_db(db=db, nodes=list(menu_nodes.values()))
    default_menu_dict = MenuDict.from_definition_list(default_menu)

    if not menu_nodes:
        await create_default_menu(db=db)
        return

    diff_menu = DeepDiff(menu_items.to_rest(), default_menu_dict.to_rest(), ignore_order=True)

    if not diff_menu:
        rprint("Menu Up to date, nothing to update")
        return

    await update_menu(db=db, existing_menu=menu_items, new_menu=default_menu_dict, menu_nodes=menu_nodes)
    rprint("Menu has been updated")


async def upgrade_permissions(db: InfrahubDatabase) -> None:
    existing_permissions = await NodeManager.query(
        schema=InfrahubKind.OBJECTPERMISSION,
        db=db,
        limit=1,
    )
    if existing_permissions:
        rprint("Permissions Up to date, nothing to update")
        return

    await setup_permissions(db=db)
    rprint("Permissions have been updated")


async def setup_permissions(db: InfrahubDatabase) -> None:
    existing_accounts = await NodeManager.query(
        schema=InfrahubKind.ACCOUNT,
        db=db,
        limit=1,
    )
    administrator_role = await create_super_administrator_role(db=db)
    await create_super_administrators_group(db=db, role=administrator_role, admin_accounts=existing_accounts)
    await create_default_roles(db=db)

    if config.SETTINGS.main.allow_anonymous_access:
        await create_anonymous_role(db=db)
