from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from infrahub_sdk.async_typer import AsyncTyper
from rich import print as rprint

from infrahub import config
from infrahub.patch.edge_adder import PatchPlanEdgeAdder
from infrahub.patch.edge_deleter import PatchPlanEdgeDeleter
from infrahub.patch.edge_updater import PatchPlanEdgeUpdater
from infrahub.patch.plan_reader import PatchPlanReader
from infrahub.patch.plan_writer import PatchPlanWriter
from infrahub.patch.queries.base import PatchQuery
from infrahub.patch.runner import (
    PatchPlanEdgeDbIdTranslator,
    PatchRunner,
)
from infrahub.patch.vertex_adder import PatchPlanVertexAdder
from infrahub.patch.vertex_deleter import PatchPlanVertexDeleter
from infrahub.patch.vertex_updater import PatchPlanVertexUpdater

from .constants import ERROR_BADGE, SUCCESS_BADGE

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext
    from infrahub.database import InfrahubDatabase


patch_app = AsyncTyper(help="Commands for planning, applying, and reverting database patches")


def get_patch_runner(db: InfrahubDatabase) -> PatchRunner:
    return PatchRunner(
        plan_writer=PatchPlanWriter(),
        plan_reader=PatchPlanReader(),
        edge_db_id_translator=PatchPlanEdgeDbIdTranslator(),
        vertex_adder=PatchPlanVertexAdder(db=db),
        vertex_deleter=PatchPlanVertexDeleter(db=db),
        vertex_updater=PatchPlanVertexUpdater(db=db),
        edge_adder=PatchPlanEdgeAdder(db=db),
        edge_deleter=PatchPlanEdgeDeleter(db=db),
        edge_updater=PatchPlanEdgeUpdater(db=db),
    )


@patch_app.command(name="plan")
async def plan_patch_cmd(
    ctx: typer.Context,
    patch_path: str = typer.Argument(
        help="Path to the file containing the PatchQuery instance to run. Use Python-style dot paths, such as infrahub.cli.patch.queries.base"
    ),
    patch_plans_dir: Path = typer.Option(Path("infrahub-patches"), help="Path to patch plans directory"),  # noqa: B008
    apply: bool = typer.Option(False, help="Apply the patch immediately after creating it"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Create a plan for a given patch and save it in the patch plans directory to be applied/reverted"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    patch_module = importlib.import_module(patch_path)
    patch_query_class = None
    patch_query_class_count = 0
    for _, cls in inspect.getmembers(patch_module, inspect.isclass):
        if issubclass(cls, PatchQuery) and cls is not PatchQuery:
            patch_query_class = cls
            patch_query_class_count += 1

    patch_query_path = f"{PatchQuery.__module__}.{PatchQuery.__name__}"
    if patch_query_class is None:
        rprint(f"{ERROR_BADGE} No subclass of {patch_query_path} found in {patch_path}")
        raise typer.Exit(1)
    if patch_query_class_count > 1:
        rprint(
            f"{ERROR_BADGE} Multiple subclasses of {patch_query_path} found in {patch_path}. Please only define one per file."
        )
        raise typer.Exit(1)

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    patch_query_instance = patch_query_class(db=dbdriver)
    async with dbdriver.start_session() as db:
        patch_runner = get_patch_runner(db=db)
        patch_plan_dir = await patch_runner.prepare_plan(patch_query_instance, directory=Path(patch_plans_dir))
        rprint(f"{SUCCESS_BADGE} Patch plan created at {patch_plan_dir}")
        if apply:
            await patch_runner.apply(patch_plan_directory=patch_plan_dir)
            rprint(f"{SUCCESS_BADGE} Patch plan successfully applied")

    await dbdriver.close()


@patch_app.command(name="apply")
async def apply_patch_cmd(
    ctx: typer.Context,
    patch_plan_dir: Path = typer.Argument(help="Path to the directory containing a patch plan"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Apply a given patch plan"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    if not patch_plan_dir.exists() or not patch_plan_dir.is_dir():
        rprint(f"{ERROR_BADGE} patch_plan_dir must be an existing directory")
        raise typer.Exit(1)

    async with dbdriver.start_session() as db:
        patch_runner = get_patch_runner(db=db)
        await patch_runner.apply(patch_plan_directory=patch_plan_dir)
        rprint(f"{SUCCESS_BADGE} Patch plan successfully applied")

    await dbdriver.close()


@patch_app.command(name="revert")
async def revert_patch_cmd(
    ctx: typer.Context,
    patch_plan_dir: Path = typer.Argument(help="Path to the directory containing a patch plan"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Revert a given patch plan"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    db = await context.init_db(retry=1)

    if not patch_plan_dir.exists() or not patch_plan_dir.is_dir():
        rprint(f"{ERROR_BADGE} patch_plan_dir must be an existing directory")
        raise typer.Exit(1)

    patch_runner = get_patch_runner(db=db)
    await patch_runner.revert(patch_plan_directory=patch_plan_dir)
    rprint(f"{SUCCESS_BADGE} Patch plan successfully reverted")

    await db.close()
