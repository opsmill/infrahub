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
from infrahub.core.initialization import create_anonymous_role, create_default_account_groups, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccount, CoreObjectPermission
from infrahub.dependencies.registry import build_component_registry
from infrahub.menu.menu import default_menu
from infrahub.menu.models import MenuDict
from infrahub.menu.repository import MenuRepository
from infrahub.menu.utils import create_default_menu
from infrahub.trigger.tasks import trigger_configure_all
from infrahub.workflows.initialization import (
    setup_blocks,
    setup_deployments,
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

    await initialize_registry(db=dbdriver)

    build_component_registry()

    # NOTE add step to validate if the database and the task manager are reachable

    # -------------------------------------------
    # Add pre-upgrade  validation
    # -------------------------------------------

    # -------------------------------------------
    # Upgrade Infrahub Database and Schema
    # -------------------------------------------

    if not await migrate_database(db=dbdriver, initialize=False, check=check):
        # A migration failed, stop the upgrade process
        rprint("Upgrade cancelled due to migration failure.")
        await dbdriver.close()
        return

    await initialize_internal_schema()
    await update_core_schema(db=dbdriver, initialize=False)

    # -------------------------------------------
    # Upgrade Internal Objects, generated and managed by Infrahub
    # -------------------------------------------
    await upgrade_menu(db=dbdriver)
    await upgrade_permissions(db=dbdriver)

    # -------------------------------------------
    # Upgrade External system : Task Manager
    # -------------------------------------------
    async with get_client(sync_client=False) as client:
        await setup_blocks()
        await setup_worker_pools(client=client)
        await setup_deployments(client=client)
        await trigger_configure_all()

    await dbdriver.close()


async def upgrade_menu(db: InfrahubDatabase) -> None:
    menu_repository = MenuRepository(db=db)
    menu_nodes = await menu_repository.get_menu_db()
    menu_items = await menu_repository.get_menu(nodes=menu_nodes)
    default_menu_dict = MenuDict.from_definition_list(default_menu)

    if not menu_nodes:
        await create_default_menu(db=db)
        return

    diff_menu = DeepDiff(menu_items.to_rest(), default_menu_dict.to_rest(), ignore_order=True)

    if not diff_menu:
        rprint("Menu Up to date, nothing to update")
        return

    await menu_repository.update_menu(existing_menu=menu_items, new_menu=default_menu_dict, menu_nodes=menu_nodes)
    rprint("Menu has been updated")


async def upgrade_permissions(db: InfrahubDatabase) -> None:
    existing_permissions = await NodeManager.query(schema=CoreObjectPermission, db=db, limit=1)
    if existing_permissions:
        rprint("Permissions Up to date, nothing to update")
        return

    await setup_permissions(db=db)
    rprint("Permissions have been updated")


async def setup_permissions(db: InfrahubDatabase) -> None:
    existing_accounts = await NodeManager.query(schema=CoreAccount, db=db, limit=1)
    await create_default_account_groups(db=db, admin_accounts=existing_accounts)

    if config.SETTINGS.main.allow_anonymous_access:
        await create_anonymous_role(db=db)
