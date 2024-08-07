import logging
from timeit import default_timer as timer

import typer
from infrahub_sdk import InfrahubClientSync
from infrahub_sdk.exceptions import ServerNotResponsiveError
from rich.console import Console

from infrahub_sync.utils import get_all_sync, get_instance, get_potenda_from_instance, render_adapter

app = typer.Typer()
console = Console()

logging.basicConfig(level=logging.WARNING)


def print_error_and_abort(message: str):
    console.print(f"Error: {message}", style="bold red")
    raise typer.Abort()


@app.command(name="list")
def list_projects(
    directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
):
    """List all available SYNC projects."""
    for item in get_all_sync(directory=directory):
        console.print(f"{item.name} | {item.source.name} >> {item.destination.name} | {item.directory}")


@app.command(name="diff")
def diff_cmd(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
    branch: str = typer.Option(default=None, help="Branch to use for the diff."),
    show_progress: bool = typer.Option(default=True, help="Show a progress bar during diff"),
):
    """Calculate and print the differences between the source and the destination systems for a given project."""
    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, directory=directory)
    if not sync_instance:
        print_error_and_abort("Failed to load sync instance.")

    ptd = get_potenda_from_instance(sync_instance=sync_instance, branch=branch, show_progress=show_progress)
    ptd.source_load()
    ptd.destination_load()

    mydiff = ptd.diff()

    print(mydiff.str())


@app.command(name="sync")
def sync_cmd(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
    branch: str = typer.Option(default=None, help="Branch to use for the sync."),
    diff: bool = typer.Option(
        default=True, help="Print the differences between the source and the destination before syncing"
    ),
    show_progress: bool = typer.Option(default=True, help="Show a progress bar during syncing"),
):
    """Synchronize the data between source and the destination systems for a given project or configuration file."""
    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, directory=directory)
    if not sync_instance:
        print_error_and_abort("Failed to load sync instance.")

    ptd = get_potenda_from_instance(sync_instance=sync_instance, branch=branch, show_progress=show_progress)
    ptd.source_load()
    ptd.destination_load()

    mydiff = ptd.diff()

    if mydiff.has_diffs():
        if diff:
            print(mydiff.str())
        start_synctime = timer()
        ptd.sync(diff=mydiff)
        end_synctime = timer()
        console.print(f"Sync: Completed in {end_synctime - start_synctime} sec")
    else:
        console.print("No diffence found. Nothing to sync")


@app.command(name="generate")
def generate(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
):
    """Generate all the python files for a given sync based on the configuration."""

    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, directory=directory)
    if not sync_instance:
        print_error_and_abort(f"Unable to find the sync {name}. Use the list command to see the sync available")

    # TODO
    # - Do not use the env variable token here if token is present in settings
    # - Do not use `main` if the branch is indicated in the file
    infrahub_address = None
    if sync_instance.destination.name == "infrahub":
        if sync_instance.destination.settings and isinstance(sync_instance.source.settings, dict):
            infrahub_address = sync_instance.destination.settings["url"]
    elif sync_instance.source.name == "infrahub":
        if sync_instance.source.settings and isinstance(sync_instance.source.settings, dict):
            infrahub_address = sync_instance.source.settings["url"]

    client = InfrahubClientSync(address=infrahub_address)

    try:
        schema = client.schema.all()
    except ServerNotResponsiveError as exc:
        print_error_and_abort(str(exc))

    rendered_files = render_adapter(sync_instance=sync_instance, schema=schema)
    for template, output_path in rendered_files:
        console.print(f"Rendered template {template} to {output_path}")
