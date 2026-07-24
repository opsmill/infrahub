from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer
from infrahub_sdk.async_typer import AsyncTyper
from rich.console import Console

from infrahub import config
from infrahub.components import ComponentType
from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.merge.failure_identifier import MergeFailureIdentifier
from infrahub.core.merge.failure_recoverer import MergeFailureRecoverer, RecoveryOutcome, RecoveryReport
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.registry import registry
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.dependencies.registry import build_component_registry
from infrahub.workers.dependencies import get_cache, get_component, set_component_type

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext

app = AsyncTyper()


# The callback registers this Typer app as a command group so that subcommands (e.g. ``merge``) nest
# under ``recover`` and it carries the group help. A single-subcommand group would otherwise collapse
# to the subcommand itself, losing the ``recover`` grouping.
@app.callback()
def callback() -> None:
    """Recover from failed operations."""


def _print_report(console: Console, report: RecoveryReport) -> None:
    if report.outcome is RecoveryOutcome.NOTHING_TO_RECOVER:
        console.print("[green]No failed merge to recover.[/green]")
    elif report.outcome is RecoveryOutcome.ORPHANED_CLEARED:
        console.print("[yellow]Cleared a stale merge-protection marker; there was no branch to recover.[/yellow]")
    elif report.outcome is RecoveryOutcome.RECOVERED:
        console.print(f"[bold green]Recovered the failed merge on branch '{report.branch}'.[/bold green]")
        if report.proposed_change is not None:
            console.print(f"Proposed change '{report.proposed_change}' was reset to OPEN.")
        console.print("Writes to the default branch are allowed again.")
    elif report.outcome is RecoveryOutcome.FAILED:
        console.print(
            f"[red]Recovery of branch '{report.branch}' failed. The branch stays protected; "
            f"review the logs and retry.[/red]"
        )


@app.command(name="merge")
async def recover_cmd(
    ctx: typer.Context,
    branch: str | None = typer.Argument(
        None, help="Name of the branch to recover; if omitted, the failed merge is auto-detected."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Recover even when the merge lock is absent/ambiguous, not just when the worker is confirmed dead.",
    ),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Recover a failed branch merge.

    Roll back the partial graph merge and reset the branch (and any associated proposed change) to
    OPEN, then lift the write protection so the default branch is writable again. Idempotent: a run
    with nothing to recover reports so and makes no changes. By default only a merge whose worker is
    confirmed dead is recovered; pass --force to also recover a merge stuck with an absent/ambiguous
    lock.

    Raises:
        Exit: When the recovery does not complete successfully (raises typer.Exit to signal a
            non-zero exit status to the caller).

    """
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    console = Console()

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    db = await context.init_db(retry=1)

    try:
        await initialize_registry(db=db)
        set_component_type(component_type=ComponentType.API_SERVER)
        build_component_registry()

        cache = await get_cache()
        component = await get_component()
        merge_write_blocker = MergeWriteBlocker(cache=cache)
        default_branch = await Branch.get_by_name(db=db, name=registry.default_branch)

        # The proposed-change lookup during recovery resolves its schema through ``db.schema``, which
        # prefers a schema attached to the db over the global registry. Build the internal and core
        # schema in a fresh, registry-independent manager and attach it to the db, so recovery works
        # without depending on (or mutating) the global registry or any user-defined schema.
        schema_manager = SchemaManager()
        schema_branch = schema_manager.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)
        schema_branch.load_schema(schema=SchemaRoot(**core_models))
        schema_branch.process()
        db.add_schema(schema=schema_branch, name=default_branch.name)

        identifier = MergeFailureIdentifier(
            db=db,
            cache=cache,
            component=component,
            merge_write_blocker=merge_write_blocker,
            default_branch=default_branch,
            grace_period_seconds=config.SETTINGS.main.merge_failure_grace_period_seconds,
        )
        recoverer = MergeFailureRecoverer(
            db=db,
            merge_write_blocker=merge_write_blocker,
            identifier=identifier,
            default_branch=default_branch,
            cache=cache,
            rollbacker=GraphRollbacker(db=db),
            schema_manager=schema_manager,
        )

        preview = await recoverer.preview(force=force, branch_name=branch)
        if preview.outcome is RecoveryOutcome.RECOVERABLE:
            console.print(f"A failed merge was found on branch [bold]'{preview.branch}'[/bold].")
            if preview.merge_started_at is not None:
                console.print(f"The merge started at {preview.merge_started_at}.")
            if preview.proposed_change is not None:
                console.print(f"Associated proposed change: {preview.proposed_change}.")

            if not yes and not typer.confirm("Recover this failed merge?"):
                console.print("Aborted; no changes were made.")
                raise typer.Exit(code=1)

        # Pin recovery to the branch that was previewed and confirmed
        report = await recoverer.recover(force=force, branch_name=branch or preview.branch)
        _print_report(console=console, report=report)
        if report.outcome is RecoveryOutcome.FAILED:
            raise typer.Exit(code=1)
    finally:
        await db.close()
