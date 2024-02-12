import json
import logging
import os
from pathlib import Path
from timeit import default_timer as timer

import typer
import yaml
from infrahub_sdk import InfrahubClientSync
from rich.console import Console

from infrahub_sync import SyncInstance
from infrahub_sync.generator import render_template
from infrahub_sync.utils import get_all_sync, get_instance, get_potenda_from_instance

app = typer.Typer()
console = Console()

logging.basicConfig(level=logging.WARNING)

def print_error_and_abort(message: str):
    console.print(f"Error: {message}", style="bold red")
    raise typer.Abort()

@app.command(name="list")
def list_projects():
    """List all available SYNC projects."""
    for item in get_all_sync():
        console.print(f"{item.name} | {item.source.name} >> {item.destination.name} | {item.directory}")


@app.command(name="diff")
def diff_cmd(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    base_directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
    branch: str = typer.Option(default=None, help="Branch to use for the diff."),
    show_progress: bool = typer.Option(default=True, help="Show a progress bar during diff"),
):
    """Calculate and print the differences between the source and the destination systems for a given project."""
    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, base_directory=base_directory)
    if not sync_instance:
        print_error_and_abort("Failed to load sync instance.")

    ptd = get_potenda_from_instance(sync_instance=sync_instance, branch=branch, show_progress=show_progress)
    ptd.load()

    mydiff = ptd.diff()

    print(mydiff.str())


@app.command(name="sync")
def sync_cmd(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    base_directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
    branch: str = typer.Option(default=None, help="Branch to use for the sync."),
    diff: bool = typer.Option(
        default=True, help="Print the differences between the source and the destinatio before syncing"
    ),
    show_progress: bool = typer.Option(default=True, help="Show a progress bar during syncing"),

):
    """Synchronize the data between source and the destination systems for a given project or configuration file."""
    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, base_directory=base_directory)
    if not sync_instance:
        print_error_and_abort("Failed to load sync instance.")


    ptd = get_potenda_from_instance(sync_instance=sync_instance, branch=branch, show_progress=show_progress)
    ptd.load()

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


@app.command()
def generate(
    name: str = typer.Option(default=None, help="Name of the sync to use"),
    config_file: str = typer.Option(default=None, help="File path to the sync configuration YAML file"),
    base_directory: str = typer.Option(None, help="Base directory to search for sync configurations"),
):
    """Generate all the python files for a given sync based on the configuration."""

    if sum([bool(name), bool(config_file)]) != 1:
        print_error_and_abort("Please specify exactly one of 'name' or 'config_file'.")

    sync_instance = get_instance(name=name, config_file=config_file, base_directory=base_directory)
    if not sync_instance:
        print_error_and_abort(f"Unable to find the sync {name}. Use the list command to see the sync available")

    files_to_render = (
        ("diffsync_models.j2", "models.py"),
        ("diffsync_adapter.j2", "adapter.py"),
    )

    client = InfrahubClientSync()

    here = os.path.abspath(os.path.dirname(__file__))
    current_dir = str(os.getcwd())

    template_dir_absolute = str(os.path.join(here, "generator/templates"))
    template_dir_relative = template_dir_absolute.replace(current_dir, "")

    schema = client.schema.all()

    for adapter in [sync_instance.source, sync_instance.destination]:
        output_dir_absolute = str(os.path.join(sync_instance.directory, adapter.name))

        if not Path(output_dir_absolute).is_dir():
            Path(output_dir_absolute).mkdir(exist_ok=True)

        for item in files_to_render:
            render_template(
                template_dir=template_dir_relative,
                template_file=item[0],
                output_dir=output_dir_absolute,
                output_file=item[1],
                context={"schema": schema, "adapter": adapter, "config": sync_instance},
            )

            console.print(f"Saved {item[0]} in {item[1]}")
