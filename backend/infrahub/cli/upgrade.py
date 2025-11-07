from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import typer
from deepdiff import DeepDiff
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client

from infrahub import config
from infrahub.core.initialization import (
    create_anonymous_role,
    create_default_account_groups,
    get_root_node,
    initialize_registry,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import get_migration_console
from infrahub.core.protocols import CoreAccount, CoreObjectPermission
from infrahub.dependencies.registry import build_component_registry
from infrahub.lock import initialize_lock
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

from .db import (
    detect_migration_to_run,
    initialize_internal_schema,
    mark_branches_needing_rebase,
    migrate_database,
    trigger_rebase_branches,
    update_core_schema,
)

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext
    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase

app = AsyncTyper()
console = get_migration_console()


@app.command(name="upgrade")
async def upgrade_cmd(
    ctx: typer.Context,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    check: bool = typer.Option(False, help="Check the state of the system without upgrading."),
    rebase_branches: bool = typer.Option(False, help="Rebase and apply migrations to branches if required."),
    interactive: bool = typer.Option(
        False, help="Use interactive prompt to accept or deny rebase of individual branches."
    ),
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
    initialize_lock()

    build_component_registry()

    root_node = await get_root_node(db=dbdriver)

    # NOTE add step to validate if the database and the task manager are reachable

    # -------------------------------------------
    # Add pre-upgrade  validation
    # -------------------------------------------

    # -------------------------------------------
    # Upgrade Infrahub Database and Schema
    # -------------------------------------------

    migrations = await detect_migration_to_run(current_graph_version=root_node.graph_version)
    if check:
        await dbdriver.close()
        return

    if not await migrate_database(db=dbdriver, initialize=False, migrations=migrations):
        # A migration failed, stop the upgrade process
        console.log("Upgrade cancelled due to migration failure.")
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

    # -------------------------------------------
    # Perform branch rebase and apply migrations to them
    # -------------------------------------------
    branches = await mark_branches_needing_rebase(db=dbdriver)
    plural = len(branches) != 1
    get_migration_console().log(
        f"Found {len(branches)} {'branches' if plural else 'branch'} that {'need' if plural else 'needs'} to be rebased"
    )

    if rebase_branches:
        branches_to_rebase: list[Branch] = []
        if not interactive:
            branches_to_rebase = branches
        else:
            for branch in branches:
                if typer.confirm(f"Rebase branch {branch.name}?"):
                    branches_to_rebase.append(branch)

        await trigger_rebase_branches(db=dbdriver, branches=branches_to_rebase)

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
        console.log("Menu Up to date, nothing to update")
        return

    await menu_repository.update_menu(existing_menu=menu_items, new_menu=default_menu_dict, menu_nodes=menu_nodes)
    console.log("Menu has been updated")


async def upgrade_permissions(db: InfrahubDatabase) -> None:
    existing_permissions = await NodeManager.query(schema=CoreObjectPermission, db=db, limit=1)
    if existing_permissions:
        console.log("Permissions Up to date, nothing to update")
        return

    await setup_permissions(db=db)
    console.log("Permissions have been updated")


async def setup_permissions(db: InfrahubDatabase) -> None:
    existing_accounts = await NodeManager.query(schema=CoreAccount, db=db, limit=1)
    await create_default_account_groups(db=db, admin_accounts=existing_accounts)

    if config.SETTINGS.main.allow_anonymous_access:
        await create_anonymous_role(db=db)
