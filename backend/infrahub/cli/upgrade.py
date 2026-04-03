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
from infrahub.core.migrations.shared import get_migration_console, suppress_internal_logs
from infrahub.core.protocols import CoreAccount, CoreObjectPermission
from infrahub.dependencies.registry import build_component_registry
from infrahub.exceptions import DatabaseError
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

from .constants import ERROR_BADGE, FAILED_BADGE, SUCCESS_BADGE
from .db import (
    check_core_schema_diff,
    detect_migration_to_run,
    get_branches_needing_rebase,
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


async def validate_prerequisites(db: InfrahubDatabase) -> bool:
    """Validate that the database is reachable and initialized before starting upgrade."""
    try:
        await get_root_node(db=db)
        return True
    except DatabaseError as exc:
        console.log(f"{ERROR_BADGE} Database prerequisite check failed: {exc}")
        return False
    except Exception as exc:
        console.log(f"{ERROR_BADGE} Database is unreachable: {exc}")
        console.log(
            "  Verify that the database is running and that the connection settings in your configuration file are correct."
        )
        return False


@app.command(name="upgrade")
async def upgrade_cmd(
    ctx: typer.Context,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    check: bool = typer.Option(False, help="Check the state of the system without upgrading."),
    rebase_branches: bool = typer.Option(False, help="Rebase and apply migrations to branches if required."),
    interactive: bool = typer.Option(
        False, help="Use interactive prompt to accept or deny rebase of individual branches."
    ),
    verbose: bool = typer.Option(False, help="Show detailed internal output from migrations and rebase."),
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

    if not await validate_prerequisites(db=dbdriver):
        await dbdriver.close()
        raise typer.Exit(1)

    root_node = await get_root_node(db=dbdriver)

    if check:
        await _upgrade_check(db=dbdriver, root_node_graph_version=root_node.graph_version)
        await dbdriver.close()
        return

    await _upgrade_execute(
        db=dbdriver,
        root_node_graph_version=root_node.graph_version,
        rebase_branches=rebase_branches,
        interactive=interactive,
        verbose=verbose,
    )

    await dbdriver.close()


async def _upgrade_execute(
    db: InfrahubDatabase,
    root_node_graph_version: int,
    rebase_branches: bool = False,
    interactive: bool = False,
    verbose: bool = False,
) -> None:
    """Execute the full upgrade sequence with structured step output."""
    console.log("[bold]Step 1/6: Database migrations[/bold]")
    migrations = await detect_migration_to_run(current_graph_version=root_node_graph_version)

    if verbose:
        if not await migrate_database(db=db, initialize=False, migrations=migrations, verbose=verbose):
            console.log(f"Upgrade cancelled due to migration failure. {FAILED_BADGE}")
            return
    else:
        with suppress_internal_logs():
            if not await migrate_database(db=db, initialize=False, migrations=migrations, verbose=verbose):
                console.log(f"Upgrade cancelled due to migration failure. {FAILED_BADGE}")
                return

    console.log("[bold]Step 2/6: Internal schema[/bold]")
    await initialize_internal_schema()
    console.log("Internal schema initialized")

    console.log("[bold]Step 3/6: Core schema[/bold]")
    if verbose:
        await update_core_schema(db=db, initialize=False)
    else:
        with suppress_internal_logs():
            await update_core_schema(db=db, initialize=False)

    console.log("[bold]Step 4/6: Internal objects[/bold]")
    await upgrade_menu(db=db)
    await upgrade_permissions(db=db)

    console.log("[bold]Step 5/6: Task manager[/bold]")
    async with get_client(sync_client=False) as client:
        await setup_blocks()
        await setup_worker_pools(client=client)
        await setup_deployments(client=client)
        await trigger_configure_all()
    console.log("Task manager configured")

    console.log("[bold]Step 6/6: Branch rebase[/bold]")
    branches = await mark_branches_needing_rebase(db=db)
    plural = len(branches) != 1
    console.log(
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

        if verbose:
            await trigger_rebase_branches(db=db, branches=branches_to_rebase)
        else:
            with suppress_internal_logs():
                await trigger_rebase_branches(db=db, branches=branches_to_rebase)

    console.log(f"[bold]Upgrade complete[/bold] {SUCCESS_BADGE}")


async def _upgrade_check(db: InfrahubDatabase, root_node_graph_version: int) -> None:
    """Display comprehensive upgrade status without executing any changes."""
    console.log("[bold]Infrahub Upgrade Check[/bold]")

    console.log("\nDatabase:")
    console.log("  Reachable: yes")

    console.log("\nDatabase migrations:")
    migrations = await detect_migration_to_run(current_graph_version=root_node_graph_version)
    if not migrations:
        console.log("  Up to date, nothing to do")

    await initialize_internal_schema()

    console.log("\nCore schema:")
    try:
        has_diff = await check_core_schema_diff(db=db)
        if has_diff:
            console.log("  Schema has differences, update required")
        else:
            console.log("  Up to date, nothing to do")
    except Exception as exc:
        console.log(f"  Unable to check: {exc}")

    console.log("\nBranches:")
    branches = await get_branches_needing_rebase(db=db)
    if branches:
        branch_names = ", ".join(b.name for b in branches)
        noun = "branches" if len(branches) != 1 else "branch"
        verb = "need" if len(branches) != 1 else "needs"
        console.log(f"  {len(branches)} {noun} {verb} rebase: {branch_names}")
    else:
        console.log("  No branches need rebase")

    console.log("\nRun 'infrahub upgrade' to apply all changes.")


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
        console.log("Menu up to date, nothing to update")
        return

    await menu_repository.update_menu(existing_menu=menu_items, new_menu=default_menu_dict, menu_nodes=menu_nodes)
    console.log("Menu has been updated")


async def upgrade_permissions(db: InfrahubDatabase) -> None:
    existing_permissions = await NodeManager.query(schema=CoreObjectPermission, db=db, limit=1)
    if existing_permissions:
        console.log("Permissions up to date, nothing to update")
        return

    await setup_permissions(db=db)
    console.log("Permissions have been updated")


async def setup_permissions(db: InfrahubDatabase) -> None:
    existing_accounts = await NodeManager.query(schema=CoreAccount, db=db, limit=1)
    await create_default_account_groups(db=db, admin_accounts=existing_accounts)

    if config.SETTINGS.main.allow_anonymous_access:
        await create_anonymous_role(db=db)
